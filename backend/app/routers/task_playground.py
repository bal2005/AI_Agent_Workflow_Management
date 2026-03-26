"""
Task Playground Router
======================
Runs an agent against a real filesystem using the GitHub Copilot SDK.
The agent can read files, list directories, and write files — all scoped
to the root_path the user provides.

POST /task-playground/run
"""

import os
import asyncio
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app import models
from app.database import get_db
from app.crypto import decrypt

router = APIRouter(prefix="/task-playground", tags=["task-playground"])


# ── Request / Response schemas ────────────────────────────────────────────────

class TaskRunRequest(BaseModel):
    agent_id: int
    task: str
    root_path: str
    allowed_permissions: list[str] = []          # filesystem permissions
    shell_permissions: dict = {}                  # {"execute_commands": true, "allow_read_only_commands": true}
    web_permissions: dict = {}                    # {"perform_search": true, "open_result_links": true}


class TaskRunResponse(BaseModel):
    result: str
    steps: list[str] = []           # tool calls made during execution
    engine: str = "copilot-sdk"


# ── Filesystem tool implementations ──────────────────────────────────────────

# In-memory snapshots keyed by root path — used for change detection
_snapshots: dict[str, dict[str, float]] = {}


def _safe_path(root: Path, rel: str) -> Path:
    """Resolve a relative path inside root, raise if it escapes root."""
    target = (root / rel).resolve()
    if not str(target).startswith(str(root.resolve())):
        raise ValueError(f"Path '{rel}' escapes the allowed root directory")
    return target


def _scan_mtimes(base: Path, root: Path) -> dict[str, float]:
    """Return {relative_path: mtime} for all files under base."""
    result = {}
    for item in base.rglob("*"):
        if item.is_file():
            try:
                result[str(item.relative_to(root))] = item.stat().st_mtime
            except Exception:
                pass
    return result


def fs_list_directory(root: Path, rel_path: str = ".") -> str:
    target = _safe_path(root, rel_path)
    if not target.exists():
        return f"Error: path '{rel_path}' does not exist"
    if not target.is_dir():
        return f"Error: '{rel_path}' is not a directory"
    entries = []
    for item in sorted(target.iterdir()):
        kind = "DIR " if item.is_dir() else "FILE"
        size = f"  ({item.stat().st_size} bytes)" if item.is_file() else ""
        entries.append(f"{kind}  {item.name}{size}")
    return "\n".join(entries) if entries else "(empty directory)"


def fs_read_file(root: Path, rel_path: str) -> str:
    """Read a file — supports .txt/.md/code, .pdf, and .docx."""
    target = _safe_path(root, rel_path)
    if not target.exists():
        return f"Error: file '{rel_path}' does not exist"
    if not target.is_file():
        return f"Error: '{rel_path}' is not a file"

    suffix = target.suffix.lower()

    # ── PDF ──
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(target))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n--- Page Break ---\n\n".join(pages).strip()
            return text or "(PDF has no extractable text)"
        except ImportError:
            return "Error: pypdf not installed. Run: pip install pypdf"
        except Exception as e:
            return f"Error reading PDF: {e}"

    # ── DOCX ──
    if suffix == ".docx":
        try:
            from docx import Document
            doc = Document(str(target))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs) or "(DOCX has no text content)"
        except ImportError:
            return "Error: python-docx not installed. Run: pip install python-docx"
        except Exception as e:
            return f"Error reading DOCX: {e}"

    # ── Plain text / code ──
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return target.read_text(encoding="latin-1")
        except Exception as e:
            return f"Error reading file (binary?): {e}"
    except Exception as e:
        return f"Error reading file: {e}"


def fs_write_file(root: Path, rel_path: str, content: str) -> str:
    """Create a new file or fully overwrite an existing one."""
    target = _safe_path(root, rel_path)
    existed = target.exists()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        action = "Overwrote" if existed else "Created"
        return f"{action} '{rel_path}' ({len(content)} characters)"
    except Exception as e:
        return f"Error writing file: {e}"


def fs_edit_file(root: Path, rel_path: str, old_text: str, new_text: str) -> str:
    """
    Edit an existing file by replacing the first occurrence of old_text with new_text.
    Use this instead of write_file when you only want to change part of an existing file.
    Always call read_file first to get the exact current content.
    old_text must not be empty — use append_to_file to add content at the end.
    """
    if not old_text.strip():
        return (
            "Error: old_text cannot be empty. "
            "To add content at the end of a file use append_to_file. "
            "To replace content use read_file first to get the exact text to replace."
        )
    target = _safe_path(root, rel_path)
    if not target.exists():
        return f"Error: file '{rel_path}' does not exist. Use write_file to create it."
    try:
        current = target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file for edit: {e}"

    if old_text not in current:
        return (
            f"Error: the text to replace was not found in '{rel_path}'.\n"
            f"Make sure old_text matches exactly (including whitespace/newlines).\n"
            f"Tip: use read_file first to see the exact current content."
        )

    updated = current.replace(old_text, new_text, 1)
    try:
        target.write_text(updated, encoding="utf-8")
        return f"Successfully edited '{rel_path}' — replaced {len(old_text)} chars with {len(new_text)} chars"
    except Exception as e:
        return f"Error writing edited file: {e}"


def fs_append_to_file(root: Path, rel_path: str, content: str) -> str:
    """Append content to the end of an existing file without touching existing content."""
    target = _safe_path(root, rel_path)
    if not target.exists():
        return f"Error: file '{rel_path}' does not exist. Use write_file to create it first."
    try:
        existing = target.read_text(encoding="utf-8")
        # Ensure we start on a new line
        separator = "\n" if existing and not existing.endswith("\n") else ""
        target.write_text(existing + separator + content, encoding="utf-8")
        return f"Successfully appended {len(content)} characters to '{rel_path}'"
    except Exception as e:
        return f"Error appending to file: {e}"


def fs_snapshot_changes(root: Path, rel_path: str = ".") -> str:
    """
    Take a snapshot of current file modification times.
    Call this BEFORE the operation you want to monitor.
    Then call get_changes_since_snapshot after to see what changed.
    """
    target = _safe_path(root, rel_path)
    if not target.exists():
        return f"Error: path '{rel_path}' does not exist"
    base = target if target.is_dir() else target.parent
    snapshot = _scan_mtimes(base, root)
    _snapshots[str(root.resolve())] = snapshot
    return f"Snapshot taken — tracking {len(snapshot)} files under '{rel_path}'"


def fs_get_changes(root: Path, rel_path: str = ".") -> str:
    """
    Compare current filesystem state against the last snapshot.
    Returns lists of new, modified, and deleted files since the snapshot.
    """
    key = str(root.resolve())
    if key not in _snapshots:
        return "No snapshot found. Call snapshot_changes first, then make your changes, then call this."

    target = _safe_path(root, rel_path)
    base = target if target.is_dir() else target.parent
    current = _scan_mtimes(base, root)
    before = _snapshots[key]

    added = [f for f in current if f not in before]
    deleted = [f for f in before if f not in current]
    modified = [
        f for f in current
        if f in before and current[f] != before[f]
    ]

    if not added and not deleted and not modified:
        return "No changes detected since snapshot."

    lines = []
    if added:
        lines.append(f"NEW ({len(added)}):")
        lines.extend(f"  + {f}" for f in sorted(added))
    if modified:
        lines.append(f"MODIFIED ({len(modified)}):")
        lines.extend(f"  ~ {f}" for f in sorted(modified))
    if deleted:
        lines.append(f"DELETED ({len(deleted)}):")
        lines.extend(f"  - {f}" for f in sorted(deleted))

    return "\n".join(lines)


# ── Tool definitions for Copilot SDK ─────────────────────────────────────────

def _build_fs_tools(root: Path, permissions: list[str]) -> list[dict]:
    """Return tool definitions scoped to the granted permissions."""
    tools = []

    if "browse_folders" in permissions or "read_files" in permissions:
        tools.append({
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files and folders in a directory. Use '.' for the root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to list (default '.')"}
                    },
                    "required": [],
                },
            },
        })

    if "read_files" in permissions:
        tools.append({
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the full content of a file. Supports .txt, .md, code files, .pdf, and .docx.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file"}
                    },
                    "required": ["path"],
                },
            },
        })

    if "write_files" in permissions:
        tools.append({
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Create a new file or fully overwrite an existing file. Use edit_file instead if you only want to change part of an existing file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to write"},
                        "content": {"type": "string", "description": "Full file content"},
                    },
                    "required": ["path", "content"],
                },
            },
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": (
                    "Edit an existing file by replacing a specific piece of text. "
                    "Use this instead of write_file when modifying part of an existing file. "
                    "old_text must not be empty — use append_to_file to add content at the end. "
                    "Always call read_file first to get the exact current content."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file"},
                        "old_text": {"type": "string", "description": "The exact text to find and replace (must not be empty)"},
                        "new_text": {"type": "string", "description": "The replacement text"},
                    },
                    "required": ["path", "old_text", "new_text"],
                },
            },
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "append_to_file",
                "description": (
                    "Append content to the END of an existing file without changing existing content. "
                    "Use this when the task says 'add', 'append', or 'insert at the end'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file"},
                        "content": {"type": "string", "description": "Content to append at the end"},
                    },
                    "required": ["path", "content"],
                },
            },
        })

    if "detect_file_changes" in permissions or "detect_folder_changes" in permissions:
        tools.append({
            "type": "function",
            "function": {
                "name": "snapshot_changes",
                "description": "Take a snapshot of current file modification times. Call this BEFORE making changes you want to track.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to snapshot (default '.')"}
                    },
                    "required": [],
                },
            },
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "get_changes_since_snapshot",
                "description": "Compare current filesystem state to the last snapshot. Returns new, modified, and deleted files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to check (default '.')"}
                    },
                    "required": [],
                },
            },
        })

    return tools


def _dispatch_tool(name: str, args: dict, root: Path) -> str:
    """Execute a tool call — filesystem, shell, or web."""
    from app.shell_tools import dispatch_shell_tool, _READONLY_TOOLS, _WRITE_TOOLS
    from app.web_tools import dispatch_web_tool, ALL_WEB_TOOL_NAMES
    # Filesystem tools
    if name == "list_directory":
        return fs_list_directory(root, args.get("path", "."))
    elif name == "read_file":
        return fs_read_file(root, args.get("path", ""))
    elif name == "write_file":
        return fs_write_file(root, args.get("path", ""), args.get("content", ""))
    elif name == "edit_file":
        return fs_edit_file(root, args.get("path", ""), args.get("old_text", ""), args.get("new_text", ""))
    elif name == "append_to_file":
        return fs_append_to_file(root, args.get("path", ""), args.get("content", ""))
    elif name == "snapshot_changes":
        return fs_snapshot_changes(root, args.get("path", "."))
    elif name == "get_changes_since_snapshot":
        return fs_get_changes(root, args.get("path", "."))
    # Shell tools
    elif name in _READONLY_TOOLS or name in _WRITE_TOOLS:
        return dispatch_shell_tool(name, args)
    # Web tools
    elif name in ALL_WEB_TOOL_NAMES:
        return dispatch_web_tool(name, args)
    else:
        return f"Unknown tool: {name}"


# ── Copilot SDK agentic loop ──────────────────────────────────────────────────

async def _run_agent_loop(
    config: models.LLMConfig,
    skill: str,
    task: str,
    root: Path,
    tools: list[dict],
    max_iterations: int = 10,
) -> tuple[str, list[str]]:
    import httpx

    steps: list[str] = []
    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    api_key = config.api_key or ""
    model = config.model_name or "gpt-4o"

    messages = [
        {"role": "system", "content": skill},
        {"role": "user", "content": task},
    ]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _clean_messages(msgs: list) -> list:
        """
        Remove any trailing assistant messages that have tool_calls but no
        corresponding tool response — Groq rejects these with 400.
        """
        cleaned = list(msgs)
        # Collect tool_call_ids that have been responded to
        responded_ids = {
            m["tool_call_id"]
            for m in cleaned
            if m.get("role") == "tool" and m.get("tool_call_id")
        }
        result = []
        for m in cleaned:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                pending = [tc["id"] for tc in m["tool_calls"] if tc["id"] not in responded_ids]
                if pending:
                    # Drop this assistant message — it has unanswered tool calls
                    continue
            result.append(m)
        return result

    final_answer = ""

    for iteration in range(max_iterations):
        safe_messages = _clean_messages(messages)
        body: dict = {
            "model": model,
            "messages": safe_messages,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
            body["parallel_tool_calls"] = False

        if config.temperature is not None:
            body["temperature"] = config.temperature
        if config.max_tokens is not None:
            body["max_tokens"] = config.max_tokens

        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text

            # ── Full diagnostics on 400 ──────────────────────────────────────
            total_chars = sum(len(str(m.get("content") or "")) for m in safe_messages)
            print("=" * 60, flush=True)
            print(f"[400 ERROR] model={model}", flush=True)
            print(f"[400 ERROR] url={base_url}/chat/completions", flush=True)
            print(f"[400 ERROR] response body: {detail}", flush=True)
            print(f"[400 ERROR] message_count={len(safe_messages)}", flush=True)
            print(f"[400 ERROR] total_content_chars={total_chars}", flush=True)
            print(f"[400 ERROR] has_tools={bool(tools)} tool_choice={body.get('tool_choice')} parallel={body.get('parallel_tool_calls')}", flush=True)
            print(f"[400 ERROR] temperature={body.get('temperature')} max_tokens={body.get('max_tokens')}", flush=True)
            print(f"[400 ERROR] message roles: {[m['role'] for m in safe_messages]}", flush=True)
            print("=" * 60, flush=True)
            # ────────────────────────────────────────────────────────────────

            if e.response.status_code == 400:
                fallback_body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": skill},
                        {"role": "user", "content": task},
                    ],
                }
                if config.temperature is not None:
                    fallback_body["temperature"] = config.temperature
                print(f"[400 FALLBACK] retrying with clean 2-msg history, no tools", flush=True)
                try:
                    fb_resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=fallback_body, timeout=60)
                    fb_resp.raise_for_status()
                    fb_msg = fb_resp.json()["choices"][0]["message"]
                    return (fb_msg.get("content") or "[No response]"), steps
                except httpx.HTTPStatusError as fb_e:
                    try:
                        fb_detail = fb_e.response.json()
                    except Exception:
                        fb_detail = fb_e.response.text
                    print(f"[400 FALLBACK ERROR] status={fb_e.response.status_code} body={fb_detail}", flush=True)
                    print(f"[400 FALLBACK ERROR] fallback_msg_count={len(fallback_body['messages'])} temperature={fallback_body.get('temperature')}", flush=True)
                    return f"[Fallback error] {fb_detail}", steps
                except Exception as fb_e:
                    print(f"[400 FALLBACK ERROR] {fb_e}", flush=True)
                    return f"[Fallback error] {fb_e}", steps
            return f"[API error {e.response.status_code}] {detail}", steps

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            final_answer = msg.get("content") or "[No response]"
            break

        # Execute each tool call and feed results back
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            try:
                fn_args = json.loads(raw_args)
                if not isinstance(fn_args, dict):
                    raise ValueError("args not a dict")
            except (json.JSONDecodeError, ValueError):
                # Model produced malformed JSON — skip this call gracefully
                steps.append(f"⚠ {fn_name}() — malformed arguments, skipping")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": f"Error: could not parse tool arguments. Please try again with valid JSON.",
                })
                continue

            steps.append(f"🔧 {fn_name}({', '.join(f'{k}={repr(v)}' for k, v in fn_args.items())})")
            tool_result = _dispatch_tool(fn_name, fn_args, root)
            steps.append(f"   → {tool_result[:200]}{'...' if len(tool_result) > 200 else ''}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })
    else:
        final_answer = "[Max iterations reached] " + (msg.get("content") or "")

    return final_answer, steps


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/run", response_model=TaskRunResponse)
async def run_task(payload: TaskRunRequest, db: Session = Depends(get_db)):
    # Load agent
    agent = db.query(models.Agent).filter(models.Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Load active LLM config
    config = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()
    if not config:
        raise HTTPException(status_code=400, detail="No active LLM config. Set one in LLM Config page.")

    config.api_key = decrypt(config.api_key) if config.api_key else ""

    # Validate root path
    root = Path(payload.root_path)
    if not root.exists():
        raise HTTPException(status_code=400, detail=f"Root path does not exist: {payload.root_path}")
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Root path is not a directory: {payload.root_path}")

    # Determine permissions — use payload override or fall back to agent's DB permissions
    permissions = payload.allowed_permissions
    if not permissions:
        access = (
            db.query(models.AgentToolAccess)
            .join(models.Tool)
            .filter(
                models.AgentToolAccess.agent_id == agent.id,
                models.Tool.key == "filesystem",
            )
            .first()
        )
        permissions = access.granted_permissions if access else ["read_files", "browse_folders"]

    # Build filesystem tool definitions
    fs_tools = _build_fs_tools(root, permissions)

    # Build shell tool definitions
    from app.shell_tools import build_shell_tools
    sh_tools = build_shell_tools(payload.shell_permissions)

    # Build web tool definitions
    from app.web_tools import build_web_tools
    web_tools = build_web_tools(payload.web_permissions)

    all_tools = fs_tools + sh_tools + web_tools

    # Describe active tool groups in the skill context
    tool_context_lines = [
        f"You have access to the local filesystem at: {root.resolve()}",
        f"All filesystem paths must be relative to this root directory.",
        f"Filesystem permissions: {', '.join(permissions) or 'none'}",
    ]
    if sh_tools:
        sp = payload.shell_permissions
        tool_context_lines.append(
            f"Shell access: read-only={'yes' if sp.get('allow_read_only_commands') else 'no'}, "
            f"write-impacting={'yes' if sp.get('allow_write_impacting_commands') else 'no'}"
        )
    if web_tools:
        wp = payload.web_permissions
        tool_context_lines.append(
            f"Web access: search={'yes' if wp.get('perform_search') else 'no'}, "
            f"open links={'yes' if wp.get('open_result_links') else 'no'}"
        )

    skill = agent.system_prompt + "\n\n" + "\n".join(tool_context_lines)

    # Run the agentic loop
    result, steps = await _run_agent_loop(config, skill, payload.task, root, all_tools)

    return TaskRunResponse(result=result, steps=steps, engine="copilot-sdk")
