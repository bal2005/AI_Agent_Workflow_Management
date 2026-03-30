"""MCP tool for summarizing a file's content.

Provides a single tool ``file_summary`` that accepts a file path, reads the file,
and returns a structured summary. Errors such as missing files or permission
issues are captured and reported in the returned model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Import the FastMCP class – the runtime will provide the ``mcp`` instance.
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Pydantic model describing the structured output.
# ---------------------------------------------------------------------------

class FileSummary(BaseModel):
    """Structured summary of a file.

    Attributes
    ----------
    path: str
        Absolute path of the processed file.
    exists: bool
        ``True`` if the file existed on the filesystem.
    readable: bool
        ``True`` if the file could be opened for reading.
    line_count: int
        Number of lines in the file (0 when unreadable).
    word_count: int
        Number of whitespace‑separated words (0 when unreadable).
    char_count: int
        Number of characters, including newlines (0 when unreadable).
    preview: str
        First 200 characters of the file (empty when unreadable).
    error: Optional[str]
        Human‑readable error message when something went wrong.
    """

    path: str = Field(..., description="Absolute path of the processed file")
    exists: bool = Field(..., description="Whether the file exists on disk")
    readable: bool = Field(..., description="Whether the file could be opened for reading")
    line_count: int = Field(0, description="Number of lines in the file")
    word_count: int = Field(0, description="Number of words in the file")
    char_count: int = Field(0, description="Number of characters in the file")
    preview: str = Field("", description="First 200 characters of the file content")
    error: Optional[str] = Field(
        None, description="Error message if the file could not be processed"
    )


# ---------------------------------------------------------------------------
# Helper functions – kept separate for testability and modularity.
# ---------------------------------------------------------------------------

def _read_text(file_path: Path) -> str:
    """Read *file_path* as UTF‑8 text.

    The ``errors='replace'`` flag ensures binary data does not raise an exception.
    """
    return file_path.read_text(encoding="utf-8", errors="replace")


def _generate_summary(content: str) -> dict:
    """Generate simple statistics from *content*.

    Returns a dictionary compatible with the ``FileSummary`` fields (except ``path``
    and error‑related flags).
    """
    line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
    word_count = len(content.split())
    char_count = len(content)
    preview = content[:200]
    return {
        "line_count": line_count,
        "word_count": word_count,
        "char_count": char_count,
        "preview": preview,
    }


# ---------------------------------------------------------------------------
# MCP server instance – exported for external import.
# ---------------------------------------------------------------------------

mcp = FastMCP("File Summary Server")


# ---------------------------------------------------------------------------
# Public tool registration.
# ---------------------------------------------------------------------------

@mcp.tool()
def file_summary(path: str) -> FileSummary:
    """Read *path* and return a :class:`FileSummary`.

    The function is deliberately defensive: it reports existence, readability, and
    any I/O errors via the ``error`` field while still providing a consistent
    ``FileSummary`` object.
    """
    # Resolve to an absolute path for reproducibility.
    file_path = Path(path).expanduser().resolve()

    summary = FileSummary(
        path=str(file_path),
        exists=file_path.is_file(),
        readable=False,
    )

    if not summary.exists:
        summary.error = f"File does not exist: {file_path}"
        return summary

    try:
        content = _read_text(file_path)
        summary.readable = True
    except Exception as exc:
        summary.error = f"Unable to read file: {exc}"
        return summary

    stats = _generate_summary(content)
    summary.line_count = stats["line_count"]
    summary.word_count = stats["word_count"]
    summary.char_count = stats["char_count"]
    summary.preview = stats["preview"]
    # ``error`` remains ``None`` on success.
    return summary


# ---------------------------------------------------------------------------
# When executed directly, start a stdio‑based MCP server exposing the tool.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

__all__ = ["mcp", "FileSummary", "file_summary"]
