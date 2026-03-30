from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP


class FileSummary(BaseModel):
    """Structured summary of a file.

    The model is used as the return type for the ``summarize_file`` tool.
    It contains basic metadata, a short preview of the content, and an optional
    error field that is populated when the file cannot be read.
    """

    path: str = Field(..., description="Absolute path of the file")
    size_bytes: int = Field(..., description="File size in bytes")
    line_count: int = Field(..., description="Number of lines in the file")
    preview: str = Field(..., description="First few lines (up to 5) of the file")
    error: Optional[str] = Field(
        None, description="Error message if reading failed"
    )


# Create a FastMCP server instance. In a larger application you would import
# this instance elsewhere and register additional tools.
mcp = FastMCP("File Summary Tool")


@mcp.tool()
def summarize_file(path: str) -> FileSummary:
    """Read a file and return a structured summary.

    The function is deliberately defensive: it validates the path, handles
    missing‑file and permission errors, and always returns a ``FileSummary``
    instance.  When an error occurs the ``error`` field is populated and the
    other fields contain safe default values.

    Args:
        path: Path to the file to read. Relative paths are resolved against the
            current working directory.

    Returns:
        FileSummary: Structured information about the file or an error.
    """
    try:
        # Resolve to an absolute path for reproducibility.
        abs_path = os.path.abspath(path)

        # Basic existence checks.
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"File not found: {abs_path}")
        if not os.path.isfile(abs_path):
            raise IsADirectoryError(f"Path is not a file: {abs_path}")

        # Read the file content safely using UTF‑8. If the file is binary or has a
        # different encoding, the exception will be caught and reported.
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        size = os.path.getsize(abs_path)
        preview = "".join(lines[:5])  # First up to five lines.

        return FileSummary(
            path=abs_path,
            size_bytes=size,
            line_count=len(lines),
            preview=preview,
        )
    except Exception as exc:
        # Return a summary that indicates failure without raising.
        return FileSummary(
            path=path,
            size_bytes=0,
            line_count=0,
            preview="",
            error=str(exc),
        )


if __name__ == "__main__":
    # Run the server using the default stdio transport.
    mcp.run()
