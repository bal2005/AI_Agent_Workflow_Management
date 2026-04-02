"""
Agent Runner — executes inside the sandbox container using the Copilot SDK.

Flow:
  1. Read task payload from /run_workspace/.task_input.json
  2. Decrypt API key using ENCRYPTION_KEY env var
  3. Build Copilot SDK Tool objects for each permitted tool
  4. Create a CopilotClient session with BYOK provider config
  5. Register on_pre_tool_use hook — enforces granted_permissions at runtime
  6. Send user message, wait for session.idle event
  7. Write structured output to /run_workspace/.task_output.json
  8. Write human-readable log to /run_workspace/run.log

The SDK handles the tool call / result loop internally.
Permission enforcement happens in on_pre_tool_use before any tool executes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional


# ── API key decryption ────────────────────────────────────────────────────────

def _decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt the API key using ENCRYPTION_KEY env var (Fernet/AES-128).
    Falls back to returning the value as-is if decryption fails.
    The key is passed via container env var — never stored on disk.
    """
    if not encrypted_key:
        return ""
    enc_key = os.environ.get("ENCRYPTION_KEY", "").strip()
    if not enc_key:
        return encrypted_key  # dev mode — assume plaintext
    try:
        from cryptography.fernet import Fernet
        return Fernet(enc_key.encode()).decrypt(encrypted_key.encode()).decode()
    except Exception:
        return encrypted_key  # already plaintext or wrong key


# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logger(workspace: Path) -> logging.Logger:
    log_path = workspace / "run.log"
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_h = logging.FileHandler(log_path)
    file_h.setFormatter(fmt)
    stdout_h = logging.StreamHandler(sys.stdout)
    stdout_h.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(file_h)
    root.addHandler(stdout_h)
    root.setLevel(logging.INFO)
    return logging.getLogger("agent_runner")


# ── Tool implementations (all scoped to /workspace) ───────────────────────────

def _safe(workspace: Path, rel: str) -> Path:
    """Resolve path and assert it stays inside workspace."""
    target = (workspace / rel).resolve()
    if not str(target).startswith(str(workspace.resolve())):
        raise ValueError(f"Path '{rel}' escapes the workspace")
    return target


def _read_file(workspace: Path, path: str) -> str:
    try:
        t = _safe(workspace, path)
        if not t.exists():
            return f"Error: '{path}' does not exist"
        return t.read_text(encoding="utf-8", errors="replace")
    except ValueError as e:
        return f"Error: {e}"


def _write_file(workspace: Path, path: str, content: str) -> str:
    try:
        t = _safe(workspace, path)
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to '{path}'"
    except ValueError as e:
        return f"Error: {e}"


def _list_directory(workspace: Path, path: str = ".") -> str:
    try:
        t = _safe(workspace, path)
        if not t.is_dir():
            return f"Error: '{path}' is not a directory"
        entries = [f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in sorted(t.iterdir())]
        return "\n".join(entries) or "(empty)"
    except ValueError as e:
        return f"Error: {e}"


def _shell_exec(command: str) -> str:
    import subprocess
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return r.stdout + (f"\n[stderr] {r.stderr}" if r.stderr else "")
    except subprocess.TimeoutExpired:
        return "Error: command timed out"
    except Exception as e:
        return f"Error: {e}"


def _web_search(query: str, max_results: int = 8, topic: str = "general") -> str:
    """Tavily web search — requires TAVILY_API_KEY env var."""
    import httpx
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return "[Search error] TAVILY_API_KEY not set in container environment"
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": min(max_results, 10),
                "search_depth": "basic",
                "topic": topic,
                "include_answer": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        lines = []
        if data.get("answer"):
            lines.append(f"Answer: {data['answer']}\n")
        for i, r in enumerate(data.get("results", []), 1):
            lines.append(f"{i}. {r.get('title', '')}")
            lines.append(f"   URL: {r.get('url', '')}")
            lines.append(f"   {r.get('content', '')[:300]}")
            lines.append("")
        return "\n".join(lines).strip() or f"No results for: {query}"
    except Exception as e:
        return f"[Search error] {e}"


def _search_news(query: str, max_results: int = 8) -> str:
    return _web_search(query, max_results=max_results, topic="news")


def _search_domain(query: str, domain: str, max_results: int = 6) -> str:
    return _web_search(f"site:{domain} {query}", max_results=max_results)


def _open_result_link(url: str) -> str:
    return _extract_page_content(url, max_chars=2000)


def _extract_page_content(url: str, max_chars: int = 8000) -> str:
    import httpx
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return "[Search error] TAVILY_API_KEY not set in container environment"
    try:
        resp = httpx.post(
            "https://api.tavily.com/extract",
            json={"api_key": key, "urls": [url]},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results:
            r = results[0]
            title = r.get("title", "")
            content = r.get("raw_content", "") or r.get("content", "")
            return f"Title: {title}\nURL: {url}\n\n{content[:max_chars]}"
    except Exception:
        pass
    return f"URL: {url}\n\n[extract unavailable]"


# ── Permission-gated Copilot SDK Tool builder ─────────────────────────────────

# Maps tool name → (tool_key, permission_key)
# tool_key matches the key in granted_permissions dict
# permission_key is the specific permission required
_TOOL_PERMISSION_MAP = {
    "read_file":            ("filesystem",  "read_files"),
    "write_file":           ("filesystem",  "write_files"),
    "list_directory":       ("filesystem",  "read_files"),
    "shell_exec":           ("shell",       "execute_commands"),
    "perform_web_search":   ("web_search",  "perform_search"),
    "search_news":          ("web_search",  "perform_search"),
    "search_domain":        ("web_search",  "perform_search"),
    "open_result_link":     ("web_search",  "open_links"),
    "extract_page_content": ("web_search",  "open_links"),
}


def _build_sdk_tools(
    workspace: Path,
    available_tools: list[str],
    granted_permissions: dict[str, list[str]],
    log: logging.Logger,
) -> list:
    """
    Build Copilot SDK Tool objects for each tool in available_tools.

    Each tool's handler:
      1. Checks granted_permissions before executing
      2. Calls the actual implementation function
      3. Returns {"textResultForLlm": result, "resultType": "success"}

    The on_pre_tool_use hook provides a second layer of permission enforcement
    at the SDK level before the handler is even called.
    """
    try:
        from copilot.tools import Tool
    except ImportError:
        log.error("github-copilot-sdk not installed in container image")
        return []

    # Tool schemas — what the LLM sees
    _schemas: dict[str, dict] = {
        "read_file": {
            "description": "Read the full content of a file from /workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path to the file"}},
                "required": ["path"],
            },
        },
        "write_file": {
            "description": "Create or overwrite a file in /workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Relative path to write"},
                    "content": {"type": "string", "description": "Full file content"},
                },
                "required": ["path", "content"],
            },
        },
        "list_directory": {
            "description": "List files and folders in a directory. Use '.' for workspace root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative path (default '.')"}},
                "required": [],
            },
        },
        "shell_exec": {
            "description": "Execute a shell command inside the sandbox container.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command to run"}},
                "required": ["command"],
            },
        },
        "perform_web_search": {
            "description": "Search the web using Tavily. Returns titles, URLs, snippets, and a direct answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string",  "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 8)"},
                },
                "required": ["query"],
            },
        },
        "search_news": {
            "description": "Search for recent news articles using Tavily.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string",  "description": "News search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 8)"},
                },
                "required": ["query"],
            },
        },
        "search_domain": {
            "description": "Search within a specific website domain using Tavily.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string",  "description": "Search query"},
                    "domain":      {"type": "string",  "description": "Domain to restrict search to"},
                    "max_results": {"type": "integer", "description": "Max results (default 6)"},
                },
                "required": ["query", "domain"],
            },
        },
        "open_result_link": {
            "description": "Open a URL and return a preview of its content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to open"},
                },
                "required": ["url"],
            },
        },
        "extract_page_content": {
            "description": "Fetch a URL and extract full clean readable text content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch"},
                    "max_chars": {"type": "integer", "description": "Max characters to return (default 8000)"},
                },
                "required": ["url"],
            },
        },
    }

    tools = []

    for tool_name in available_tools:
        if tool_name not in _schemas:
            log.warning(f"Unknown tool requested: {tool_name} — skipping")
            continue

        schema = _schemas[tool_name]
        tool_key, permission_key = _TOOL_PERMISSION_MAP.get(tool_name, ("", ""))

        # Capture loop variables for the closure
        _name = tool_name
        _tkey = tool_key
        _pkey = permission_key

        def _make_handler(name, tkey, pkey):
            async def handler(invocation) -> object:
                # invocation is a ToolInvocation dataclass — .arguments is already parsed
                args = invocation.arguments if isinstance(invocation.arguments, dict) else {}
                if pkey and tkey:
                    if pkey not in granted_permissions.get(tkey, []):
                        msg = f"PERMISSION DENIED: '{pkey}' not granted on '{tkey}'"
                        log.warning(f"[{name}] {msg}")
                        try:
                            from copilot.types import ToolResult
                            return ToolResult(text_result_for_llm=msg, result_type="denied")
                        except ImportError:
                            return {"textResultForLlm": msg, "resultType": "denied"}
                log.info(f"Executing tool: {name}({args})")
                if name == "read_file":
                    result = _read_file(workspace, args.get("path", ""))
                elif name == "write_file":
                    result = _write_file(workspace, args.get("path", ""), args.get("content", ""))
                elif name == "list_directory":
                    result = _list_directory(workspace, args.get("path", "."))
                elif name == "shell_exec":
                    result = _shell_exec(args.get("command", ""))
                elif name == "perform_web_search":
                    result = _web_search(args.get("query", ""), args.get("max_results", 8))
                elif name == "search_news":
                    result = _search_news(args.get("query", ""), args.get("max_results", 8))
                elif name == "search_domain":
                    result = _search_domain(args.get("query", ""), args.get("domain", ""), args.get("max_results", 6))
                elif name == "open_result_link":
                    result = _open_result_link(args.get("url", ""))
                elif name == "extract_page_content":
                    result = _extract_page_content(args.get("url", ""), args.get("max_chars", 8000))
                else:
                    result = f"No handler for tool: {name}"
                log.info(f"Tool result [{name}]: {result[:120]}{'...' if len(result) > 120 else ''}")
                try:
                    from copilot.types import ToolResult
                    return ToolResult(text_result_for_llm=result, result_type="success")
                except ImportError:
                    return {"textResultForLlm": result, "resultType": "success"}
            return handler

        tools.append(Tool(
            name=tool_name,
            description=schema["description"],
            parameters=schema["parameters"],
            handler=_make_handler(_name, _tkey, _pkey),
        ))
        log.info(f"Registered SDK tool: {tool_name} (requires {permission_key} on {tool_key})")

    return tools


# ── Copilot SDK provider config builder ───────────────────────────────────────

def _build_provider(base_url: str, api_key: str, provider_hint: str = "openai"):
    """Build a typed ProviderConfig for the Copilot SDK (v1.0.0b+)."""
    from copilot.types import ProviderConfig
    provider_type = "openai"
    if provider_hint == "claude":
        provider_type = "anthropic"
    elif provider_hint == "azure":
        provider_type = "azure"
    url = base_url.rstrip("/") if base_url else None
    return ProviderConfig(
        type=provider_type,
        base_url=url or None,
        api_key=api_key or None,
    )


# ── Main async agent loop using Copilot SDK ───────────────────────────────────

async def _run_with_sdk(
    system_prompt: str,
    user_message: str,
    base_url: str,
    api_key: str,
    model: str,
    temperature: Optional[float],
    max_tokens: Optional[float],
    sdk_tools: list,
    granted_permissions: dict,
    provider_hint: str,
    log: logging.Logger,
) -> tuple[str, list[str]]:
    """
    Run the agent using the Copilot SDK typed API (v1.0.0b+).

    Uses SessionConfig dataclass + send_and_wait(MessageOptions).
    Raises on failure so run_agent_task can fall back to direct httpx.
    """
    from copilot import CopilotClient, PermissionHandler
    from copilot.types import (
        SessionConfig, SessionHooks, MessageOptions,
        SystemMessageReplaceConfig, InfiniteSessionConfig,
        PreToolUseHookInput, PreToolUseHookOutput,
        PostToolUseHookInput,
        ErrorOccurredHookInput,
    )

    tool_usage_log: list[str] = []

    async def on_pre_tool_use(inp: PreToolUseHookInput, ctx: dict) -> PreToolUseHookOutput:
        tool_name = inp.toolName if hasattr(inp, "toolName") else ""
        tool_key, permission_key = _TOOL_PERMISSION_MAP.get(tool_name, ("", ""))
        if tool_key and permission_key:
            if permission_key not in granted_permissions.get(tool_key, []):
                msg = f"⛔ DENIED: {tool_name} (needs '{permission_key}' on '{tool_key}')"
                log.warning(msg)
                tool_usage_log.append(msg)
                return PreToolUseHookOutput(permissionDecision="deny")
        tool_usage_log.append(f"✅ allowed: {tool_name}")
        return PreToolUseHookOutput(permissionDecision="allow")

    async def on_post_tool_use(inp: PostToolUseHookInput, ctx: dict) -> None:
        tool_name = inp.toolName if hasattr(inp, "toolName") else "?"
        tool_usage_log.append(f"🔧 {tool_name}() completed")

    async def on_error_occurred(inp: ErrorOccurredHookInput, ctx: dict) -> None:
        err = getattr(inp, "error", str(inp))
        log.warning(f"SDK error: {err}")
        tool_usage_log.append(f"⚠ error: {str(err)[:120]}")

    hooks = SessionHooks(
        on_pre_tool_use=on_pre_tool_use,
        on_post_tool_use=on_post_tool_use,
        on_error_occurred=on_error_occurred,
    )

    session_cfg = SessionConfig(
        model=model,
        system_message=SystemMessageReplaceConfig(mode="replace", content=system_prompt),
        on_permission_request=PermissionHandler.approve_all,
        provider=_build_provider(base_url, api_key, provider_hint),
        tools=sdk_tools,
        hooks=hooks,
        infinite_sessions=InfiniteSessionConfig(enabled=False),
    )

    client = CopilotClient()
    session = None

    try:
        log.info(f"Starting SDK session | model={model} tools={[t.name for t in sdk_tools]}")
        await client.start()
        session = await client.create_session(session_cfg)

        event = await session.send_and_wait(
            MessageOptions(prompt=user_message),
            timeout=180.0,
        )

        if event is None:
            final_text = "[No response — session timed out]"
        else:
            final_text = getattr(event.data, "content", None) or "[No response]"

        log.info(f"SDK session complete | output_chars={len(final_text)}")

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

    return final_text, tool_usage_log


# ── Main entry point ──────────────────────────────────────────────────────────

def run_agent_task(payload: dict, workspace: Path) -> dict:
    """
    Execute one task inside the sandbox.

    Uses the Copilot SDK for session management when possible.
    For BYOK providers (non-GitHub Copilot), falls back to direct httpx
    agentic loop which correctly forwards tool schemas to the external model.
    The SDK's custom Tool objects with handlers are designed for the Copilot
    service's native execution — they don't get forwarded to BYOK providers.
    """
    log = _setup_logger(workspace)
    log.info(f"Agent runner started | workspace={workspace}")

    system_prompt       = payload.get("system_prompt", "")
    user_message        = payload.get("user_message", "")
    base_url            = payload.get("llm_base_url", "https://api.openai.com/v1").rstrip("/")
    model               = payload.get("llm_model", "gpt-4o")
    temperature         = payload.get("llm_temperature")
    max_tokens          = payload.get("llm_max_tokens")
    provider_hint       = payload.get("llm_provider", "openai")
    granted_permissions = payload.get("granted_permissions", {})
    available_tools     = payload.get("available_tools", [])

    api_key = _decrypt_api_key(
        payload.get("llm_api_key_enc", "") or payload.get("llm_api_key", "")
    )

    log.info(f"Config | model={model} provider={provider_hint} tools={available_tools}")
    log.info(f"Permissions | {granted_permissions}")

    # ── Try Copilot SDK first (all providers) ─────────────────────────────────
    # SDK supports BYOK via ProviderConfig(type="openai", base_url=..., api_key=...).
    # Falls back to direct httpx on any SDK failure.
    sdk_tools = _build_sdk_tools(workspace, available_tools, granted_permissions, log)
    log.info(f"Built {len(sdk_tools)} SDK tool(s)")

    try:
        final_text, tool_usage_log = asyncio.run(_run_with_sdk(
            system_prompt=system_prompt,
            user_message=user_message,
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            sdk_tools=sdk_tools,
            granted_permissions=granted_permissions,
            provider_hint=provider_hint,
            log=log,
        ))
        log.info(f"Agent finished via SDK | output_chars={len(final_text)}")
        return {"success": True, "final_text": final_text, "tool_usage": tool_usage_log}
    except Exception as e:
        log.warning(f"SDK run failed: {e} — falling back to direct httpx")

    return _run_direct_httpx(
        system_prompt, user_message, base_url, api_key, model,
        temperature, max_tokens, available_tools, granted_permissions,
        workspace, log,
    )


# ── Direct httpx fallback (when SDK unavailable) ──────────────────────────────

def _run_direct_httpx(
    system_prompt, user_message, base_url, api_key, model,
    temperature, max_tokens, available_tools, granted_permissions,
    workspace, log,
) -> dict:
    """Fallback agent loop using direct httpx — no SDK dependency."""
    import httpx

    tool_defs = _build_openai_tool_defs(available_tools)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    tool_usage_log: list[str] = []
    final_text = ""

    for iteration in range(10):
        body: dict = {"model": model, "messages": messages}
        if tool_defs:
            body["tools"] = tool_defs
            body["tool_choice"] = "auto"
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = int(max_tokens)

        try:
            resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=120)
            resp.raise_for_status()
        except Exception as e:
            log.error(f"LLM call failed: {e}")
            return {"success": False, "error": str(e), "tool_usage": tool_usage_log}

        msg = resp.json()["choices"][0]["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            final_text = msg.get("content") or "[No response]"
            break

        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments", "{}"))
            except Exception:
                args = {}

            # Permission check
            tkey, pkey = _TOOL_PERMISSION_MAP.get(name, ("", ""))
            if tkey and pkey and pkey not in granted_permissions.get(tkey, []):
                result = f"PERMISSION DENIED: '{pkey}' not granted on '{tkey}'"
                tool_usage_log.append(f"⛔ {name}() — {result}")
            else:
                result = _dispatch(name, args, workspace)
                tool_usage_log.append(f"🔧 {name}() → {result[:120]}")

            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    return {"success": True, "final_text": final_text, "tool_usage": tool_usage_log}


def _dispatch(name: str, args: dict, workspace: Path) -> str:
    if name == "read_file":
        return _read_file(workspace, args.get("path", ""))
    elif name == "write_file":
        return _write_file(workspace, args.get("path", ""), args.get("content", ""))
    elif name == "list_directory":
        return _list_directory(workspace, args.get("path", "."))
    elif name == "shell_exec":
        return _shell_exec(args.get("command", ""))
    elif name == "perform_web_search":
        return _web_search(args.get("query", ""), args.get("max_results", 8))
    elif name == "search_news":
        return _search_news(args.get("query", ""), args.get("max_results", 8))
    elif name == "search_domain":
        return _search_domain(args.get("query", ""), args.get("domain", ""), args.get("max_results", 6))
    elif name == "open_result_link":
        return _open_result_link(args.get("url", ""))
    elif name == "extract_page_content":
        return _extract_page_content(args.get("url", ""), args.get("max_chars", 8000))
    return f"Unknown tool: {name}"


def _build_openai_tool_defs(tool_names: list[str]) -> list[dict]:
    defs = {
        "read_file":          {"description": "Read a file",          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        "write_file":         {"description": "Write a file",         "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
        "list_directory":     {"description": "List directory",       "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}},
        "shell_exec":         {"description": "Run shell command",    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
        "perform_web_search": {"description": "Search the web",       "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
        "search_news":        {"description": "Search recent news",   "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
        "search_domain":      {"description": "Search a domain",      "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "domain": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query", "domain"]}},
        "open_result_link":   {"description": "Open a result link",   "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
        "extract_page_content":{"description": "Extract page content","parameters": {"type": "object", "properties": {"url": {"type": "string"}, "max_chars": {"type": "integer"}}, "required": ["url"]}},
    }
    return [{"type": "function", "function": {"name": n, **defs[n]}} for n in tool_names if n in defs]


# ── Container entrypoint ──────────────────────────────────────────────────────

if __name__ == "__main__":
    workspace = Path("/workspace")
    run_workspace = Path("/run_workspace")
    control_workspace = run_workspace if run_workspace.exists() else workspace
    input_file = control_workspace / ".task_input.json"
    output_file = control_workspace / ".task_output.json"

    if not input_file.exists():
        output_file.write_text(json.dumps({"success": False, "error": "No .task_input.json found"}))
        sys.exit(1)

    payload = json.loads(input_file.read_text())
    result = run_agent_task(payload, workspace)
    output_file.write_text(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
