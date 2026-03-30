from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server instance. This can be imported and the tool
# registered in a larger application, or the module can be run directly.
#mcp = FastMCP("File Summary Server")

class FileSummary(BaseModel):
    """Structured summary of a file's contents.

    The fields are deliberately simple so they can be easily serialized to JSON
    and understood by downstream agents.
    """

    file_path: str = Field(..., description="Absolute path to the file that was read")
    size_bytes: int = Field(..., description="Size of the file in bytes")
    line_count: int = Field(..., description="Total number of lines in the file")
    word_count: int = Field(..., description="Total number of whitespace‑separated words")
    preview: List[str] = Field(
        ..., description="First few lines of the file (up to `preview_lines`)")
    error: Optional[str] = Field(
        None, description="Error message if the file could not be read")

def _read_file(path: Path) -> str:
    """Read the entire file content as text.

    Raises:
        OSError: If the file cannot be opened or read.
    """
    # Using UTF‑8 with replacement characters to avoid crashes on binary data.
    return path.read_text(encoding="utf-8", errors="replace")

def _summarize_content(content: str, preview_lines: int = 5) -> dict:
    """Create a summary dictionary from raw file content.

    Returns a mapping compatible with the ``FileSummary`` model (excluding the
    ``file_path`` and ``error`` fields).
    """
    lines = content.splitlines()
    line_count = len(lines)
    word_count = sum(len(line.split()) for line in lines)
    preview = lines[:preview_lines]
    return {
        "line_count": line_count,
        "word_count": word_count,
        "preview": preview,
    }

def summarize_file(path: str, preview_lines: int = 5) -> FileSummary:
    """Read *path* and return a :class:`FileSummary`.

    The function is deliberately pure – it does not depend on any MCP context –
    so it can be unit‑tested in isolation.
    """
    file_path = Path(path).expanduser().resolve()
    try:
        # Ensure the file exists and is a regular file.
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        size_bytes = file_path.stat().st_size
        raw_content = _read_file(file_path)
        summary_data = _summarize_content(raw_content, preview_lines)
        return FileSummary(
            file_path=str(file_path),
            size_bytes=size_bytes,
            **summary_data,
        )
    except Exception as exc:  # Broad catch to convert any I/O error to a model.
        return FileSummary(
            file_path=str(file_path),
            size_bytes=0,
            line_count=0,
            word_count=0,
            preview=[],
            error=str(exc),
        )

# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

mcp = FastMCP("File Summary Server")

@mcp.tool()
def file_summary(path: str) -> FileSummary:
    """MCP‑compatible tool that returns a structured summary of *path*.

    The tool delegates to :func:`summarize_file` and therefore inherits its
    error‑handling behaviour.  The returned ``FileSummary`` model is automatically
    serialized by the MCP runtime.
    """
    return summarize_file(path)

if __name__ == "__main__":
    # Running the module directly starts a stdio‑based MCP server exposing the
    # ``file_summary`` tool.
    mcp.run()
