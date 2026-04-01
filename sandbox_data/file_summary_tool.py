from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Import MCP types. The actual import path may vary depending on the SDK version.
# ``Context`` provides logging and other runtime capabilities.
# ``tool`` is a decorator factory that can be used without an explicit FastMCP instance
# for modular registration.
try:
    from mcp import Context, tool  # type: ignore
except ImportError:  # pragma: no cover
    # Fallback placeholders for static analysis / documentation generation.
    Context = object  # type: ignore
    def tool(*_args, **_kwargs):  # type: ignore
        def decorator(func):
            return func
        return decorator


class FileSummary(BaseModel):
    """Structured summary of a text file.

    The model is used as the return type for the ``summarize_file`` tool so that
    MCP can automatically generate a JSON schema for validation and client
    consumption.
    """

    path: str = Field(..., description="Absolute path of the processed file")
    line_count: int = Field(..., description="Number of lines in the file")
    word_count: int = Field(..., description="Number of words in the file")
    preview: str = Field(..., description="First 200 characters of the file (UTF‑8)"
    )
    error: Optional[str] = Field(
        None, description="Error message if processing failed; ``null`` on success"
    )


@tool()
async def summarize_file(file_path: str, ctx: Context) -> FileSummary:
    """Read a file and return a structured summary.

    The function is deliberately lightweight – it reads the entire file into
    memory, counts lines and words, and returns a short preview.  Errors such as
    missing files or permission problems are caught and reported via the
    ``Context`` logger while still returning a ``FileSummary`` instance with the
    ``error`` field populated.

    Args:
        file_path: Path to the file to read.  ``~`` and relative paths are
            expanded and resolved to an absolute path.
        ctx: MCP ``Context`` providing async logging helpers.

    Returns:
        A :class:`FileSummary` instance containing the summary or an error.
    """
    # Resolve the path early so that the returned ``path`` field is canonical.
    path = Path(file_path).expanduser().resolve()
    try:
        # ``read_text`` raises ``FileNotFoundError`` or ``PermissionError`` for
        # common failure modes.  We catch a broad ``Exception`` to also handle
        # encoding errors.
        content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover – exercised via tests
        # Log the problem – ``ctx.error`` is async, so we ``await`` it.
        await ctx.error(f"Failed to read file {path!s}: {exc}")
        return FileSummary(
            path=str(path),
            line_count=0,
            word_count=0,
            preview="",
            error=str(exc),
        )

    # Compute simple statistics.
    lines = content.splitlines()
    words = content.split()
    preview = content[:200]

    # Log a debug message with the computed values.
    await ctx.debug(
        f"Read file {path!s}: {len(lines)} lines, {len(words)} words, preview length {len(preview)}"
    )

    return FileSummary(
        path=str(path),
        line_count=len(lines),
        word_count=len(words),
        preview=preview,
        error=None,
    )


def register(mcp):
    """Register the ``summarize_file`` tool with a :class:`FastMCP` instance.

    This helper allows the module to be imported without side‑effects while still
    providing a convenient way to add the tool to an existing server:

    ```python
    from mcp.server.fastmcp import FastMCP
    from file_summary_tool import register

    mcp = FastMCP("Demo Server")
    register(mcp)
    mcp.run()
    ```
    """
    # ``mcp.tool`` returns a decorator; applying it to the function registers it.
    mcp.tool()(summarize_file)
