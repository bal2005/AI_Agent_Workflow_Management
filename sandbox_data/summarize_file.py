'''MCP tool for summarizing a file's contents.

Provides a `summarize_file` tool that accepts a file path, reads the file, and returns a
structured summary using a Pydantic model. Errors such as missing files or permission
issues are handled gracefully and reported back to the caller.
'''

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server instance. In a real deployment you would likely have a
# single FastMCP instance per process and register many tools on it.
#mcp = FastMCP("File Summary Server")

# The structured output model. The fields are deliberately simple so they can be
# used directly by downstream agents.
class FileSummary(BaseModel):
    """Summary information about a text file.

    Attributes
    ----------
    path: str
        The absolute path that was processed.
    exists: bool
        Whether the file existed on the filesystem.
    readable: bool
        Whether the file could be opened for reading.
    line_count: Optional[int]
        Number of lines in the file (``None`` if unreadable).
    word_count: Optional[int]
        Number of whitespace‑separated words (``None`` if unreadable).
    char_count: Optional[int]
        Number of characters (including newlines) (``None`` if unreadable).
    preview: Optional[str]
        The first 200 characters of the file, useful for quick inspection.
    error: Optional[str]
        Human‑readable error message if something went wrong.
    """

    path: str = Field(..., description="Absolute path to the processed file")
    exists: bool = Field(..., description="True if the file exists on disk")
    readable: bool = Field(..., description="True if the file could be opened for reading")
    line_count: Optional[int] = Field(None, description="Number of lines in the file")
    word_count: Optional[int] = Field(None, description="Number of words in the file")
    char_count: Optional[int] = Field(None, description="Number of characters in the file")
    preview: Optional[str] = Field(
        None,
        description="First 200 characters of the file (truncated if longer)",
    )
    error: Optional[str] = Field(
        None,
        description="Error message when the file could not be processed",
    )


def _generate_summary(content: str) -> dict:
    """Create a dictionary with summary statistics from *content*.

    Parameters
    ----------
    content: str
        Full text of the file.

    Returns
    -------
    dict
        Mapping with ``line_count``, ``word_count``, ``char_count`` and ``preview``.
    """
    lines = content.splitlines()
    line_count = len(lines)
    word_count = len(content.split())
    char_count = len(content)
    preview = content[:200]
    return {
        "line_count": line_count,
        "word_count": word_count,
        "char_count": char_count,
        "preview": preview,
    }


# Register the tool. The decorator uses the ``FastMCP`` instance defined above.
@mcp.tool()
def summarize_file(path: str) -> FileSummary:
    """Read *path* and return a structured summary.

    The function is tolerant to errors – if the file does not exist or cannot be read,
    the returned ``FileSummary`` will contain ``exists=False`` or ``readable=False`` and
    an ``error`` description. When the file is successfully read, statistical fields are
    populated and ``error`` is ``None``.
    """
    # Resolve to an absolute path for reproducibility.
    absolute_path = Path(path).expanduser().resolve()
    summary = FileSummary(
        path=str(absolute_path),
        exists=False,
        readable=False,
        line_count=None,
        word_count=None,
        char_count=None,
        preview=None,
        error=None,
    )

    if not absolute_path.exists():
        summary.error = f"File does not exist: {absolute_path}"
        return summary

    summary.exists = True

    # Attempt to open the file in text mode with UTF‑8 encoding. If this fails we capture
    # the exception and surface a friendly message.
    try:
        with open(absolute_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:  # noqa: BLE001 – we want to catch any I/O error.
        summary.error = f"Unable to read file: {exc}"
        return summary

    summary.readable = True
    stats = _generate_summary(content)
    summary.line_count = stats["line_count"]
    summary.word_count = stats["word_count"]
    summary.char_count = stats["char_count"]
    summary.preview = stats["preview"]
    return summary


if __name__ == "__main__":
    # When executed directly, run a small demo using stdio transport.
    # This mirrors the typical pattern shown in the MCP documentation.
    mcp.run()
