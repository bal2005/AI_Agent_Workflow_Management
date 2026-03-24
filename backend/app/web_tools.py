"""
Web Search Tools
================
Two permission groups:
  perform_search  → perform_web_search, search_news, search_domain
  open_result_links → open_result_link, extract_page_content

Uses DuckDuckGo (no API key needed) via the duckduckgo-search library,
with httpx + BeautifulSoup for page fetching/extraction.
"""

import httpx
from typing import Optional

TIMEOUT = 15


# ── perform_search group ──────────────────────────────────────────────────────

def perform_web_search(query: str, max_results: int = 8, safe_search: bool = True) -> str:
    """General web search using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            safesearch = "moderate" if safe_search else "off"
            results = list(ddgs.text(query, max_results=max_results, safesearch=safesearch))
        if not results:
            return f"No results found for: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   URL: {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')[:200]}")
            lines.append("")
        return "\n".join(lines).strip()
    except ImportError:
        return "[Error] duckduckgo-search not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"[Search error] {e}"


def search_news(query: str, max_results: int = 8) -> str:
    """Search for recent news articles."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        if not results:
            return f"No news found for: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   Source: {r.get('source', '')}  Date: {r.get('date', '')}")
            lines.append(f"   URL: {r.get('url', '')}")
            lines.append(f"   {r.get('body', '')[:200]}")
            lines.append("")
        return "\n".join(lines).strip()
    except ImportError:
        return "[Error] duckduckgo-search not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"[News search error] {e}"


def search_domain(query: str, domain: str, max_results: int = 6) -> str:
    """Search within a specific domain (e.g. site:github.com)."""
    scoped_query = f"site:{domain} {query}"
    return perform_web_search(scoped_query, max_results=max_results)


# ── open_result_links group ───────────────────────────────────────────────────

def _fetch_html(url: str) -> tuple[str, str]:
    """Fetch a URL and return (html_content, error_or_empty)."""
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
        return resp.text, ""
    except httpx.HTTPStatusError as e:
        return "", f"HTTP {e.response.status_code} for {url}"
    except httpx.ConnectError:
        return "", f"Could not connect to {url}"
    except Exception as e:
        return "", f"Error fetching {url}: {e}"


def open_result_link(url: str) -> str:
    """
    Open a URL and return a summary of the page title + first 1000 chars of text.
    Use extract_page_content for full content extraction.
    """
    html, err = _fetch_html(url)
    if err:
        return err
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title"
        # Remove scripts/styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [ln for ln in text.splitlines() if ln.strip()]
        preview = "\n".join(lines[:40])
        return f"Title: {title}\nURL: {url}\n\n{preview}"
    except ImportError:
        # Fallback: strip tags with regex
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return f"URL: {url}\n\n{text[:1000]}"
    except Exception as e:
        return f"Error parsing page: {e}"


def extract_page_content(url: str, max_chars: int = 8000) -> str:
    """
    Fetch a URL and extract clean readable text content.
    Strips navigation, scripts, and boilerplate. Returns up to max_chars characters.
    """
    html, err = _fetch_html(url)
    if err:
        return err
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title"
        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "button", "iframe", "noscript"]):
            tag.decompose()
        # Prefer article/main content if available
        main = soup.find("article") or soup.find("main") or soup.find("body") or soup
        text = main.get_text(separator="\n", strip=True)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        content = "\n".join(lines)[:max_chars]
        return f"Title: {title}\nURL: {url}\n\n{content}"
    except ImportError:
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return f"URL: {url}\n\n{text[:max_chars]}"
    except Exception as e:
        return f"Error extracting content: {e}"


# ── Tool definitions + dispatcher ─────────────────────────────────────────────

_SEARCH_TOOLS = {
    "perform_web_search": {
        "fn": perform_web_search,
        "description": "Search the web using DuckDuckGo. Returns titles, URLs, and snippets.",
        "params": {
            "query": ("string", "Search query", True),
            "max_results": ("integer", "Max results to return (default 8)", False),
            "safe_search": ("boolean", "Enable safe search filtering (default true)", False),
        },
    },
    "search_news": {
        "fn": search_news,
        "description": "Search for recent news articles on a topic.",
        "params": {
            "query": ("string", "News search query", True),
            "max_results": ("integer", "Max results to return (default 8)", False),
        },
    },
    "search_domain": {
        "fn": search_domain,
        "description": "Search within a specific website domain (e.g. github.com, docs.python.org).",
        "params": {
            "query": ("string", "Search query", True),
            "domain": ("string", "Domain to restrict search to, e.g. 'github.com'", True),
            "max_results": ("integer", "Max results (default 6)", False),
        },
    },
}

_LINK_TOOLS = {
    "open_result_link": {
        "fn": open_result_link,
        "description": "Open a URL and return the page title and a preview of its text content.",
        "params": {
            "url": ("string", "Full URL to open", True),
        },
    },
    "extract_page_content": {
        "fn": extract_page_content,
        "description": "Fetch a URL and extract full clean readable text content (up to 8000 chars).",
        "params": {
            "url": ("string", "Full URL to fetch", True),
            "max_chars": ("integer", "Max characters to return (default 8000)", False),
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
    web_permissions = {
        "perform_search": bool,
        "open_result_links": bool,
    }
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
