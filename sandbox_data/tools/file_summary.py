'''File summary tool for MCP.

Provides an async tool that reads a file, extracts its content, and returns a structured summary.
The tool is registered using the @mcp.tool() decorator and uses Pydantic models for
schema generation and validation.
''' 

from __future__ import annotations

import pathlib
from typing import Optional

from pydantic import BaseModel, Field

# Import MCP components
from mcp.server.fastmcp import FastMCP
from mcp.context import Context

# Initialize the MCP server (name is arbitrary for this module)
# In a larger application you would likely share a single FastMCP instance.
# Here we create a local instance for registration purposes.
_mcp = FastMCP("File Summary Server")


class FileSummary(BaseModel):
    """Structured summary of a file's content.

    Attributes
    ----------
    path: str
        The absolute path of the file that was processed.
    size_bytes: int
        Size of the file in bytes.
    line_count: int
        Number of lines in the file.
    word_count: int
        Approximate number of whitespace‑separated words.
    preview: str
        The first few lines (up to 5) of the file, joined by newlines.
    """

    path: str = Field(..., description="Absolute path of the processed file")
    size_bytes: int = Field(..., description="File size in bytes")
    line_count: int = Field(..., description="Number of lines in the file")
    word_count: int = Field(..., description="Number of words in the file")
    preview: str = Field(..., description="First up to five lines of the file")


class SummaryResult(BaseModel):
    """Result wrapper returned by the tool.

    If ``success`` is ``True`` the ``summary`` field contains the extracted data.
    Otherwise ``error`` provides a human‑readable explanation.
    """

    success: bool = Field(..., description="Whether the operation succeeded")
    summary: Optional[FileSummary] = Field(
        None, description="Structured summary when the operation succeeds"
    )
    error: Optional[str] = Field(
        None, description="Error message when the operation fails"
    )


def _generate_summary(path: pathlib.Path, content: str) -> FileSummary:
    """Create a :class:`FileSummary` from raw file content.

    Parameters
    ----------
    path:
        The absolute path to the file.
    content:
        Full text content of the file.
    """
    lines = content.splitlines()
    line_count = len(lines)
    word_count = len(content.split())
    preview = "\n".join(lines[:5])
    return FileSummary(
        path=str(path),
        size_bytes=path.stat().st_size,
        line_count=line_count,
        word_count=word_count,
        preview=preview,
    )


@_mcp.tool()
async def summarize_file(path: str, ctx: Context | None = None) -> SummaryResult:
    """Read a file and return a structured summary.

    The function is deliberately async to fit MCP's asynchronous execution model.
    It logs useful diagnostics via the provided ``ctx`` (if any).

    Parameters
    ----------
    path:
        Relative or absolute path to the file to be summarized.
    ctx:
        Optional MCP ``Context`` for logging and progress reporting.

    Returns
    -------
    SummaryResult
        A Pydantic model containing either the summary or an error description.
    """
    # Resolve the path safely – disallow empty strings and normalise.
    if not path:
        return SummaryResult(success=False, error="Path must be a non‑empty string")

    file_path = pathlib.Path(path).expanduser().resolve()
    if ctx:
        await ctx.debug(f"Attempting to read file: {file_path}")

    try:
        # Ensure the path points to a regular file and is readable.
        if not file_path.is_file():
            return SummaryResult(success=False, error=f"File does not exist: {file_path}")
        # Read the file using UTF‑8 with fallback to latin‑1 for binary‑like text.
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback for files that are not valid UTF‑8.
            content = file_path.read_text(encoding="latin-1")
        summary = _generate_summary(file_path, content)
        if ctx:
            await ctx.info(f"Successfully summarized file: {file_path}")
        return SummaryResult(success=True, summary=summary)
    except Exception as exc:  # pragma: no cover – defensive programming
        # Log the unexpected error and return a user‑friendly message.
        if ctx:
            await ctx.error(f"Error reading file {file_path}: {exc}")
        return SummaryResult(success=False, error=str(exc))

# Export the MCP instance so that external code can mount or run it.
__all__ = ["_mcp", "summarize_file", "FileSummary", "SummaryResult"]
