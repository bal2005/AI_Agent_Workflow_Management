"""
Web Search Tools — powered by Tavily
======================================
Two permission groups:
  perform_search    → perform_web_search, search_news, search_domain
  open_result_links → open_result_link, extract_page_content

Tavily is a search API built for AI agents. It returns clean, structured
results with full page content — no scraping, no rate-limit roulette.

Requires: TAVILY_API_KEY in environment (.env or docker-compose).
Get a free key at: https://app.tavily.com
"""

import os
import httpx
from typing import Optional

TIMEOUT = 30
TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


def _get_tavily_key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "TAVILY_API_KEY is not set. Add it to backend/.env and restart the backend."
        )
    return key


# ── Core Tavily search ────────────────────────────────────────────────────────

def _tavily_search(
    query: str,
    max_results: int = 8,
    search_depth: str = "basic",   # "basic" or "advanced"
    topic: str = "general",        # "general" or "news"
    include_answer: bool = True,
    days: Optional[int] = None,    # for news: restrict to last N days
) -> str:
    """
    Call the Tavily search API and return formatted results.
    Returns a human-readable string the LLM can use directly.
    """
    try:
        key = _get_tavily_key()
    except RuntimeError as e:
        return f"[Search error] {e}"

    payload: dict = {
        "api_key":       key,
        "query":         query,
        "max_results":   min(max_results, 10),  # Tavily max is 10
        "search_depth":  search_depth,
        "topic":         topic,
        "include_answer": include_answer,
        "include_raw_content": False,
    }
    if days and topic == "news":
        payload["days"] = days

    try:
        resp = httpx.post(TAVILY_API_URL, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except Exception:
            detail = e.response.text
        return f"[Search error] Tavily API {e.response.status_code}: {detail}"
    except Exception as e:
        return f"[Search error] {e}"

    lines = []

    # Tavily often returns a direct answer — very useful for factual queries
    answer = data.get("answer", "")
    if answer:
        lines.append(f"Answer: {answer}\n")

    results = data.get("results", [])
    if not results:
        return f"No results found for: {query}"

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   URL: {r.get('url', '')}")
        # Tavily returns clean content — use it directly
        content = r.get("content", "")
        if content:
            lines.append(f"   {content[:300]}")
        lines.append("")

    return "\n".join(lines).strip()


# ── perform_search group ──────────────────────────────────────────────────────

def perform_web_search(query: str, max_results: int = 8, safe_search: bool = True) -> str:
    """General web search using Tavily. Returns titles, URLs, snippets, and a direct answer."""
    return _tavily_search(query, max_results=max_results, topic="general")


def search_news(query: str, max_results: int = 8) -> str:
    """Search for recent news articles using Tavily news topic."""
    return _tavily_search(query, max_results=max_results, topic="news", days=7)


def search_domain(query: str, domain: str, max_results: int = 6) -> str:
    """Search within a specific domain by appending site: to the query."""
    scoped_query = f"site:{domain} {query}"
    return _tavily_search(scoped_query, max_results=max_results)


# ── open_result_links group ───────────────────────────────────────────────────

def open_result_link(url: str) -> str:
    """
    Open a URL and return a preview using Tavily extract.
    Falls back to direct httpx fetch if Tavily extract fails.
    """
    return extract_page_content(url, max_chars=2000)


def extract_page_content(url: str, max_chars: int = 8000) -> str:
    """
    Fetch a URL and extract clean readable text using Tavily extract API.
    Falls back to direct httpx + BeautifulSoup if Tavily is unavailable.
    """
    # Try Tavily extract first — returns clean content without scraping noise
    try:
        key = _get_tavily_key()
        resp = httpx.post(
            TAVILY_EXTRACT_URL,
            json={"api_key": key, "urls": [url]},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results:
            r = results[0]
            title   = r.get("title", "")
            content = r.get("raw_content", "") or r.get("content", "")
            return f"Title: {title}\nURL: {url}\n\n{content[:max_chars]}"
    except Exception:
        pass  # fall through to httpx fallback

    # Fallback: direct httpx fetch
    return _fetch_and_parse(url, max_chars)


def _fetch_and_parse(url: str, max_chars: int = 8000) -> str:
    """Direct httpx fetch + BeautifulSoup parse as fallback."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return f"Error fetching {url}: {e}"

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title"
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "button", "iframe", "noscript"]):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.find("body") or soup
        text = main.get_text(separator="\n", strip=True)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        content = "\n".join(lines)[:max_chars]
        return f"Title: {title}\nURL: {url}\n\n{content}"
    except Exception:
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return f"URL: {url}\n\n{text[:max_chars]}"


# ── Tool registry + dispatcher ────────────────────────────────────────────────

_SEARCH_TOOLS = {
    "perform_web_search": {
        "fn": perform_web_search,
        "description": "Search the web using Tavily. Returns titles, URLs, snippets, and a direct answer when available.",
        "params": {
            "query":       ("string",  "Search query",                              True),
            "max_results": ("integer", "Max results to return (default 8, max 10)", False),
        },
    },
    "search_news": {
        "fn": search_news,
        "description": "Search for recent news articles (last 7 days) using Tavily.",
        "params": {
            "query":       ("string",  "News search query",                         True),
            "max_results": ("integer", "Max results to return (default 8)",         False),
        },
    },
    "search_domain": {
        "fn": search_domain,
        "description": "Search within a specific website domain (e.g. github.com, docs.python.org).",
        "params": {
            "query":       ("string",  "Search query",                              True),
            "domain":      ("string",  "Domain to restrict search to",              True),
            "max_results": ("integer", "Max results (default 6)",                   False),
        },
    },
}

_LINK_TOOLS = {
    "open_result_link": {
        "fn": open_result_link,
        "description": "Open a URL and return a preview of its content.",
        "params": {
            "url": ("string", "Full URL to open", True),
        },
    },
    "extract_page_content": {
        "fn": extract_page_content,
        "description": "Fetch a URL and extract full clean readable text content (up to 8000 chars).",
        "params": {
            "url":       ("string",  "Full URL to fetch",                           True),
            "max_chars": ("integer", "Max characters to return (default 8000)",     False),
        },
    },
}


def _make_tool_def(name: str, spec: dict) -> dict:
    properties = {}
    required = []
    for param_name, (param_type, param_desc, is_required) in spec["params"].items():
        properties[param_name] = {"type": param_type, "description": param_desc}
        if is_required:
            required.append(param_name)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": spec["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_web_tools(web_permissions: dict) -> list[dict]:
    """
    Build tool definitions based on granted web permissions.
    web_permissions = { "perform_search": bool, "open_result_links": bool }
    """
    tools = []
    if web_permissions.get("perform_search", False):
        for name, spec in _SEARCH_TOOLS.items():
            tools.append(_make_tool_def(name, spec))
    if web_permissions.get("open_result_links", False):
        for name, spec in _LINK_TOOLS.items():
            tools.append(_make_tool_def(name, spec))
    return tools


def dispatch_web_tool(name: str, args: dict) -> str:
    """Execute a web tool call by name."""
    all_tools = {**_SEARCH_TOOLS, **_LINK_TOOLS}
    if name not in all_tools:
        return f"Unknown web tool: {name}"
    fn = all_tools[name]["fn"]
    try:
        clean_args = {k: v for k, v in args.items() if v is not None}
        return fn(**clean_args)
    except TypeError as e:
        return f"Error calling {name}: {e}"


ALL_WEB_TOOL_NAMES = set(list(_SEARCH_TOOLS.keys()) + list(_LINK_TOOLS.keys()))
