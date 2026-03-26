"""
Workflow Runner — Phase 1
=========================
Sequential task execution using GitHub Copilot SDK per task.

Each task gets its own isolated CopilotClient + session.
Prior task output is passed as structured context in the user message.
Tool filtering is enforced via on_pre_tool_use hook.
tool_use_failed is recovered via on_error_occurred hook.
"""

import asyncio
import time
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from app import models
from app.crypto import decrypt
from app.prompt_utils import compose_agent_prompt

logger = logging.getLogger(__name__)

# ── Allowed tool names per permission set ─────────────────────────────────────

_FS_READ_TOOLS  = {"list_directory", "read_file"}
_FS_WRITE_TOOLS = {"write_file", "edit_file", "append_to_file"}

# Built-in CLI tools we never want the model to call via BYOK
_BLOCKED_BUILTIN_TOOLS = {
    "container.exec", "shell", "run_command", "execute_command",
    "bash", "python", "terminal",
}


def _allowed_tool_names(task: models.Task) -> set[str]:
    """Return the set of tool names this task is allowed to call."""
    mode = task.tool_usage_mode or "none"
    if mode == "none":
        return set()
    allowed = set(_FS_READ_TOOLS)
    if mode == "allowed":
        allowed |= _FS_WRITE_TOOLS
    return allowed


# ── SDK Tool builders ─────────────────────────────────────────────────────────

def _build_sdk_tools(task: models.Task) -> list:
    """
    Build Copilot SDK Tool objects for the task's allowed permissions.
    Uses the low-level Tool API so we don't need Pydantic models at module level.
    """
    try:
        from copilot.tools import Tool
    except ImportError:
        return []

    if not task.folder_path:
        return []

    root = Path(task.folder_path)
    if not root.exists() or not root.is_dir():
        return []

    from app.routers.task_playground import (
        fs_list_directory, fs_read_file, fs_write_file,
        fs_edit_file, fs_append_to_file,
    )

    mode = task.tool_usage_mode or "none"
    if mode == "none":
        return []

    tools = []

    # list_directory
    async def handle_list_directory(inv):
        path = inv.get("arguments", {}).get("path", ".")
        result = fs_list_directory(root, path)
        return {"textResultForLlm": result, "resultType": "success"}

    tools.append(Tool(
        name="list_directory",
        description="List files and folders in a directory. Use '.' for root.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path (default '.')"}},
            "required": [],
        },
        handler=handle_list_directory,
        skip_permission=True,
    ))

    # read_file
    async def handle_read_file(inv):
        path = inv.get("arguments", {}).get("path", "")
        result = fs_read_file(root, path)
        return {"textResultForLlm": result, "resultType": "success"}

    tools.append(Tool(
        name="read_file",
        description="Read the full content of a file.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path to the file"}},
            "required": ["path"],
        },
        handler=handle_read_file,
        skip_permission=True,
    ))

    if mode == "allowed":
        # write_file
        async def handle_write_file(inv):
            args = inv.get("arguments", {})
            result = fs_write_file(root, args.get("path", ""), args.get("content", ""))
            return {"textResultForLlm": result, "resultType": "success"}

        tools.append(Tool(
            name="write_file",
            description="Create or overwrite a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=handle_write_file,
            skip_permission=True,
        ))

        # edit_file
        async def handle_edit_file(inv):
            args = inv.get("arguments", {})
            result = fs_edit_file(root, args.get("path", ""), args.get("old_text", ""), args.get("new_text", ""))
            return {"textResultForLlm": result, "resultType": "success"}

        tools.append(Tool(
            name="edit_file",
            description="Replace a specific piece of text in an existing file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
            handler=handle_edit_file,
            skip_permission=True,
        ))

        # append_to_file
        async def handle_append_to_file(inv):
            args = inv.get("arguments", {})
            result = fs_append_to_file(root, args.get("path", ""), args.get("content", ""))
            return {"textResultForLlm": result, "resultType": "success"}

        tools.append(Tool(
            name="append_to_file",
            description="Append content to the end of an existing file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=handle_append_to_file,
            skip_permission=True,
        ))

    return tools


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_user_message(task: models.Task, prior_output: Optional[str]) -> str:
    """
    Build the user-turn message for this task.
    Prior task output is appended as context — NOT injected into system prompt.
    Trimmed to keep token usage stable.
    """
    parts = [task.description.strip()]

    if task.workflow and task.workflow.strip():
        parts.append(f"Follow these steps:\n{task.workflow.strip()}")

    if task.folder_path:
        parts.append(f"Working directory: {task.folder_path}")

    if prior_output and prior_output.strip():
        # Trim prior output to avoid token blowout
        trimmed = prior_output.strip()[:1500]
        if len(prior_output.strip()) > 1500:
            trimmed += "\n[prior output truncated]"
        parts.append(f"--- Context from previous step ---\n{trimmed}")

    return "\n\n".join(parts)


# ── LLM config resolver ───────────────────────────────────────────────────────

def _resolve_cfg(task: models.Task, db) -> SimpleNamespace:
    if task.llm_config_id:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.id == task.llm_config_id).first()
    else:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()
    if not cfg:
        raise RuntimeError("No active LLM config found")
    return SimpleNamespace(
        provider=task.llm_provider or cfg.provider,
        base_url=cfg.base_url,
        api_key=decrypt(cfg.api_key) if cfg.api_key else "",
        model_name=task.llm_model or cfg.model_name,
        temperature=task.llm_temperature if task.llm_temperature is not None else cfg.temperature,
        max_tokens=task.llm_max_tokens if task.llm_max_tokens is not None else cfg.max_tokens,
        top_p=task.llm_top_p if task.llm_top_p is not None else cfg.top_p,
        top_k=cfg.top_k,
        label=cfg.label,
    )


def _build_provider_config(cfg: SimpleNamespace) -> dict:
    """Map our config to Copilot SDK provider dict."""
    provider_type = "openai"
    if cfg.provider == "claude":
        provider_type = "anthropic"
    elif cfg.provider == "azure":
        provider_type = "azure"

    p: dict = {"type": provider_type}

    base_url = (cfg.base_url or "").rstrip("/")
    if base_url:
        if cfg.provider == "azure":
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            p["base_url"] = f"{parsed.scheme}://{parsed.netloc}"
            p["azure"] = {"api_version": "2024-10-21"}
        else:
            p["base_url"] = base_url

    if cfg.api_key:
        p["api_key"] = cfg.api_key

    return p


# ── Core SDK executor ─────────────────────────────────────────────────────────

async def execute_task_with_copilot(
    task: models.Task,
    cfg: SimpleNamespace,
    system_prompt: str,
    user_message: str,
    sdk_tools: list,
    allowed_tool_names: set[str],
) -> dict:
    """
    Execute one task using a fresh Copilot SDK session.
    Returns a structured result dict.
    """
    try:
        from copilot import CopilotClient, PermissionHandler
    except ImportError:
        raise RuntimeError("github-copilot-sdk not installed")

    tool_usage_log: list[str] = []
    final_text: str = ""
    done_event = asyncio.Event()

    # ── Hooks ─────────────────────────────────────────────────────────────────

    async def on_pre_tool_use(input_data, invocation):
        tool_name = input_data.get("toolName", "")
        # Block built-in CLI tools and anything not in allowed list
        if tool_name in _BLOCKED_BUILTIN_TOOLS or (allowed_tool_names and tool_name not in allowed_tool_names):
            logger.info(f"[WorkflowRunner] Blocking tool: {tool_name}")
            tool_usage_log.append(f"⛔ blocked: {tool_name}")
            return {"permissionDecision": "deny"}
        return {"permissionDecision": "allow", "modifiedArgs": input_data.get("toolArgs")}

    async def on_post_tool_use(input_data, invocation):
        tool_name = input_data.get("toolName", "")
        tool_usage_log.append(f"🔧 {tool_name}()")
        return {}

    async def on_error_occurred(input_data, invocation):
        error = input_data.get("error", "")
        ctx = input_data.get("errorContext", "")
        logger.warning(f"[WorkflowRunner] SDK error in {ctx}: {error}")
        tool_usage_log.append(f"⚠ error skipped: {ctx} — {str(error)[:120]}")
        # Skip tool_use_failed and similar — let model continue without the tool
        return {"errorHandling": "skip"}

    # ── Session config ─────────────────────────────────────────────────────────

    extra_body: dict = {}
    if cfg.temperature is not None:
        extra_body["temperature"] = cfg.temperature
    if cfg.top_p is not None:
        extra_body["top_p"] = cfg.top_p
    if cfg.max_tokens is not None:
        extra_body["max_tokens"] = cfg.max_tokens

    session_config: dict = {
        "model": cfg.model_name or "gpt-4o",
        "system_message": {"mode": "replace", "content": system_prompt},
        "on_permission_request": PermissionHandler.approve_all,
        "provider": _build_provider_config(cfg),
        "tools": sdk_tools,
        "infinite_sessions": {"enabled": False},
        "hooks": {
            "on_pre_tool_use": on_pre_tool_use,
            "on_post_tool_use": on_post_tool_use,
            "on_error_occurred": on_error_occurred,
        },
    }
    if extra_body:
        session_config["extra_body"] = extra_body

    # ── Run session ────────────────────────────────────────────────────────────

    client = CopilotClient()
    session = None

    try:
        await client.start()
        session = await client.create_session(session_config)

        def on_event(event):
            nonlocal final_text
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            if event_type == "assistant.message":
                final_text = getattr(event.data, "content", "") or ""
            elif event_type == "session.idle":
                done_event.set()

        session.on(on_event)
        await session.send(user_message)

        try:
            await asyncio.wait_for(done_event.wait(), timeout=120.0)
        except asyncio.TimeoutError:
            logger.warning("[WorkflowRunner] Session timed out after 120s")
            final_text = final_text or "[Timeout: no response within 120s]"

    finally:
        if session:
            try:
                await session.disconnect()
            except Exception:
                pass
        try:
            await client.stop()
        except Exception:
            pass

    return {
        "success": True,
        "final_text": final_text or "[No response]",
        "structured_output": {},
        "tool_usage": tool_usage_log,
        "logs": tool_usage_log,
        "metadata": {
            "model": cfg.model_name,
            "provider": cfg.provider,
            "agent_name": task.agent.name if task.agent else None,
            "task_id": task.id,
            "task_name": task.name,
        },
    }


# ── Fallback: direct httpx loop ───────────────────────────────────────────────

async def _execute_task_fallback(
    task: models.Task,
    cfg: SimpleNamespace,
    system_prompt: str,
    user_message: str,
) -> dict:
    """
    Fallback to direct httpx agent loop when Copilot SDK is unavailable
    or raises a non-recoverable error.
    """
    from app.routers.task_playground import _build_fs_tools, _run_agent_loop

    tools = []
    if task.tool_usage_mode != "none" and task.folder_path:
        root = Path(task.folder_path)
        if root.exists() and root.is_dir():
            perms = ["read_files", "browse_folders"]
            if task.tool_usage_mode == "allowed":
                perms += ["write_files"]
            tools = _build_fs_tools(root, perms)

    root_path = Path(task.folder_path) if task.folder_path else Path(".")
    result, steps = await _run_agent_loop(cfg, system_prompt, user_message, root_path, tools)

    return {
        "success": True,
        "final_text": result,
        "structured_output": {},
        "tool_usage": steps,
        "logs": steps,
        "metadata": {
            "model": cfg.model_name,
            "provider": cfg.provider,
            "agent_name": task.agent.name if task.agent else None,
            "task_id": task.id,
            "task_name": task.name,
            "engine": "fallback-httpx",
        },
    }


# ── Public entry point ────────────────────────────────────────────────────────

def run_task_in_workflow(
    task: models.Task,
    db,
    prior_output: Optional[str] = None,
) -> dict:
    """
    Synchronous wrapper — called from Celery task.
    Builds all config, composes prompts, runs SDK session, returns structured result.
    """
    cfg = _resolve_cfg(task, db)

    domain_prompt = task.agent.domain.domain_prompt if (task.agent and task.agent.domain) else None
    agent_prompt = task.agent.system_prompt if task.agent else ""
    if task.llm_system_behavior:
        agent_prompt = (agent_prompt + "\n\n" + task.llm_system_behavior).strip()

    # Add tool context hint to system prompt so model knows what's available
    allowed = _allowed_tool_names(task)
    if allowed:
        tool_hint = f"\nAvailable tools: {', '.join(sorted(allowed))}. Use only these — do not attempt shell, container, or system-level operations."
        agent_prompt = agent_prompt + tool_hint

    system_prompt, _ = compose_agent_prompt(domain_prompt, agent_prompt)
    user_message = _build_user_message(task, prior_output)
    sdk_tools = _build_sdk_tools(task)

    print(f"[WorkflowRunner] task={task.name} model={cfg.model_name} tools={[t.name for t in sdk_tools]} prior={'yes' if prior_output else 'no'}", flush=True)

    try:
        result = asyncio.run(execute_task_with_copilot(
            task=task,
            cfg=cfg,
            system_prompt=system_prompt,
            user_message=user_message,
            sdk_tools=sdk_tools,
            allowed_tool_names=allowed,
        ))
        print(f"[WorkflowRunner] ✓ task={task.name} success via SDK", flush=True)
        return result
    except Exception as e:
        logger.warning(f"[WorkflowRunner] SDK failed for task={task.name}: {e} — falling back to httpx")
        print(f"[WorkflowRunner] ⚠ SDK error: {e} — using fallback", flush=True)
        try:
            return asyncio.run(_execute_task_fallback(task, cfg, system_prompt, user_message))
        except Exception as fe:
            return {
                "success": False,
                "final_text": "",
                "structured_output": {},
                "tool_usage": [],
                "logs": [f"SDK error: {e}", f"Fallback error: {fe}"],
                "metadata": {"task_id": task.id, "task_name": task.name},
                "error": str(fe),
            }
