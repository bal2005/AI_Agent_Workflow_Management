"""MCP tool for summarizing a file's content.

This module defines a FastMCP server with a single tool `summarize_file` that
* accepts a file path,
* reads the file content (if possible), and
* returns a structured summary using a Pydantic model.

The tool handles missing files, permission errors, and other I/O problems
gracefully, returning an `error` field in the summary when appropriate.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.context import Context
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pydantic model representing the structured summary returned by the tool.
# ---------------------------------------------------------------------------
class FileSummary(BaseModel):
    """Structured summary of a file.

    Attributes
    ----------
    path: str
        The absolute path that was requested.
    exists: bool
        Whether the file exists on the filesystem.
    readable: bool
        Whether the file could be opened for reading.
    size_bytes: Optional[int]
        Size of the file in bytes (if it exists).
    line_count: Optional[int]
        Number of lines in the file (if readable).
    preview: Optional[str]
        First 3 lines of the file joined by ``"\n"`` (if readable).
    error: Optional[str]
        Human‑readable error message when something goes wrong.
    """

    path: str = Field(..., description="The absolute file path that was processed")
    exists: bool = Field(..., description="True if the file exists on the filesystem")
    readable: bool = Field(..., description="True if the file could be opened for reading")
    size_bytes: Optional[int] = Field(
        None, description="Size of the file in bytes (None when file does not exist)"
    )
    line_count: Optional[int] = Field(
        None, description="Number of lines in the file (None when unreadable)"
    )
    preview: Optional[str] = Field(
        None,
        description="First three lines of the file joined by newlines (None when unreadable)",
    )
    error: Optional[str] = Field(
        None, description="Error message describing why the file could not be processed"
    )


# ---------------------------------------------------------------------------
# Helper functions – kept separate for testability and clarity.
# ---------------------------------------------------------------------------
def _read_file(path: Path) -> str:
    """Read the full text of *path*.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    PermissionError
        If the file cannot be opened for reading.
    OSError
        For other I/O related problems.
    """
    # Using binary mode then decoding ensures we handle any UTF‑8 compatible file.
    with path.open("rb") as f:
        return f.read().decode(errors="replace")


def _generate_summary(path_str: str, content: Optional[str], error: Optional[str] = None) -> FileSummary:
    """Create a :class:`FileSummary` from the raw content.

    Parameters
    ----------
    path_str: str
        The original path supplied by the caller.
    content: Optional[str]
        The file content when reading succeeded; ``None`` otherwise.
    error: Optional[str]
        Optional error message to embed in the summary.
    """
    abs_path = str(Path(path_str).expanduser().resolve())
    exists = Path(abs_path).exists()
    readable = exists and Path(abs_path).is_file()
    size = os.path.getsize(abs_path) if exists else None

    if content is None:
        # Unreadable – keep the fields that do not depend on content as ``None``.
        return FileSummary(
            path=abs_path,
            exists=exists,
            readable=False,
            size_bytes=size,
            line_count=None,
            preview=None,
            error=error,
        )

    # Content is available – compute line count and a short preview.
    lines = content.splitlines()
    line_count = len(lines)
    preview = "\n".join(lines[:3]) if lines else ""
    return FileSummary(
        path=abs_path,
        exists=True,
        readable=True,
        size_bytes=size,
        line_count=line_count,
        preview=preview,
        error=error,
    )


# ---------------------------------------------------------------------------
# MCP server and tool registration.
# ---------------------------------------------------------------------------
mcp = FastMCP("File Summary Server")


@mcp.tool()
async def summarize_file(path: str, ctx: Context) -> FileSummary:
    """Return a structured summary of the file located at *path*.

    The function is deliberately tolerant – it never raises an exception to the
    caller.  Instead, any problem is captured in the ``error`` field of the
    returned :class:`FileSummary`.

    Parameters
    ----------
    path:
        Relative or absolute path to the file to be summarized.
    ctx:
        MCP context – currently unused but kept for consistency with the
        framework's signature requirements.
    """
    # Normalise the path early for logging / debugging purposes.
    abs_path = Path(path).expanduser().resolve()
    await ctx.debug(f"Summarizing file: {abs_path}")

    # Fast‑path: file does not exist.
    if not abs_path.exists():
        error_msg = f"File not found: {abs_path}"
        await ctx.error(error_msg)
        return _generate_summary(str(abs_path), None, error=error_msg)

    # Ensure we are dealing with a regular file, not a directory.
    if not abs_path.is_file():
        error_msg = f"Path is not a file: {abs_path}"
        await ctx.error(error_msg)
        return _generate_summary(str(abs_path), None, error=error_msg)

    try:
        content = _read_file(abs_path)
        await ctx.info(f"Read {len(content)} characters from {abs_path}")
        return _generate_summary(str(abs_path), content)
    except PermissionError as exc:
        error_msg = f"Permission denied when reading {abs_path}: {exc}"
        await ctx.error(error_msg)
        return _generate_summary(str(abs_path), None, error=error_msg)
    except OSError as exc:
        error_msg = f"I/O error reading {abs_path}: {exc}"
        await ctx.error(error_msg)
        return _generate_summary(str(abs_path), None, error=error_msg)


if __name__ == "__main__":
    # Running the module directly starts a stdio‑based MCP server, which is
    # convenient for quick manual testing.
    mcp.run()
