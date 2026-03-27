"""
Filesystem browser API
======================
GET  /fs/browse?path=/workspace        — list directory contents
GET  /fs/workspace-root                — return the configured workspace root
POST /fs/mkdir                         — create a subfolder inside workspace
"""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/fs", tags=["filesystem"])

# The workspace root inside the container — set via env var, default /workspace
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))


def _safe(path: str) -> Path:
    """Resolve path and ensure it stays within WORKSPACE_ROOT."""
    if not path or path.strip() in ("", "/"):
        return WORKSPACE_ROOT
    # Strip leading slash so Path join works correctly
    rel = path.lstrip("/")
    resolved = (WORKSPACE_ROOT / rel).resolve()
    # Security: must stay inside workspace root
    try:
        resolved.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path escapes workspace root")
    return resolved


class MkdirRequest(BaseModel):
    path: str   # relative path under workspace root, e.g. "/runs/run_001"


@router.post("/mkdir")
def mkdir(payload: MkdirRequest):
    """Create a new folder inside the workspace. Returns the full container path."""
    target = _safe(payload.path)
    if target.exists():
        if not target.is_dir():
            raise HTTPException(status_code=400, detail="Path exists and is not a directory")
        # Already exists — return it
    else:
        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    try:
        rel = "/" + str(target.relative_to(WORKSPACE_ROOT))
        if rel == "/.":
            rel = "/"
    except ValueError:
        rel = payload.path

    return {
        "created": True,
        "path": rel,
        "full_path": str(target),
    }


@router.get("/workspace-root")
def get_workspace_root():
    """Return the workspace root path as seen inside the container."""
    return {
        "workspace_root": str(WORKSPACE_ROOT),
        "exists": WORKSPACE_ROOT.exists(),
    }


@router.get("/browse")
def browse(path: str = Query(default="/")):
    """
    List directory contents at the given path (relative to workspace root).
    Returns folders and files separately for easy tree rendering.
    """
    target = _safe(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path does not exist: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    entries = []
    try:
        for item in sorted(target.iterdir()):
            # Skip hidden files/dirs
            if item.name.startswith("."):
                continue
            # Compute path relative to workspace root for display
            try:
                rel = "/" + str(item.relative_to(WORKSPACE_ROOT))
            except ValueError:
                rel = str(item)
            entries.append({
                "name": item.name,
                "path": rel,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else None,
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Compute current path relative to workspace root
    try:
        current_rel = "/" + str(target.relative_to(WORKSPACE_ROOT))
        if current_rel == "/.":
            current_rel = "/"
    except ValueError:
        current_rel = "/"

    # Parent path
    if target == WORKSPACE_ROOT:
        parent = None
    else:
        try:
            parent_rel = "/" + str(target.parent.relative_to(WORKSPACE_ROOT))
        except ValueError:
            parent_rel = "/"
        parent = parent_rel

    return {
        "current": current_rel,
        "parent": parent,
        "workspace_root": str(WORKSPACE_ROOT),
        "full_path": str(target),   # actual container path — use this as folder_path in tasks
        "entries": entries,
    }
