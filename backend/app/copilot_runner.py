"""
GitHub Copilot SDK runner — wraps CopilotClient with BYOK provider config.

Maps our LLMConfig (provider, base_url, api_key, model_name, params) to the
Copilot SDK's SessionConfig `provider` dict as documented at:
https://github.com/github/copilot-sdk/tree/main/python

Provider mapping:
  openai  / custom / gemini  → type="openai"
  claude                     → type="anthropic"
  ollama                     → type="openai" + local base_url, no api_key
  azure                      → type="azure"
"""

import asyncio
from typing import Optional
from app import models
from app.crypto import decrypt


def _build_provider(config: models.LLMConfig) -> dict:
    """Convert our LLMConfig into a Copilot SDK ProviderConfig dict."""
    provider_type = "openai"
    if config.provider == "claude":
        provider_type = "anthropic"
    elif config.provider == "azure":
        provider_type = "azure"

    p: dict = {
        "type": provider_type,
        "base_url": (config.base_url or "").rstrip("/") or None,
    }

    if config.api_key:
        p["api_key"] = config.api_key

    if config.provider == "azure":
        p["azure"] = {"api_version": "2024-10-21"}
        # Azure base_url must be just the host — strip any path
        if p["base_url"]:
            from urllib.parse import urlparse
            parsed = urlparse(p["base_url"])
            p["base_url"] = f"{parsed.scheme}://{parsed.netloc}"

    # Remove None base_url so SDK uses its default
    if not p.get("base_url"):
        p.pop("base_url", None)

    return p


def _build_session_options(config: models.LLMConfig, skill: str, allow_tools: bool = False) -> dict:
    """Build the full session options dict for client.create_session()."""
    from copilot import PermissionHandler

    opts: dict = {
        "model": config.model_name or "gpt-4o",
        "system_message": {"mode": "replace", "content": skill},
        "on_permission_request": PermissionHandler.approve_all,
        "provider": _build_provider(config),
        "available_tools": [],   # disable SDK built-in tools for BYOK provider compat
    }

    # Optional inference params passed as extra options where SDK supports them
    extra: dict = {}
    if config.temperature is not None:
        extra["temperature"] = config.temperature
    if config.top_p is not None:
        extra["top_p"] = config.top_p
    if config.max_tokens is not None:
        extra["max_tokens"] = config.max_tokens

    if extra:
        opts["extra_body"] = extra

    return opts


async def run_via_copilot_sdk(
    config: models.LLMConfig,
    skill: str,
    user_prompt: str,
    allow_tools: bool = False,
    timeout: float = 60.0,
) -> str:
    """
    Create a GitHub Copilot SDK session using BYOK provider config,
    send the user prompt, wait for the response, and return the text.
    
    allow_tools: if False, passes tool_choice="none" to block tool calls at API level.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from copilot import CopilotClient
    except ImportError:
        return "[Error] github-copilot-sdk not installed. Run: pip install github-copilot-sdk"

    # Decrypt API key — it's stored encrypted in DB
    if config.api_key:
        config.api_key = decrypt(config.api_key)
    
    # If not allowing tools, append instruction to skill
    final_skill = skill
    if not allow_tools:
        final_skill = skill + "\n\n[IMPORTANT: You do not have access to any tools. Answer using only your knowledge. If you cannot answer, say 'I don't know'.]"
    
    session_opts = _build_session_options(config, final_skill, allow_tools=allow_tools)
    client = CopilotClient()
    session = None

    try:
        logger.info(f"[Copilot SDK] Starting session with model={config.model_name}, allow_tools={allow_tools}")
        await client.start()
        session = await client.create_session(session_opts)
        event = await session.send_and_wait({"prompt": user_prompt}, timeout=timeout)
        if event is None:
            logger.info("[Copilot SDK] No response received")
            return "[No response received]"
        result = getattr(event.data, "content", "") or "[Empty response]"
        logger.info("[Copilot SDK] ✓ Success via SDK")
        return result

    except asyncio.TimeoutError:
        logger.warning(f"[Copilot SDK] Timeout after {timeout}s")
        return f"[Timeout] No response from Copilot SDK after {timeout}s"
    except Exception as e:
        error_str = str(e)
        logger.warning(f"[Copilot SDK] Error: {error_str}")
        # If tool_use_failed error, fall back to direct httpx call
        if "tool_use_failed" in error_str or "Tool choice is none" in error_str:
            logger.info("[Copilot SDK] Falling back to direct httpx call")
            return await _fallback_direct_call(config, skill, user_prompt)
        return f"[Copilot SDK error] {type(e).__name__}: {e}"
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


async def _fallback_direct_call(config: models.LLMConfig, skill: str, user_prompt: str) -> str:
    """Fallback: direct httpx call — no tools, no tool_choice constraint."""
    import httpx
    import logging
    logger = logging.getLogger(__name__)
    
    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {config.api_key or ''}", "Content-Type": "application/json"}
    body: dict = {
        "model": config.model_name or "gpt-4o",
        "messages": [
            {"role": "system", "content": skill},
            {"role": "user", "content": user_prompt},
        ],
        # Do NOT send tool_choice or tools — cleanest way to prevent tool calls
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    if config.top_p is not None:
        body["top_p"] = config.top_p
    if config.max_tokens is not None:
        body["max_tokens"] = config.max_tokens

    try:
        logger.info("[Fallback] Using direct httpx call (no tools)")
        print(f"[FALLBACK REQUEST] url={base_url}/chat/completions model={body['model']} msgs={len(body['messages'])} temperature={body.get('temperature')} max_tokens={body.get('max_tokens')}", flush=True)
        total_chars = sum(len(str(m.get("content") or "")) for m in body["messages"])
        print(f"[FALLBACK REQUEST] total_content_chars={total_chars} roles={[m['role'] for m in body['messages']]}", flush=True)
        resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        logger.info("[Fallback] ✓ Success via direct httpx")
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        logger.error(f"[Fallback] Connection error to {base_url}")
        return f"[Connection error] Could not reach {base_url}"
    except httpx.HTTPStatusError as e:
        logger.error(f"[Fallback] HTTP {e.response.status_code}")
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        print("=" * 60, flush=True)
        print(f"[FALLBACK 400] model={body['model']}", flush=True)
        print(f"[FALLBACK 400] response body: {detail}", flush=True)
        print(f"[FALLBACK 400] message_count={len(body['messages'])} total_chars={total_chars}", flush=True)
        print(f"[FALLBACK 400] temperature={body.get('temperature')} max_tokens={body.get('max_tokens')} top_p={body.get('top_p')}", flush=True)
    except Exception as e:
        logger.error(f"[Fallback] Error: {str(e)}")
        return f"[Fallback error] {str(e)}"
