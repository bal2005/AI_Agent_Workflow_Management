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
from app.crypto import decrypt, encrypt
from app.prompt_utils import compose_agent_prompt

logger = logging.getLogger(__name__)

# ── Allowed tool names per permission set ─────────────────────────────────────

_FS_READ_TOOLS  = {"list_directory", "read_file"}
_FS_WRITE_TOOLS = {"write_file", "edit_file", "append_to_file"}
_SHELL_TOOLS    = {"shell_exec"}
_WEB_TOOLS      = {"perform_web_search", "search_news", "search_domain", "open_result_link", "extract_page_content"}

# Built-in CLI tools we never want the model to call via BYOK
_BLOCKED_BUILTIN_TOOLS = {
    "container.exec", "shell", "run_command", "execute_command",
    "bash", "python", "terminal",
}


def _encrypt_for_sandbox(api_key: str) -> str:
    """
    Re-encrypt the already-decrypted API key for safe storage in the
    workspace JSON file. The sandbox container decrypts it using the
    ENCRYPTION_KEY env var — the plaintext never touches the filesystem.
    Returns empty string if no key provided.
    """
    if not api_key:
        return ""
    return encrypt(api_key)


def _allowed_tool_names(task: models.Task, db=None) -> set[str]:
    """Return the set of tool names this task is allowed to call."""
    mode = task.tool_usage_mode or "none"
    allowed: set[str] = set()

    if mode != "none":
        allowed |= _FS_READ_TOOLS
        if mode == "allowed":
            allowed |= _FS_WRITE_TOOLS

    # Add shell tools if agent has execute_commands permission
    if db and task.agent_id:
        from app.sandbox.permissions import PermissionChecker
        checker = PermissionChecker.from_db(db, task.agent_id)
        if checker.allowed("shell", "execute_commands"):
            allowed |= _SHELL_TOOLS
        if checker.allowed("web_search", "perform_search"):
            allowed |= _WEB_TOOLS
        if checker.allowed("web_search", "open_links"):
            allowed |= {"open_result_link", "extract_page_content"}
    elif not db:
        # No db — skip permission check, tools controlled by task config only
        pass

    return allowed


# ── SDK Tool builders ─────────────────────────────────────────────────────────

def _build_sdk_tools(task: models.Task, db=None) -> list:
    """
    Build Copilot SDK Tool objects using the typed SDK API (v1.0.0b+).

    Handler signature:  async def handler(inv: ToolInvocation) -> ToolResult
    ToolInvocation.arguments is already a parsed dict — no json.loads needed.
    ToolResult uses snake_case: text_result_for_llm, result_type.
    """
    try:
        from copilot.types import Tool, ToolInvocation, ToolResult
    except ImportError:
        logger.warning("[WorkflowRunner] copilot.types not available — no SDK tools")
        return []

    root: Path | None = None
    if task.folder_path:
        p = Path(task.folder_path)
        if p.exists() and p.is_dir():
            root = p

    mode = task.tool_usage_mode or "none"
    tools: list = []

    def _ok(text: str) -> ToolResult:
        return ToolResult(text_result_for_llm=text, result_type="success")

    def _err(text: str) -> ToolResult:
        return ToolResult(text_result_for_llm=text, result_type="failure")

    # ── Filesystem tools ──────────────────────────────────────────────────────
    if mode != "none" and root is not None:
        from app.routers.task_playground import (
            fs_list_directory, fs_read_file, fs_write_file,
            fs_edit_file, fs_append_to_file,
        )
        _root = root  # capture for closures

        async def _list_dir(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(fs_list_directory(_root, args.get("path", ".")))

        async def _read_file(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(fs_read_file(_root, args.get("path", "")))

        tools += [
            Tool(name="list_directory",
                 description="List files and folders in a directory. Use '.' for root.",
                 parameters={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Relative path (default '.')"}},
                     "required": []},
                 handler=_list_dir),
            Tool(name="read_file",
                 description="Read the full content of a file.",
                 parameters={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Relative path to the file"}},
                     "required": ["path"]},
                 handler=_read_file),
        ]

        if mode == "allowed":
            async def _write_file(inv: ToolInvocation) -> ToolResult:
                args = inv.arguments if isinstance(inv.arguments, dict) else {}
                return _ok(fs_write_file(_root, args.get("path", ""), args.get("content", "")))

            async def _edit_file(inv: ToolInvocation) -> ToolResult:
                args = inv.arguments if isinstance(inv.arguments, dict) else {}
                return _ok(fs_edit_file(_root, args.get("path", ""), args.get("old_text", ""), args.get("new_text", "")))

            async def _append_file(inv: ToolInvocation) -> ToolResult:
                args = inv.arguments if isinstance(inv.arguments, dict) else {}
                return _ok(fs_append_to_file(_root, args.get("path", ""), args.get("content", "")))

            tools += [
                Tool(name="write_file",
                     description="Create or overwrite a file.",
                     parameters={"type": "object", "properties": {
                         "path": {"type": "string"}, "content": {"type": "string"}},
                         "required": ["path", "content"]},
                     handler=_write_file),
                Tool(name="edit_file",
                     description="Replace a specific piece of text in an existing file. Call read_file first.",
                     parameters={"type": "object", "properties": {
                         "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
                         "required": ["path", "old_text", "new_text"]},
                     handler=_edit_file),
                Tool(name="append_to_file",
                     description="Append content to the end of an existing file.",
                     parameters={"type": "object", "properties": {
                         "path": {"type": "string"}, "content": {"type": "string"}},
                         "required": ["path", "content"]},
                     handler=_append_file),
            ]

    # ── Shell tool ────────────────────────────────────────────────────────────
    has_shell = False
    if db and task.agent_id:
        try:
            from app.sandbox.permissions import PermissionChecker
            _checker = PermissionChecker.from_db(db, task.agent_id)
            has_shell = _checker.allowed("shell", "execute_commands")
        except Exception:
            pass

    if has_shell:
        async def _shell_exec_tool(inv) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            import subprocess
            command = args.get("command", "")
            cwd = args.get("cwd") or (str(root) if root else None)
            try:
                r = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    timeout=30, cwd=cwd,
                )
                out = (r.stdout or "") + (f"\n[stderr] {r.stderr}" if r.stderr else "")
                return _ok(out.strip()[:4000] or "(no output)")
            except subprocess.TimeoutExpired:
                return _err("Error: command timed out after 30s")
            except Exception as e:
                return _err(f"Error: {e}")

        tools.append(Tool(
            name="shell_exec",
            description=(
                "Execute a shell command and return its output. "
                "Use for: running Python scripts, grep, netstat, ipconfig, docker logs, "
                "pip install, git commands, or any CLI tool available in the environment."
            ),
            parameters={"type": "object", "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd":     {"type": "string", "description": "Working directory (optional, defaults to task folder)"},
            }, "required": ["command"]},
            handler=_shell_exec_tool,
        ))

    # ── Web search tools ──────────────────────────────────────────────────────
    has_search = False
    has_links  = False
    if db and task.agent_id:
        try:
            from app.sandbox.permissions import PermissionChecker
            checker = PermissionChecker.from_db(db, task.agent_id)
            has_search = checker.allowed("web_search", "perform_search")
            has_links  = checker.allowed("web_search", "open_links")
        except Exception:
            pass
    elif task.agent:
        for access in (task.agent.tool_access or []):
            if hasattr(access, "tool") and access.tool and access.tool.key == "web":
                granted = set(access.granted_permissions or [])
                has_search = "perform_search" in granted
                has_links  = "open_result_links" in granted
                break

    if has_search:
        from app.web_tools import perform_web_search, search_news, search_domain

        async def _web_search(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(perform_web_search(args.get("query", ""), args.get("max_results", 8)))

        async def _search_news(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(search_news(args.get("query", ""), args.get("max_results", 8)))

        async def _search_domain(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(search_domain(args.get("query", ""), args.get("domain", ""), args.get("max_results", 6)))

        tools += [
            Tool(name="perform_web_search",
                 description="Search the web using Tavily. Returns titles, URLs, snippets, and a direct answer.",
                 parameters={"type": "object", "properties": {
                     "query": {"type": "string"}, "max_results": {"type": "integer"}},
                     "required": ["query"]},
                 handler=_web_search),
            Tool(name="search_news",
                 description="Search for recent news articles using Tavily.",
                 parameters={"type": "object", "properties": {
                     "query": {"type": "string"}, "max_results": {"type": "integer"}},
                     "required": ["query"]},
                 handler=_search_news),
            Tool(name="search_domain",
                 description="Search within a specific website domain using Tavily.",
                 parameters={"type": "object", "properties": {
                     "query": {"type": "string"}, "domain": {"type": "string"}, "max_results": {"type": "integer"}},
                     "required": ["query", "domain"]},
                 handler=_search_domain),
        ]

    if has_links:
        from app.web_tools import open_result_link, extract_page_content

        async def _open_link(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(open_result_link(args.get("url", "")))

        async def _extract_page(inv: ToolInvocation) -> ToolResult:
            args = inv.arguments if isinstance(inv.arguments, dict) else {}
            return _ok(extract_page_content(args.get("url", ""), args.get("max_chars", 8000)))

        tools += [
            Tool(name="open_result_link",
                 description="Open a URL and return a preview of its content.",
                 parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
                 handler=_open_link),
            Tool(name="extract_page_content",
                 description="Fetch a URL and extract full clean readable text content.",
                 parameters={"type": "object", "properties": {
                     "url": {"type": "string"}, "max_chars": {"type": "integer"}},
                     "required": ["url"]},
                 handler=_extract_page),
        ]

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


def _build_provider_config(cfg: SimpleNamespace):
    """Build a typed ProviderConfig for the Copilot SDK."""
    from copilot.types import ProviderConfig
    provider_type = "openai"
    if cfg.provider == "claude":
        provider_type = "anthropic"
    elif cfg.provider == "azure":
        provider_type = "azure"

    base_url = (cfg.base_url or "").rstrip("/")
    if cfg.provider == "azure" and base_url:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    return ProviderConfig(
        type=provider_type,
        base_url=base_url or None,
        api_key=cfg.api_key or None,
    )


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
    Execute one task using the Copilot SDK.

    Compatible with both SDK versions:
      - github-copilot-sdk 0.2.0  → create_session(**kwargs), send_and_wait(str)
      - agent-framework-github-copilot 1.0.0b+ → create_session(SessionConfig), send_and_wait(MessageOptions)

    Any exception propagates to the caller which falls back to httpx.
    """
    from copilot import CopilotClient, PermissionHandler
    from copilot.types import (
        SessionHooks, ProviderConfig, InfiniteSessionConfig,
        SystemMessageReplaceConfig,
        PreToolUseHookInput, PreToolUseHookOutput,
        PostToolUseHookInput, PostToolUseHookOutput,
        ErrorOccurredHookInput, ErrorOccurredHookOutput,
    )
    import inspect

    tool_usage_log: list[str] = []

    # ── Hooks ─────────────────────────────────────────────────────────────────

    async def on_pre_tool_use(inp: PreToolUseHookInput, ctx: dict) -> PreToolUseHookOutput:
        tool_name = inp.get("toolName", "") if isinstance(inp, dict) else getattr(inp, "toolName", "")
        if tool_name in _BLOCKED_BUILTIN_TOOLS or (allowed_tool_names and tool_name not in allowed_tool_names):
            logger.info(f"[WorkflowRunner] Blocking tool: {tool_name}")
            tool_usage_log.append(f"⛔ blocked: {tool_name}")
            return PreToolUseHookOutput(permissionDecision="deny")
        return PreToolUseHookOutput(permissionDecision="allow")

    async def on_post_tool_use(inp: PostToolUseHookInput, ctx: dict) -> PostToolUseHookOutput | None:
        tool_name = inp.get("toolName", "?") if isinstance(inp, dict) else getattr(inp, "toolName", "?")
        tool_usage_log.append(f"🔧 {tool_name}()")
        return None

    async def on_error_occurred(inp: ErrorOccurredHookInput, ctx: dict) -> ErrorOccurredHookOutput | None:
        err = inp.get("error", str(inp)) if isinstance(inp, dict) else getattr(inp, "error", str(inp))
        logger.warning(f"[WorkflowRunner] SDK error: {err}")
        tool_usage_log.append(f"⚠ error: {str(err)[:120]}")
        return None

    hooks = SessionHooks(
        on_pre_tool_use=on_pre_tool_use,
        on_post_tool_use=on_post_tool_use,
        on_error_occurred=on_error_occurred,
    )

    provider   = _build_provider_config(cfg)
    system_msg = SystemMessageReplaceConfig(mode="replace", content=system_prompt)
    infinite   = InfiniteSessionConfig(enabled=False)

    # ── Detect SDK API variant ────────────────────────────────────────────────
    sig = inspect.signature(CopilotClient.create_session)
    params = list(sig.parameters.keys())
    is_kwargs_api = len(params) > 1 and params[1] == "on_permission_request"
    print(f"[WorkflowRunner] SDK API: {'0.2.x kwargs' if is_kwargs_api else '1.0.x SessionConfig'}", flush=True)

    client = CopilotClient()
    session = None

    try:
        await client.start()

        if is_kwargs_api:
            # ── SDK 0.2.x ─────────────────────────────────────────────────────
            session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=cfg.model_name or "gpt-4o",
                system_message=system_msg,
                tools=sdk_tools,
                provider=provider,
                hooks=hooks,
                infinite_sessions=infinite,
            )
            event = await session.send_and_wait(user_message, timeout=120.0)
        else:
            # ── SDK 1.0.x ─────────────────────────────────────────────────────
            from copilot.types import SessionConfig, MessageOptions
            session_cfg = SessionConfig(
                model=cfg.model_name or "gpt-4o",
                system_message=system_msg,
                on_permission_request=PermissionHandler.approve_all,
                provider=provider,
                tools=sdk_tools,
                hooks=hooks,
                infinite_sessions=infinite,
            )
            session = await client.create_session(session_cfg)
            event = await session.send_and_wait(
                MessageOptions(prompt=user_message),
                timeout=120.0,
            )

        if event is None:
            final_text = "[No response — session timed out]"
        else:
            final_text = getattr(event.data, "content", None) or "[No response]"

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
        "final_text": final_text,
        "structured_output": {},
        "tool_usage": tool_usage_log,
        "logs": tool_usage_log,
        "metadata": {
            "model":      cfg.model_name,
            "provider":   cfg.provider,
            "engine":     "copilot-sdk",
            "agent_name": task.agent.name if task.agent else None,
            "task_id":    task.id,
            "task_name":  task.name,
        },
    }


# ── Fallback: direct httpx loop ───────────────────────────────────────────────

async def _execute_task_fallback(
    task: models.Task,
    cfg: SimpleNamespace,
    system_prompt: str,
    user_message: str,
    db=None,
) -> dict:
    from app.routers.task_playground import _build_fs_tools, _run_agent_loop

    tools = []
    root_path = None

    if task.folder_path:
        root_path = Path(task.folder_path).resolve()
        if root_path.exists() and root_path.is_dir() and task.tool_usage_mode != "none":
            perms = ["read_files", "browse_folders"]
            if task.tool_usage_mode == "allowed":
                perms += ["write_files"]
            tools = _build_fs_tools(root_path, perms)
        else:
            root_path = None

    if root_path is None:
        import tempfile
        root_path = Path(tempfile.gettempdir()).resolve()

    # Add web tools if agent has permission
    if db and task.agent_id:
        from app.sandbox.permissions import PermissionChecker
        from app.web_tools import build_web_tools
        checker = PermissionChecker.from_db(db, task.agent_id)
        if checker.allowed("shell", "execute_commands"):
            from app.shell_tools import build_shell_tools
            shell_perms = {
                "execute_commands": True,
                "allow_read_only_commands": checker.allowed("shell", "allow_readonly"),
                "allow_write_impacting_commands": checker.allowed("shell", "allow_write_impact"),
            }
            tools += build_shell_tools(shell_perms)
        if checker.allowed("web_search", "perform_search"):
            web_perms = {"perform_search": True}
            if checker.allowed("web_search", "open_links"):
                web_perms["open_result_links"] = True
            tools += build_web_tools(web_perms)

    patched_cfg = SimpleNamespace(
        base_url=(cfg.base_url or "").replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal").rstrip("/") or "https://api.openai.com/v1",
        api_key=cfg.api_key,
        model_name=cfg.model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )

    result, steps = await _run_agent_loop(patched_cfg, system_prompt, user_message, root_path, tools)

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

    # Add tool context hint — includes web search if agent has permission
    allowed = _allowed_tool_names(task, db)
    if allowed:
        tool_hint = (
            f"\n\nYou have access to these tools: {', '.join(sorted(allowed))}."
            f"\nIMPORTANT: When the task asks you to create, write, or save a file, "
            f"you MUST call the write_file tool — do not just describe the file contents in text."
            f"\nWhen the task requires current information from the internet, use perform_web_search, search_news, or search_domain as appropriate."
            f"\nDo not attempt shell, container, or system-level operations."
        )
        agent_prompt = agent_prompt + tool_hint

    system_prompt, _ = compose_agent_prompt(domain_prompt, agent_prompt)
    user_message = _build_user_message(task, prior_output)

    print(f"[WorkflowRunner] task={task.name} model={cfg.model_name} provider={cfg.provider} prior={'yes' if prior_output else 'no'}", flush=True)

    # ── Try Copilot SDK first (all providers) ─────────────────────────────────
    # The SDK supports BYOK via ProviderConfig(type="openai", base_url=..., api_key=...).
    # If the SDK call fails for any reason, we fall through to the direct httpx loop.
    sdk_tools = _build_sdk_tools(task, db=db)
    print(f"[WorkflowRunner] SDK path → tools={[t.name for t in sdk_tools]}", flush=True)

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
        print(f"[WorkflowRunner] ⚠ SDK error: {e} — using httpx fallback", flush=True)

    # ── httpx fallback ────────────────────────────────────────────────────────
    try:
        return asyncio.run(_execute_task_fallback(task, cfg, system_prompt, user_message, db=db))
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


# ── Sandbox entry point ───────────────────────────────────────────────────────

def run_task_in_sandbox(
    task: models.Task,
    db,
    run_id: str,
    prior_output: Optional[str] = None,
) -> dict:
    """
    Execute one task inside an isolated Docker sandbox container.

    Differences from run_task_in_workflow:
    - Permissions are loaded fresh from DB (not inferred from tool_usage_mode)
    - Task payload is written to /workspace/.task_input.json
    - Agent runner executes inside the container
    - Output is read from /workspace/.task_output.json

    Falls back to run_task_in_workflow if Docker is unavailable.
    """
    from app.sandbox.manager import SandboxManager
    from app.sandbox.permissions import PermissionChecker

    cfg = _resolve_cfg(task, db)

    domain_prompt = task.agent.domain.domain_prompt if (task.agent and task.agent.domain) else None
    agent_prompt  = task.agent.system_prompt if task.agent else ""
    if task.llm_system_behavior:
        agent_prompt = (agent_prompt + "\n\n" + task.llm_system_behavior).strip()

    system_prompt, _ = compose_agent_prompt(domain_prompt, agent_prompt)
    user_message = _build_user_message(task, prior_output)

    # Load permissions from DB — never from request
    checker = (
        PermissionChecker.from_db(db, task.agent_id)
        if task.agent_id
        else PermissionChecker.deny_all(0)
    )

    # Build granted_permissions dict for the agent runner
    granted_permissions = {k: list(v) for k, v in checker.grants.items()}

    # Determine which tools the agent may attempt (based on task config + permissions)
    available_tools: list[str] = []
    if task.tool_usage_mode != "none":
        available_tools = ["list_directory", "read_file"]
        if task.tool_usage_mode == "allowed":
            available_tools += ["write_file"]

    # Add shell tools if agent has execute_commands permission
    if checker.allowed("shell", "execute_commands"):
        available_tools.append("shell_exec")

    # Add web search if agent has perform_search permission
    if checker.allowed("web_search", "perform_search"):
        available_tools.extend(["perform_web_search", "search_news", "search_domain"])
    if checker.allowed("web_search", "open_links"):
        available_tools.extend(["open_result_link", "extract_page_content"])

    # ── Workspace resolution — decoupled from task.folder_path ──────────────
    # Each run always gets its own isolated workspace under:
    #   /workspace/runs/{run_id}/
    # This removes the dependency on task.folder_path for execution.
    #
    # If task.folder_path is set, it is used as a READ-ONLY source:
    #   - Its contents are copied into the run workspace before execution
    #   - The agent reads/writes in the run workspace, not the source folder
    #   - This preserves the source folder and isolates each run
    #
    # If task.folder_path is not set, the run workspace starts empty.
    # The agent creates all output files there.
    import re, shutil

    safe_name = re.sub(r"[^\w\-]", "_", task.name.lower()).strip("_")[:30]
    run_workspace = Path("/workspace") / "runs" / f"{safe_name}_{run_id}"
    run_workspace.mkdir(parents=True, exist_ok=True)

    # Copy source files into run workspace if task has a folder_path
    if task.folder_path:
        source = Path(task.folder_path)
        if source.exists() and source.is_dir():
            for item in source.iterdir():
                dest = run_workspace / item.name
                if item.is_file() and not dest.exists():
                    shutil.copy2(item, dest)
            print(f"[WorkflowRunner] Copied source files from {source} → {run_workspace}", flush=True)

    effective_folder = str(run_workspace)
    print(f"[WorkflowRunner] Run workspace: {effective_folder}", flush=True)

    task_payload = {
        "system_prompt":       system_prompt,
        "user_message":        user_message,
        "llm_base_url":        (cfg.base_url or "https://api.openai.com/v1").rstrip("/"),
        "llm_api_key_enc":     _encrypt_for_sandbox(cfg.api_key),
        "llm_model":           cfg.model_name or "gpt-4o",
        "llm_provider":        cfg.provider,
        "llm_temperature":     cfg.temperature,
        "llm_max_tokens":      cfg.max_tokens,
        "granted_permissions": granted_permissions,
        "available_tools":     available_tools,
        "task_id":             task.id,
        "task_name":           task.name,
        "run_id":              run_id,
        # Resolved workspace folder — container mounts this as /workspace
        "task_folder_path":    effective_folder,
    }

    # Need network if LLM is a remote endpoint (not localhost)
    base_url = (cfg.base_url or "").lower()
    needs_network = (
        checker.allowed("web_search", "perform_search")
        or not any(h in base_url for h in ("localhost", "127.0.0.1", "host.docker.internal"))
    )

    sandbox = SandboxManager(run_id=f"{run_id}-task{task.id}")
    result  = sandbox.run(task_payload, network_access=needs_network)

    # Normalise result shape to match run_task_in_workflow output
    return {
        "success":          result.get("success", False),
        "final_text":       result.get("final_text", result.get("error", "")),
        "structured_output": {},
        "tool_usage":       result.get("tool_usage", []),
        "logs":             result.get("tool_usage", []),
        "metadata": {
            "model":      cfg.model_name,
            "provider":   cfg.provider,
            "agent_name": task.agent.name if task.agent else None,
            "task_id":    task.id,
            "task_name":  task.name,
            "engine":     "sandbox",
            "run_id":     run_id,
        },
        "error": result.get("error"),
    }
