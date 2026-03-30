"""
Sandbox Monitor API
===================
Provides real-time visibility into Docker sandbox containers and workspace files.

GET /sandbox/status          — sandbox mode on/off + docker availability
GET /sandbox/containers      — list running/recent agent-run containers
GET /sandbox/workspaces      — list sandbox workspace directories
GET /sandbox/workspaces/{id} — files + logs for a specific workspace
"""
import os
import subprocess
import json
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

SANDBOX_BASE = Path(os.environ.get("SANDBOX_BASE", "/workspace")).resolve()
SANDBOX_MODE = os.environ.get("SANDBOX_MODE", "false").lower() == "true"


def _run_docker(args: list[str]) -> tuple[str, str, int]:
    """Run a docker CLI command, return (stdout, stderr, returncode)."""
    try:
        r = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except FileNotFoundError:
        return "", "Docker CLI not found", 1
    except subprocess.TimeoutExpired:
        return "", "Docker command timed out", 1


@router.get("/status")
def sandbox_status():
    """Return sandbox mode flag and Docker availability."""
    stdout, stderr, code = _run_docker(["info", "--format", "{{.ServerVersion}}"])
    docker_ok = code == 0
    agent_image_ok = False
    if docker_ok:
        img_out, _, img_code = _run_docker(["image", "inspect", "agent-runner:latest", "--format", "{{.Id}}"])
        agent_image_ok = img_code == 0

    return {
        "sandbox_mode":       SANDBOX_MODE,
        "docker_available":   docker_ok,
        "docker_version":     stdout if docker_ok else None,
        "agent_image_ready":  agent_image_ok,
        "sandbox_base":       str(SANDBOX_BASE),
        "ready":              SANDBOX_MODE and docker_ok and agent_image_ok,
    }


@router.get("/containers")
def list_containers():
    """
    List all agent-run containers — running, exited, or recently removed.
    Shows the last 50 containers matching the agent-run-* naming pattern.
    """
    fmt = "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.CreatedAt}}\t{{.Image}}"
    stdout, stderr, code = _run_docker([
        "ps", "-a",
        "--filter", "name=agent-run",
        "--format", fmt,
        "--no-trunc",
    ])

    if code != 0:
        return {"containers": [], "error": stderr}

    containers = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            containers.append({
                "id":         parts[0][:12],
                "name":       parts[1].lstrip("/"),
                "status":     parts[2],
                "created_at": parts[3],
                "image":      parts[4] if len(parts) > 4 else "agent-runner:latest",
                "running":    parts[2].startswith("Up"),
            })

    return {"containers": containers, "count": len(containers)}


@router.get("/containers/{container_id}/logs")
def container_logs(container_id: str, tail: int = 100):
    """Stream the last N lines of logs from a container."""
    stdout, stderr, code = _run_docker(["logs", container_id, "--tail", str(tail)])
    if code != 0:
        raise HTTPException(status_code=404, detail=f"Container not found or no logs: {stderr}")
    return {"logs": stdout, "stderr": stderr}


@router.get("/workspaces")
def list_workspaces():
    """List all sandbox workspace directories with their contents summary."""
    if not SANDBOX_BASE.exists():
        return {"workspaces": []}

    workspaces = []
    for d in sorted(SANDBOX_BASE.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        # Only show sandbox run dirs (they contain .task_input.json)
        if not (d / ".task_input.json").exists():
            continue

        files = [f.name for f in d.iterdir() if f.is_file()]
        has_output = (d / ".task_output.json").exists()
        has_log    = (d / "run.log").exists()

        # Read status from output file if available
        status = "running"
        if has_output:
            try:
                out = json.loads((d / ".task_output.json").read_text())
                status = "success" if out.get("success") else "failed"
            except Exception:
                status = "unknown"

        workspaces.append({
            "id":         d.name,
            "path":       str(d),
            "files":      files,
            "has_output": has_output,
            "has_log":    has_log,
            "status":     status,
            "modified":   datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
        })

    return {"workspaces": workspaces[:50]}


@router.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: str):
    """Return full details for one workspace: output, logs, file list."""
    # Sanitise — no path traversal
    if ".." in workspace_id or "/" in workspace_id:
        raise HTTPException(status_code=400, detail="Invalid workspace id")

    ws = SANDBOX_BASE / workspace_id
    if not ws.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    output = None
    if (ws / ".task_output.json").exists():
        try:
            output = json.loads((ws / ".task_output.json").read_text())
        except Exception:
            output = {"error": "Could not parse output JSON"}

    task_input = None
    if (ws / ".task_input.json").exists():
        try:
            raw = json.loads((ws / ".task_input.json").read_text())
            # Strip sensitive fields before returning to frontend
            task_input = {k: v for k, v in raw.items() if k not in ("llm_api_key",)}
        except Exception:
            pass

    run_log = ""
    if (ws / "run.log").exists():
        run_log = (ws / "run.log").read_text(errors="replace")[-8000:]  # last 8KB

    files = []
    for f in sorted(ws.iterdir()):
        if f.is_file() and not f.name.startswith(".task_"):
            files.append({"name": f.name, "size": f.stat().st_size})

    return {
        "id":         workspace_id,
        "output":     output,
        "task_input": task_input,
        "run_log":    run_log,
        "files":      files,
    }
