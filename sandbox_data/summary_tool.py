'''MCP tool for summarizing file content.

Provides a tool that reads a file and returns a structured summary.
''' 

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Import MCP decorator – assume mcp is available in runtime
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP instance (name can be generic)
# In a real application, the server would create a single FastMCP instance
# and register multiple tools. Here we create a local instance for registration.
# The instance is exported as ``mcp`` for external use.

mcp = FastMCP("File Summary Server")


class FileSummary(BaseModel):
    """Structured summary of a file's content.

    Attributes:
        path: The absolute path of the processed file.
        exists: Whether the file existed at the time of processing.
        readable: Whether the file could be opened for reading.
        line_count: Number of lines in the file (0 if unreadable).
        word_count: Number of words in the file (0 if unreadable).
        preview: First 200 characters of the file (empty if unreadable).
        error: Optional error message when the file could not be processed.
    """

    path: str = Field(..., description="Absolute path of the file processed")
    exists: bool = Field(..., description="True if the file exists on the filesystem")
    readable: bool = Field(..., description="True if the file could be opened for reading")
    line_count: int = Field(0, description="Number of lines in the file")
    word_count: int = Field(0, description="Number of words in the file")
    preview: str = Field("", description="First 200 characters of the file content")
    error: Optional[str] = Field(
        None, description="Error message if the file could not be read"
    )


@mcp.tool()
def summarize_file(path: str) -> FileSummary:
    """Read a file and return a structured summary.

    The function attempts to read the file at *path*. If the file does not exist
    or cannot be opened, the returned ``FileSummary`` will contain ``exists`` and
    ``readable`` flags set accordingly and an ``error`` description.

    Args:
        path: Relative or absolute path to the target file.

    Returns:
        FileSummary: Structured information about the file content.
    """
    # Resolve the path to an absolute Path object for consistency.
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
        # Read the entire file using UTF-8 with error handling.
        content = file_path.read_text(encoding="utf-8", errors="replace")
        summary.readable = True
    except Exception as exc:
        summary.error = f"Unable to read file: {exc}"
        return summary

    # Compute simple statistics.
    summary.line_count = content.count("\n") + (0 if content.endswith("\n") else 1)
    summary.word_count = len(content.split())
    summary.preview = content[:200]

    return summary


# Export the FastMCP instance for external usage.
__all__ = ["mcp", "FileSummary", "summarize_file"]
