from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP

# Initialize the MCP server (the name can be anything descriptive)
#mcp = FastMCP("File Summary Server")
# The server instance is created lazily in the __main__ block so the module can be imported


class FileSummary(BaseModel):
    """Structured summary of a file's contents.

    The model is deliberately small – it provides enough information for an LLM or
    downstream tool to understand the file without sending the whole payload.
    """

    path: str = Field(..., description="Absolute path of the processed file")
    size_bytes: int = Field(..., description="File size in bytes")
    line_count: int = Field(..., description="Number of lines in the file")
    preview: str = Field(
        ..., description="First 200 characters of the file (or the whole file if shorter)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if the file could not be read; otherwise null",
    )


def _read_file(path: Path) -> tuple[int, int, str]:
    """Read a file and return size, line count and a preview.

    This helper is deliberately synchronous – reading a small text file is fast
    and keeps the implementation simple. For large binary files you would want to
    stream the content instead.
    """
    content = path.read_text(encoding="utf-8", errors="replace")
    size = path.stat().st_size
    lines = content.splitlines()
    preview = content[:200]
    return size, len(lines), preview


def register_tools(mcp: FastMCP) -> None:
    """Register the ``summarize_file`` tool on the provided ``FastMCP`` instance.

    Keeping registration in a function makes the module import‑friendly – the
    server can be created elsewhere and the tool added when desired.
    """

    @mcp.tool()
    def summarize_file(file_path: str) -> FileSummary:
        """Read *file_path* and return a :class:`FileSummary`.

        The function validates the path, attempts to read the file and returns a
        structured summary. If any error occurs (e.g., the file does not exist or
        is not readable) the ``error`` field of the returned model is populated
        and the other fields contain safe fallback values.
        """
        path = Path(file_path).expanduser().resolve()
        try:
            if not path.is_file():
                raise FileNotFoundError(f"Path does not point to a regular file: {path}")
            size, line_count, preview = _read_file(path)
            return FileSummary(
                path=str(path),
                size_bytes=size,
                line_count=line_count,
                preview=preview,
                error=None,
            )
        except Exception as exc:  # Broad catch to turn any problem into a graceful response
            # Log the error via MCP's context if available – the tool itself does not
            # receive a Context object, but the server will capture the exception.
            return FileSummary(
                path=str(path),
                size_bytes=0,
                line_count=0,
                preview="",
                error=str(exc),
            )


if __name__ == "__main__":
    # When executed directly we start a minimal stdio server exposing the tool.
    mcp = FastMCP("File Summary Server")
    register_tools(mcp)
    # ``json_response=True`` makes the output easier to consume for programmatic clients.
    mcp.run(json_response=True)
