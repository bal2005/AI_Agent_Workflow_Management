"""
Centralized prompt composition utility.
All execution paths (playground, task, scheduler, dry-run) must use these helpers.
"""
import re
from typing import Optional

MAX_DOMAIN_PROMPT_CHARS = 2000
MAX_AGENT_PROMPT_CHARS = 4000


def normalize(text: Optional[str]) -> str:
    """Strip whitespace and collapse excessive blank lines."""
    if not text:
        return ""
    text = text.strip()
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _sentences(text: str) -> set[str]:
    """Return a set of lowercased non-empty sentences for dedup check."""
    return {s.strip().lower() for s in re.split(r"[.\n]", text) if len(s.strip()) > 20}


def deduplicate_sections(primary: str, secondary: str) -> str:
    """
    Remove sentences from `secondary` that already appear in `primary`.
    Keeps secondary concise when agent prompt repeats domain context.
    """
    if not primary or not secondary:
        return secondary
    primary_sentences = _sentences(primary)
    lines = secondary.split("\n")
    filtered = []
    for line in lines:
        if line.strip().lower() in primary_sentences:
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def compose_agent_prompt(
    domain_prompt: Optional[str],
    agent_prompt: Optional[str],
    user_input: Optional[str] = None,
) -> tuple[str, str]:
    """
    Build (system_prompt, user_message) for LLM calls.

    system_prompt = domain_prompt + agent_prompt (deduplicated, normalized)
    user_message  = user_input (normalized)

    Returns a tuple so callers can pass them separately to the LLM.
    """
    d = normalize(domain_prompt)
    a = normalize(agent_prompt)
    u = normalize(user_input) if user_input is not None else None

    # Cap lengths to avoid token blowout
    if len(d) > MAX_DOMAIN_PROMPT_CHARS:
        d = d[:MAX_DOMAIN_PROMPT_CHARS] + "\n[domain prompt truncated]"
    if len(a) > MAX_AGENT_PROMPT_CHARS:
        a = a[:MAX_AGENT_PROMPT_CHARS] + "\n[agent prompt truncated]"

    # Remove agent lines that duplicate domain content
    if d and a:
        a = deduplicate_sections(d, a)

    parts = [p for p in [d, a] if p]
    system = "\n\n".join(parts) or "You are a helpful assistant."

    # ── DEBUG: log the composed prompt ───────────────────────────────────────
    print("=" * 60, flush=True)
    print("[PROMPT DEBUG] Composed system prompt:", flush=True)
    if d:
        print(f"  [DOMAIN PROMPT]:\n{d}", flush=True)
    else:
        print("  [DOMAIN PROMPT]: (empty — not prepended)", flush=True)
    if a:
        print(f"  [AGENT PROMPT]:\n{a}", flush=True)
    else:
        print("  [AGENT PROMPT]: (empty)", flush=True)
    print(f"  [FULL SYSTEM PROMPT]:\n{system}", flush=True)
    if u:
        print(f"  [USER INPUT]:\n{u}", flush=True)
    print("=" * 60, flush=True)
    # ─────────────────────────────────────────────────────────────────────────

    return system, (u or "")
