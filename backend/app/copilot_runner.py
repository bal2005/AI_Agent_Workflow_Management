"""
GitHub Copilot SDK runner — playground single-turn execution.

Uses the SDK installed in the backend container (agent-framework-github-copilot).
All types live in copilot.session for this version.
Falls back to direct httpx if the SDK call fails.
"""

import asyncio
import logging
from typing import Optional
from app import models
from app.crypto import decrypt

logger = logging.getLogger(__name__)


async def run_via_copilot_sdk(
    config: models.LLMConfig,
    skill: str,
    user_prompt: str,
    allow_tools: bool = False,
    timeout: float = 60.0,
) -> str:
    """
    Run a single-turn playground request via the Copilot SDK.
    Falls back to direct httpx on any SDK failure.
    """
    # Decrypt API key
    api_key = decrypt(config.api_key) if config.api_key else ""

    try:
        from copilot import CopilotClient
        from copilot.session import (
            PermissionHandler, ProviderConfig,
            SystemMessageReplaceConfig, InfiniteSessionConfig,
        )

        provider_type = "openai"
        if config.provider == "claude":
            provider_type = "anthropic"
        elif config.provider == "azure":
            provider_type = "azure"

        base_url = (config.base_url or "").rstrip("/") or None
        if config.provider == "azure" and base_url:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

        provider = ProviderConfig(
            type=provider_type,
            base_url=base_url,
            api_key=api_key or None,
        )

        system_msg = SystemMessageReplaceConfig(mode="replace", content=skill)
        infinite   = InfiniteSessionConfig(enabled=False)

        client  = CopilotClient()
        session = None

        try:
            await client.start()
            session = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model=config.model_name or "gpt-4o",
                system_message=system_msg,
                provider=provider,
                infinite_sessions=infinite,
            )
            event = await session.send_and_wait(user_prompt, timeout=timeout)
            if event is None:
                return "[No response received]"
            result = getattr(event.data, "content", None) or "[Empty response]"
            logger.info("[Copilot SDK] ✓ playground success")
            return result

        except asyncio.TimeoutError:
            return f"[Timeout] No response after {timeout}s"
        except Exception as e:
            logger.warning(f"[Copilot SDK] error: {e} — falling back to httpx")
            return await _fallback_direct_call(config, api_key, skill, user_prompt)
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

    except ImportError as e:
        logger.warning(f"[Copilot SDK] import error: {e} — using httpx")
        return await _fallback_direct_call(config, api_key, skill, user_prompt)


async def _fallback_direct_call(
    config: models.LLMConfig,
    api_key: str,
    skill: str,
    user_prompt: str,
) -> str:
    """Direct httpx fallback — no SDK dependency."""
    import httpx

    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    headers  = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict = {
        "model": config.model_name or "gpt-4o",
        "messages": [
            {"role": "system", "content": skill},
            {"role": "user",   "content": user_prompt},
        ],
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    if config.top_p is not None:
        body["top_p"] = config.top_p
    if config.max_tokens is not None:
        body["max_tokens"] = config.max_tokens

    try:
        resp = httpx.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return f"[Connection error] Could not reach {base_url}"
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        return f"[API error {e.response.status_code}] {detail}"
    except Exception as e:
        return f"[Fallback error] {e}"
