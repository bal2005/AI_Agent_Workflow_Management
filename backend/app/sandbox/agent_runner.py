"""
Agent Runner — executes inside the sandbox container.

This module is the entrypoint for the Docker container. It:
  1. Reads the task payload from /workspace/.task_input.json
  2. Loads agent permissions (passed in payload — already validated by host)
  3. Calls the LLM with the system prompt and user message
  4. Executes tool calls, checking permissions before each one
  5. Writes structured output to /workspace/.task_output.json
  6. Writes a human-readable log to /workspace/run.log

When running inside Docker, this file is the CMD entrypoint.
When running in-process (fallback), run_agent_task() is called directly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

# ── Logging setup (writes to /workspace/run.log inside container) ─────────────

def _setup_file_logger(workspace: Path):
    import logging
    log_path = workspace / "run.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stdout))
    root.setLevel(logging.DEBUG)
    return logging.getLogger("agent_runner")


# ── Tool implementations (scoped to /workspace) ───────────────────────────────

def _tool_read_file(workspace: Path, path: str) -> str:
    target = (workspace / path).resolve()
    # Security: ensure path stays inside workspace
    if not str(target).startswith(str(workspace.resolve())):
        return f"Error: path '{path}' is outside the allowed workspace"
    if not target.exists():
        return f"Error: file '{path}' does not exist"
    return target.read_text(encoding="utf-8", errors="replace")


def _tool_write_file(workspace: Path, path: str, content: str) -> str:
    target = (workspace / path).resolve()
    if not str(target).startswith(str(workspace.resolve())):
        return f"Error: path '{path}' is outside the allowed workspace"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to '{path}'"


def _tool_list_directory(workspace: Path, path: str = ".") -> str:
    target = (workspace / path).resolve()
    if not str(target).startswith(str(workspace.resolve())):
        return f"Error: path '{path}' is outside the allowed workspace"
    if not target.is_dir():
        return f"Error: '{path}' is not a directory"
    entries = [f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in sorted(target.iterdir())]
    return "\n".join(entries) or "(empty)"


def _tool_shell_exec(command: str) -> str:
    """Execute a shell command inside the container."""
    import subprocess
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout + (f"\n[stderr] {result.stderr}" if result.stderr else "")
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s"
    except Exception as e:
        return f"Error: {e}"


# ── Permission-gated tool dispatcher ─────────────────────────────────────────

# Maps tool_name → (tool_key, permission_key, handler_fn)
_TOOL_REGISTRY = {
    "read_file":      ("filesystem", "read_files"),
    "write_file":     ("filesystem", "write_files"),
    "list_directory": ("filesystem", "read_files"),
    "shell_exec":     ("shell",      "execute_commands"),
}


def dispatch_tool(
    name: str,
    args: dict,
    workspace: Path,
    granted_permissions: dict[str, list[str]],
    log,
) -> str:
    """
    Execute a tool call after checking permissions.

    granted_permissions: { tool_key: [permission_key, ...] }
    This dict is built from the DB on the host and passed in the task payload.
    It is NOT taken from the HTTP request.
    """
    if name not in _TOOL_REGISTRY:
        return f"Unknown tool: {name}"

    tool_key, permission_key = _TOOL_REGISTRY[name]
    allowed = permission_key in granted_permissions.get(tool_key, [])

    if not allowed:
        msg = f"PERMISSION DENIED: agent does not have '{permission_key}' on '{tool_key}'"
        log.warning(msg)
        return msg  # safe error — does not raise, lets LLM continue

    log.info(f"Tool call: {name}({args})")

    if name == "read_file":
        return _tool_read_file(workspace, args.get("path", ""))
    elif name == "write_file":
        return _tool_write_file(workspace, args.get("path", ""), args.get("content", ""))
    elif name == "list_directory":
        return _tool_list_directory(workspace, args.get("path", "."))
    elif name == "shell_exec":
        return _tool_shell_exec(args.get("command", ""))
    return f"Tool '{name}' has no handler"


# ── LLM call (direct httpx — no SDK inside container) ────────────────────────

def call_llm(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    tools: list[dict],
    temperature: Optional[float],
    max_tokens: Optional[int],
) -> dict:
    """Call the LLM API and return the raw response dict."""
    import httpx

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body: dict = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()


# ── Main agent loop ───────────────────────────────────────────────────────────

def run_agent_task(payload: dict, workspace: Path) -> dict:
    """
    Execute one task inside the sandbox.

    payload keys:
      system_prompt       — agent's instructions
      user_message        — task description + prior context
      llm_base_url        — e.g. https://api.openai.com/v1
      llm_api_key         — decrypted on host before passing
      llm_model           — e.g. gpt-4o
      llm_temperature     — optional float
      llm_max_tokens      — optional int
      granted_permissions — { tool_key: [permission_key, ...] }
      available_tools     — list of tool names the agent may attempt
    """
    log = _setup_file_logger(workspace)
    log.info(f"Agent runner started | workspace={workspace}")

    system_prompt       = payload.get("system_prompt", "")
    user_message        = payload.get("user_message", "")
    base_url            = payload.get("llm_base_url", "https://api.openai.com/v1").rstrip("/")
    api_key             = payload.get("llm_api_key", "")
    model               = payload.get("llm_model", "gpt-4o")
    temperature         = payload.get("llm_temperature")
    max_tokens          = payload.get("llm_max_tokens")
    granted_permissions = payload.get("granted_permissions", {})
    available_tools     = payload.get("available_tools", [])

    log.info(f"Agent config | model={model} tools={available_tools} permissions={granted_permissions}")

    # Build OpenAI-format tool definitions for tools the agent may attempt
    tool_defs = _build_tool_definitions(available_tools)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]

    tool_usage_log: list[str] = []
    final_text = ""
    max_iterations = 10

    for iteration in range(max_iterations):
        log.info(f"LLM iteration {iteration + 1}")
        try:
            response = call_llm(base_url, api_key, model, messages, tool_defs, temperature, max_tokens)
        except Exception as e:
            log.error(f"LLM call failed: {e}")
            return {"success": False, "error": str(e), "tool_usage": tool_usage_log}

        choice = response["choices"][0]
        msg    = choice["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            final_text = msg.get("content") or "[No response]"
            log.info(f"Agent finished | output_chars={len(final_text)}")
            break

        # Execute each tool call
        for tc in tool_calls:
            fn_name  = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            try:
                fn_args = json.loads(raw_args)
            except json.JSONDecodeError:
                fn_args = {}

            result = dispatch_tool(fn_name, fn_args, workspace, granted_permissions, log)
            tool_usage_log.append(f"🔧 {fn_name}() → {result[:120]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
    else:
        final_text = msg.get("content") or "[Max iterations reached]"

    return {
        "success": True,
        "final_text": final_text,
        "tool_usage": tool_usage_log,
    }


def _build_tool_definitions(tool_names: list[str]) -> list[dict]:
    """Build minimal OpenAI tool definitions for the requested tools."""
    defs = {
        "read_file":      {"description": "Read a file from /workspace", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        "write_file":     {"description": "Write a file to /workspace",  "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
        "list_directory": {"description": "List files in a directory",   "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}},
        "shell_exec":     {"description": "Run a shell command",         "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    }
    return [
        {"type": "function", "function": {"name": name, **defs[name]}}
        for name in tool_names if name in defs
    ]


# ── Container entrypoint ──────────────────────────────────────────────────────

if __name__ == "__main__":
    workspace = Path("/workspace")
    input_file  = workspace / ".task_input.json"
    output_file = workspace / ".task_output.json"

    if not input_file.exists():
        output_file.write_text(json.dumps({"success": False, "error": "No .task_input.json found"}))
        sys.exit(1)

    payload = json.loads(input_file.read_text())
    result  = run_agent_task(payload, workspace)
    output_file.write_text(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
