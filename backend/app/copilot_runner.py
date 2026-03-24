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


def _build_session_options(config: models.LLMConfig, skill: str) -> dict:
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
    timeout: float = 60.0,
) -> str:
    """
    Create a GitHub Copilot SDK session using BYOK provider config,
    send the user prompt, wait for the response, and return the text.
    """
    try:
        from copilot import CopilotClient
    except ImportError:
        return "[Error] github-copilot-sdk not installed. Run: pip install github-copilot-sdk"

    # Decrypt API key — it's stored encrypted in DB
    if config.api_key:
        config.api_key = decrypt(config.api_key)
    session_opts = _build_session_options(config, skill)
    client = CopilotClient()
    session = None

    try:
        await client.start()
        session = await client.create_session(session_opts)
        event = await session.send_and_wait({"prompt": user_prompt}, timeout=timeout)
        if event is None:
            return "[No response received]"
        return getattr(event.data, "content", "") or "[Empty response]"

    except asyncio.TimeoutError:
        return f"[Timeout] No response from Copilot SDK after {timeout}s"
    except Exception as e:
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
