"""MCP tool for reading a file and returning a structured summary.

This module defines a Pydantic model for the summary output and an async
function that can be registered with a :class:`~mcp.server.fastmcp.FastMCP`
instance using the ``@mcp.tool()`` decorator.

The tool:

1. Accepts a file path (string).
2. Reads the file content (text mode, UTF‑8).
3. Returns a summary containing the path, line count, word count, a short
   preview of the content, and an optional error message if something went
   wrong.

Error handling is performed for common I/O problems such as the file not
existing, lacking permissions, or being unreadable.  The function never
raises – it always returns a ``FileSummary`` instance, making it safe to be
used directly by an LLM‑driven agent.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# The MCP server instance is created only when the module is executed as a
# script.  Importers can also import ``summarize_file`` and register it with an
# existing FastMCP instance.


class FileSummary(BaseModel):
    """Structured summary of a file's contents.

    Attributes
    ----------
    file_path: str
        The absolute path that was processed.
    line_count: int
        Number of lines in the file.
    word_count: int
        Number of whitespace‑separated words.
    preview: str
        First 200 characters of the file (or the whole file if shorter).
    error: Optional[str]
        Human‑readable error message when the file could not be read.
    """

    file_path: str = Field(..., description="Absolute path of the processed file")
    line_count: int = Field(..., description="Number of lines in the file")
    word_count: int = Field(..., description="Number of words in the file")
    preview: str = Field(..., description="First 200 characters of the file content")
    error: Optional[str] = Field(
        None, description="Error message if the file could not be read"
    )


async def _read_file(path: Path) -> str:
    """Read a file as UTF‑8 text.

    This helper isolates the I/O so that the public ``summarize_file``
    function stays focused on the summarisation logic.
    """
    # ``Path.read_text`` raises appropriate exceptions which we will catch
    # in the caller.
    return path.read_text(encoding="utf-8")


async def summarize_file(file_path: str) -> FileSummary:
    """Read *file_path* and return a :class:`FileSummary`.

    The function is deliberately tolerant – any exception results in a
    ``FileSummary`` with ``error`` populated while the other fields contain
    safe default values.
    """
    # Resolve to an absolute path for reproducibility.
    path = Path(file_path).expanduser().resolve()

    # Default values used when an error occurs.
    line_count = 0
    word_count = 0
    preview = ""
    error_msg: Optional[str] = None

    try:
        if not path.is_file():
            raise FileNotFoundError(f"Path does not point to a regular file: {path}")
        content = await _read_file(path)
        lines = content.splitlines()
        line_count = len(lines)
        word_count = len(content.split())
        preview = content[:200]
    except FileNotFoundError as exc:
        error_msg = str(exc)
    except PermissionError as exc:
        error_msg = f"Permission denied: {exc}"
    except OSError as exc:
        # Catch any other OS‑related errors (e.g., encoding issues).
        error_msg = f"Unable to read file: {exc}"
    except Exception as exc:  # pragma: no cover – safety net.
        error_msg = f"Unexpected error: {exc}"

    return FileSummary(
        file_path=str(path),
        line_count=line_count,
        word_count=word_count,
        preview=preview,
        error=error_msg,
    )


# ---------------------------------------------------------------------------
# Registration helper – when run directly we start a minimal MCP server exposing
# the ``summarize_file`` tool.  This keeps the module usable both as a library
# and as a standalone demo.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(name="File Summary Server")

    @mcp.tool()
    async def summarize(path: str) -> FileSummary:  # pragma: no cover
        """MCP‑exposed wrapper around :func:`summarize_file`."""
        return await summarize_file(path)

    # Run the server using the default stdio transport.
    mcp.run()
