"""
Agent Creation Test — GitHub Copilot SDK (BYOK) + Groq
=======================================================
Tests the GitHub Copilot SDK from https://github.com/github/copilot-sdk/tree/main/python
using the BYOK custom provider config to route through Groq (OpenAI-compatible).

The SDK wraps the prompt into a Copilot agent session — same pattern used by
the Agent Studio playground endpoint via app/copilot_runner.py.

Tests:
  1. Basic session — single turn via Copilot SDK BYOK
  2. Streaming session — delta events
  3. Multi-turn session — thread with memory
  4. Custom tool — @define_tool decorator
  5. Stock Market Agent — loads skill from DB, runs via SDK
  6. Permission handler — custom approve/deny logic
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ── Pull active LLM config from DB ──────────────────────────────────────────
from app.database import SessionLocal
from app import models

def get_active_config():
    db = SessionLocal()
    try:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()
        if not cfg:
            print("❌  No active LLM config. Set one active in the LLM Config page.")
            sys.exit(1)
        return cfg
    finally:
        db.close()

cfg = get_active_config()
print(f"✅  Active config: [{cfg.provider}] {cfg.model_name} @ {cfg.base_url}\n")

# Decrypt API key (stored encrypted in DB)
from app.crypto import decrypt
if cfg.api_key:
    cfg.api_key = decrypt(cfg.api_key)

# ── Build BYOK provider dict (mirrors copilot_runner._build_provider) ────────
def build_provider(config: models.LLMConfig) -> dict:
    ptype = "openai"
    if config.provider == "claude":
        ptype = "anthropic"
    elif config.provider == "azure":
        ptype = "azure"

    p = {"type": ptype}
    if config.base_url:
        base = config.base_url.rstrip("/")
        if config.provider == "azure":
            from urllib.parse import urlparse
            parsed = urlparse(base)
            base = f"{parsed.scheme}://{parsed.netloc}"
        p["base_url"] = base
    if config.api_key:
        p["api_key"] = config.api_key
    if config.provider == "azure":
        p["azure"] = {"api_version": "2024-10-21"}
    return p

PROVIDER = build_provider(cfg)
MODEL    = cfg.model_name or "gpt-4o"
DIVIDER  = "─" * 60

# ── Copilot SDK imports ───────────────────────────────────────────────────────
try:
    from copilot import CopilotClient, PermissionHandler, PermissionRequest, PermissionRequestResult
    from copilot import define_tool
    from pydantic import BaseModel, Field
except ImportError as e:
    print(f"❌  {e}\nRun: pip install github-copilot-sdk")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# Helper — run a single-turn session and return the response text
# Uses send_and_wait for clean blocking semantics
# ════════════════════════════════════════════════════════════════════════════

async def sdk_run(skill: str, user_prompt: str, extra_opts: dict = None, timeout: float = 60) -> str:
    opts = {
        "model": MODEL,
        "system_message": {"mode": "replace", "content": skill},
        "on_permission_request": PermissionHandler.approve_all,
        "provider": PROVIDER,
        "available_tools": [],   # disable SDK built-in tools (web_fetch etc.) for BYOK compat
        **(extra_opts or {}),
    }

    client = CopilotClient()
    session = None
    try:
        await client.start()
        session = await client.create_session(opts)
        event = await session.send_and_wait({"prompt": user_prompt}, timeout=timeout)
        if event is None:
            return "[No response received]"
        return getattr(event.data, "content", "") or "[Empty response]"
    except Exception as e:
        return f"[SDK error] {type(e).__name__}: {e}"
    finally:
        if session:
            try: await session.disconnect()
            except Exception: pass
        try: await client.stop()
        except Exception: pass


# ════════════════════════════════════════════════════════════════════════════
# TEST 1 — Basic single-turn session via Copilot SDK BYOK
# ════════════════════════════════════════════════════════════════════════════

async def test_basic():
    print(DIVIDER)
    print("TEST 1 — Basic Single-Turn Session (Copilot SDK BYOK)")
    print(DIVIDER)

    result = await sdk_run(
        skill="You are a concise assistant. Answer in one sentence.",
        user_prompt="What is the GitHub Copilot SDK used for?",
    )
    print(f"Agent: {result}\n")


# ════════════════════════════════════════════════════════════════════════════
# TEST 2 — Streaming session (assistant.message_delta events)
# ════════════════════════════════════════════════════════════════════════════

async def test_streaming():
    print(DIVIDER)
    print("TEST 2 — Streaming Session (delta events)")
    print(DIVIDER)

    chunks: list[str] = []
    done = asyncio.Event()

    def on_event(event):
        etype = event.type.value if hasattr(event.type, "value") else str(event.type)
        if etype == "assistant.message_delta":
            chunk = getattr(event.data, "delta_content", "") or ""
            chunks.append(chunk)
            print(chunk, end="", flush=True)
        elif etype in ("session.idle", "assistant.message"):
            done.set()

    opts = {
        "model": MODEL,
        "system_message": {"mode": "replace", "content": "You are a financial analyst. Be concise."},
        "on_permission_request": PermissionHandler.approve_all,
        "provider": PROVIDER,
        "streaming": True,
        "available_tools": [],
    }

    client = CopilotClient()
    session = None
    try:
        await client.start()
        session = await client.create_session(opts)
        session.on(on_event)
        print("Agent (streaming): ", end="", flush=True)
        await session.send({"prompt": "In 2 sentences, why do Indian IT stocks track the USD/INR rate?"})
        await asyncio.wait_for(done.wait(), timeout=60)
        print("\n")
    except Exception as e:
        print(f"\n[SDK error] {type(e).__name__}: {e}\n")
    finally:
        if session:
            try: await session.disconnect()
            except Exception: pass
        try: await client.stop()
        except Exception: pass


# ════════════════════════════════════════════════════════════════════════════
# TEST 3 — Multi-turn session (session reuse / thread memory)
# ════════════════════════════════════════════════════════════════════════════

async def test_multi_turn():
    print(DIVIDER)
    print("TEST 3 — Multi-Turn Session (memory across turns)")
    print(DIVIDER)

    turns = [
        "My portfolio has TCS, Infosys, and Wipro.",
        "Which of those is typically the most volatile?",
        "What stocks did I mention earlier?",
    ]

    opts = {
        "model": MODEL,
        "system_message": {"mode": "replace", "content": "You are a helpful stock assistant. Keep answers short."},
        "on_permission_request": PermissionHandler.approve_all,
        "provider": PROVIDER,
        "available_tools": [],
    }

    client = CopilotClient()
    session = None
    try:
        await client.start()
        session = await client.create_session(opts)

        for i, prompt in enumerate(turns, 1):
            try:
                event = await session.send_and_wait({"prompt": prompt}, timeout=60)
                content = getattr(event.data, "content", "") if event else "[No response]"
                print(f"Turn {i} — User: {prompt}")
                print(f"Turn {i} — Agent: {content}\n")
            except Exception as e:
                print(f"Turn {i} — Error: {type(e).__name__}: {e}\n")
    finally:
        if session:
            try: await session.disconnect()
            except Exception: pass
        try: await client.stop()
        except Exception: pass


# ════════════════════════════════════════════════════════════════════════════
# TEST 4 — Custom tool via @define_tool
# ════════════════════════════════════════════════════════════════════════════

class StockParams(BaseModel):
    ticker: str = Field(description="Stock ticker e.g. INFY, TCS, WIPRO")

@define_tool(description="Get the current mock price for an Indian stock ticker")
async def get_stock_price(params: StockParams) -> str:
    prices = {"INFY": "₹1,842 (+1.2%)", "TCS": "₹3,920 (+0.8%)", "WIPRO": "₹462 (-0.3%)"}
    return prices.get(params.ticker.upper(), f"₹1,000 (mock) for {params.ticker}")

async def test_custom_tool():
    print(DIVIDER)
    print("TEST 4 — Custom Tool (@define_tool)")
    print(DIVIDER)

    result = await sdk_run(
        skill="You are a stock assistant. Use get_stock_price to answer price queries.",
        user_prompt="What is the current price of INFY and TCS?",
        extra_opts={"tools": [get_stock_price]},
    )
    print(f"Agent: {result}\n")


# ════════════════════════════════════════════════════════════════════════════
# TEST 5 — Stock Market Agent from DB (skill loaded from NeonDB)
# ════════════════════════════════════════════════════════════════════════════

async def test_stock_market_agent():
    print(DIVIDER)
    print("TEST 5 — Stock Market Agent (skill from DB via Copilot SDK)")
    print(DIVIDER)

    db = SessionLocal()
    try:
        agent_record = db.query(models.Agent).filter(
            models.Agent.name == "Stock Market Analysis Agent"
        ).first()
        if not agent_record:
            print("⚠  Agent not found in DB, using fallback skill.")
            skill = "You are a stock market expert. Provide concise analysis."
        else:
            skill = agent_record.system_prompt
            print(f"✅  Loaded skill from DB agent: '{agent_record.name}'")
    finally:
        db.close()

    queries = [
        "Give a brief overview of Indian IT sector performance today.",
        "Which large-cap Indian tech stock has the best fundamentals?",
    ]

    opts = {
        "model": MODEL,
        "system_message": {"mode": "replace", "content": skill},
        "on_permission_request": PermissionHandler.approve_all,
        "provider": PROVIDER,
        "available_tools": [],
    }

    client = CopilotClient()
    session = None
    try:
        await client.start()
        session = await client.create_session(opts)

        for i, q in enumerate(queries, 1):
            try:
                event = await session.send_and_wait({"prompt": q}, timeout=60)
                content = getattr(event.data, "content", "") if event else "[No response]"
                print(f"\nUser (turn {i}): {q}")
                print(f"Agent (turn {i}): {content}")
            except Exception as e:
                print(f"\nTurn {i} — Error: {type(e).__name__}: {e}")
    finally:
        if session:
            try: await session.disconnect()
            except Exception: pass
        try: await client.stop()
        except Exception: pass
    print()


# ════════════════════════════════════════════════════════════════════════════
# TEST 6 — Custom permission handler (deny shell, approve rest)
# ════════════════════════════════════════════════════════════════════════════

async def test_permission_handler():
    print(DIVIDER)
    print("TEST 6 — Custom Permission Handler")
    print(DIVIDER)

    def selective_permission(request: PermissionRequest, invocation: dict) -> PermissionRequestResult:
        kind = request.kind.value if hasattr(request.kind, "value") else str(request.kind)
        if kind == "shell":
            print(f"  [Permission] DENIED shell command")
            return PermissionRequestResult(kind="denied-interactively-by-user")
        print(f"  [Permission] APPROVED {kind}")
        return PermissionRequestResult(kind="approved")

    result = await sdk_run(
        skill="You are a helpful assistant.",
        user_prompt="What is 2 + 2? Answer in one word.",
        extra_opts={"on_permission_request": selective_permission},
    )
    print(f"Agent: {result}\n")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

async def main():
    print("\n🚀  GitHub Copilot SDK Test Suite")
    print(f"    Provider : {cfg.provider} ({PROVIDER['type']})")
    print(f"    Model    : {MODEL}")
    print(f"    Endpoint : {cfg.base_url}\n")

    await test_basic()
    await test_streaming()
    await test_multi_turn()
    await test_custom_tool()
    await test_stock_market_agent()
    await test_permission_handler()

    print(DIVIDER)
    print("✅  All tests completed.")
    print(DIVIDER)


if __name__ == "__main__":
    asyncio.run(main())
