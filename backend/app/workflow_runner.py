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

    # Add web tools if the agent has perform_search permission in DB
    if db and task.agent_id:
        from app.sandbox.permissions import PermissionChecker
        checker = PermissionChecker.from_db(db, task.agent_id)
        if checker.allowed("web_search", "perform_search"):
            allowed |= _WEB_TOOLS
        if checker.allowed("web_search", "open_links"):
            allowed |= {"open_result_link", "extract_page_content"}

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
        ))

    # ── Web search tools (SDK placeholder — active when Copilot native key used) ──
    # Check if agent has web search permission
    if task.agent_id:
        try:
            # Note: _build_sdk_tools is called without db in some paths,
            # so we check the task's agent tool_access relationship directly.
            for access in (task.agent.tool_access if task.agent else []):
                if hasattr(access, "tool") and access.tool and access.tool.key == "web":
                    granted = set(access.granted_permissions or [])
                    if "perform_search" in granted or "open_result_links" in granted:
                        from app.web_tools import (
                            perform_web_search,
                            search_news,
                            search_domain,
                            open_result_link,
                            extract_page_content,
                        )

                        async def handle_web_search(inv):
                            args = inv.get("arguments", {})
                            result = perform_web_search(
                                args.get("query", ""),
                                args.get("max_results", 8),
                            )
                            return {"textResultForLlm": result, "resultType": "success"}

                        async def handle_search_news(inv):
                            args = inv.get("arguments", {})
                            result = search_news(
                                args.get("query", ""),
                                args.get("max_results", 8),
                            )
                            return {"textResultForLlm": result, "resultType": "success"}

                        async def handle_search_domain(inv):
                            args = inv.get("arguments", {})
                            result = search_domain(
                                args.get("query", ""),
                                args.get("domain", ""),
                                args.get("max_results", 6),
                            )
                            return {"textResultForLlm": result, "resultType": "success"}

                        tools.append(Tool(
                            name="perform_web_search",
                            description="Search the web using Tavily. Returns titles, URLs, snippets, and a direct answer.",
                            parameters={
                                "type": "object",
                                "properties": {
                                    "query":       {"type": "string",  "description": "Search query"},
                                    "max_results": {"type": "integer", "description": "Max results (default 8)"},
                                },
                                "required": ["query"],
                            },
                            handler=handle_web_search,
                        ))
                        tools.append(Tool(
                            name="search_news",
                            description="Search for recent news articles using Tavily.",
                            parameters={
                                "type": "object",
                                "properties": {
                                    "query":       {"type": "string",  "description": "News search query"},
                                    "max_results": {"type": "integer", "description": "Max results (default 8)"},
                                },
                                "required": ["query"],
                            },
                            handler=handle_search_news,
                        ))
                        tools.append(Tool(
                            name="search_domain",
                            description="Search within a specific website domain using Tavily.",
                            parameters={
                                "type": "object",
                                "properties": {
                                    "query":       {"type": "string",  "description": "Search query"},
                                    "domain":      {"type": "string",  "description": "Domain to restrict search to"},
                                    "max_results": {"type": "integer", "description": "Max results (default 6)"},
                                },
                                "required": ["query", "domain"],
                            },
                            handler=handle_search_domain,
                        ))
                        if "open_result_links" in granted:
                            async def handle_open_result_link(inv):
                                args = inv.get("arguments", {})
                                result = open_result_link(args.get("url", ""))
                                return {"textResultForLlm": result, "resultType": "success"}

                            async def handle_extract_page_content(inv):
                                args = inv.get("arguments", {})
                                result = extract_page_content(
                                    args.get("url", ""),
                                    args.get("max_chars", 8000),
                                )
                                return {"textResultForLlm": result, "resultType": "success"}

                            tools.append(Tool(
                                name="open_result_link",
                                description="Open a URL and return a preview of its content.",
                                parameters={
                                    "type": "object",
                                    "properties": {
                                        "url": {"type": "string", "description": "Full URL to open"},
                                    },
                                    "required": ["url"],
                                },
                                handler=handle_open_result_link,
                            ))
                            tools.append(Tool(
                                name="extract_page_content",
                                description="Fetch a URL and extract full clean readable text content.",
                                parameters={
                                    "type": "object",
                                    "properties": {
                                        "url": {"type": "string", "description": "Full URL to fetch"},
                                        "max_chars": {"type": "integer", "description": "Max characters to return (default 8000)"},
                                    },
                                    "required": ["url"],
                                },
                                handler=handle_extract_page_content,
                            ))
                        break
        except Exception:
            pass  # permissions not loadable — skip web tools

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

    ── PLACEHOLDER ──────────────────────────────────────────────────────────────
    This function is kept as a placeholder for when a native GitHub Copilot
    API key is available. The SDK's custom Tool objects with handlers work
    correctly with GitHub Copilot's own model endpoints.

    Currently NOT called for BYOK providers (OpenAI, Ollama, Claude, etc.)
    because the SDK does not forward custom tool schemas to external models.
    run_task_in_workflow() routes BYOK providers to _execute_task_fallback()
    (direct httpx) instead.

    To activate: remove the BYOK check in run_task_in_workflow() and set a
    native GitHub Copilot API key in LLM Config.
    ─────────────────────────────────────────────────────────────────────────────
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
        # Guard: SDK may pass a string instead of dict in error states
        if not isinstance(input_data, dict):
            return {"permissionDecision": "allow"}
        tool_name = input_data.get("toolName", "")
        if tool_name in _BLOCKED_BUILTIN_TOOLS or (allowed_tool_names and tool_name not in allowed_tool_names):
            logger.info(f"[WorkflowRunner] Blocking tool: {tool_name}")
            tool_usage_log.append(f"⛔ blocked: {tool_name}")
            return {"permissionDecision": "deny"}
        return {"permissionDecision": "allow", "modifiedArgs": input_data.get("toolArgs")}

    async def on_post_tool_use(input_data, invocation):
        if not isinstance(input_data, dict):
            return {}
        tool_name = input_data.get("toolName", "")
        tool_usage_log.append(f"🔧 {tool_name}()")
        return {}

    async def on_error_occurred(input_data, invocation):
        if not isinstance(input_data, dict):
            tool_usage_log.append(f"⚠ SDK error: {str(input_data)[:120]}")
            return {"errorHandling": "skip"}
        error = input_data.get("error", "")
        ctx = input_data.get("errorContext", "")
        logger.warning(f"[WorkflowRunner] SDK error in {ctx}: {error}")
        tool_usage_log.append(f"⚠ error skipped: {ctx} — {str(error)[:120]}")
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

    # ── Routing: BYOK vs GitHub Copilot native ────────────────────────────────
    # The Copilot SDK's custom Tool objects with handlers are designed for
    # GitHub Copilot's own service. For BYOK providers (OpenAI, Ollama, Claude,
    # custom endpoints), the SDK does NOT forward tool schemas to the external
    # model — so tool calls never happen.
    #
    # PLACEHOLDER: When a native GitHub Copilot API key is available, remove
    # the BYOK check below and let all providers use execute_task_with_copilot().
    # The SDK path (execute_task_with_copilot) is kept intact as a placeholder
    # for that future use case.
    #
    # For now: BYOK providers go straight to _execute_task_fallback (direct httpx).
    # ─────────────────────────────────────────────────────────────────────────────
    base_url_lower = (cfg.base_url or "").lower()
    is_byok = bool(cfg.base_url and
                   "copilot" not in base_url_lower and
                   "github" not in base_url_lower)

    if is_byok:
        print(f"[WorkflowRunner] BYOK provider ({cfg.provider}) → direct httpx (SDK placeholder active)", flush=True)
        try:
            return asyncio.run(_execute_task_fallback(task, cfg, system_prompt, user_message, db=db))
        except Exception as e:
            return {
                "success": False, "final_text": str(e), "structured_output": {},
                "tool_usage": [], "logs": [f"Error: {e}"],
                "metadata": {"task_id": task.id, "task_name": task.name}, "error": str(e),
            }

    # ── GitHub Copilot native path (SDK with Tool handlers) ───────────────────
    sdk_tools = _build_sdk_tools(task)
    print(f"[WorkflowRunner] Copilot native → SDK tools={[t.name for t in sdk_tools]}", flush=True)

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
