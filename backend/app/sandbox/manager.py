"""
SandboxManager — creates, runs, and destroys Docker sandbox containers.

One container per workflow run. The container:
  - mounts only sandbox_data/{run_id}/ as /workspace
  - has no network access by default (--network none)
  - is resource-capped (memory + CPU)
  - is auto-removed on exit (--rm)

The agent runner script inside the container reads a task payload JSON
from /workspace/.task_input.json and writes output to /workspace/.task_output.json.

Tradeoff: using --network none means the agent cannot call external APIs.
For agents that need web access, pass network_access=True which uses the
default bridge network instead. This is a conscious security tradeoff.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from app.sandbox.logging_config import get_logger

log = get_logger("sandbox.manager")

# SANDBOX_BASE — path inside the backend container where workspaces are created (file I/O)
SANDBOX_BASE = Path(os.environ.get("SANDBOX_BASE", "/sandbox_host")).resolve()

# HOST_SANDBOX_BASE — the same directory's path on the HOST machine, used in docker run -v
# Must be set to the host-side path of the sandbox_data volume mount.
# e.g. if docker-compose has: - ./sandbox_data:/sandbox_host
# then HOST_SANDBOX_BASE = /absolute/path/to/sandbox_data on the host
HOST_SANDBOX_BASE = os.environ.get("HOST_SANDBOX_BASE", "")

# Docker image that contains the agent runner script
AGENT_IMAGE = os.environ.get("AGENT_IMAGE", "agent-runner:latest")


class SandboxError(Exception):
    """Raised when sandbox creation or execution fails."""


class SandboxManager:
    """Manages the lifecycle of one sandbox container per workflow run."""

    def __init__(self, run_id: Optional[str] = None):
        self.run_id      = run_id or str(uuid.uuid4())
        self.workspace   = SANDBOX_BASE / self.run_id
        self.container_id: Optional[str] = None

    # ── Workspace ─────────────────────────────────────────────────────────────

    def prepare_workspace(self) -> Path:
        """Create the isolated workspace directory for this run."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        log.info("Workspace created", extra={"run_id": self.run_id, "sandbox": str(self.workspace)})
        return self.workspace

    def write_task_input(self, payload: dict) -> None:
        """Write the task payload JSON that the agent runner will read."""
        input_file = self.workspace / ".task_input.json"
        input_file.write_text(json.dumps(payload, indent=2))

    def read_task_output(self) -> dict:
        """Read the output JSON written by the agent runner."""
        output_file = self.workspace / ".task_output.json"
        if not output_file.exists():
            return {"success": False, "error": "No output file produced by agent runner"}
        try:
            return json.loads(output_file.read_text())
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid output JSON: {e}"}

    def read_run_log(self) -> str:
        """Read the execution log written by the agent runner."""
        log_file = self.workspace / "run.log"
        return log_file.read_text() if log_file.exists() else ""

    # ── Container lifecycle ───────────────────────────────────────────────────

    def run(
        self,
        task_payload: dict,
        network_access: bool = False,
        memory_mb: int = 512,
        cpus: float = 1.0,
        timeout_seconds: int = 300,
    ) -> dict:
        self.prepare_workspace()
        self.write_task_input(task_payload)

        # ── Determine the workspace mount path ────────────────────────────────
        # The task's folder_path is where the agent should read/write files.
        # We mount it as /workspace so the agent operates on the real task folder.
        # The run-specific dir (SANDBOX_BASE/run_id) holds only control files
        # (.task_input.json, .task_output.json, run.log) — mounted as /run_workspace.
        #
        # If no folder_path is set, fall back to the run-specific dir for both.

        task_folder = task_payload.get("task_folder_path", "").strip()

        # Build host-side paths for volume mounts
        if HOST_SANDBOX_BASE:
            host_run_dir = HOST_SANDBOX_BASE.rstrip("/") + "/" + self.run_id
        else:
            host_run_dir = str(self.workspace)

        # Resolve the task folder to a host path
        # Inside the backend container, /workspace maps to sandbox_data on the host
        # and /sandbox_host also maps to sandbox_data — so strip the container prefix
        if task_folder:
            # task_folder is a path inside the backend container (e.g. /workspace/test_run_001)
            # Map it to the host path by replacing the container mount point
            if task_folder.startswith("/workspace/"):
                rel = task_folder[len("/workspace/"):]
                if HOST_SANDBOX_BASE:
                    host_task_folder = HOST_SANDBOX_BASE.rstrip("/") + "/" + rel
                else:
                    host_task_folder = str(SANDBOX_BASE / rel)
            elif task_folder.startswith("/sandbox_host/"):
                rel = task_folder[len("/sandbox_host/"):]
                if HOST_SANDBOX_BASE:
                    host_task_folder = HOST_SANDBOX_BASE.rstrip("/") + "/" + rel
                else:
                    host_task_folder = str(SANDBOX_BASE / rel)
            else:
                # Absolute path on host or unknown — use as-is
                host_task_folder = task_folder
        else:
            host_task_folder = host_run_dir

        log.info("Starting sandbox container", extra={
            "run_id":           self.run_id,
            "image":            AGENT_IMAGE,
            "host_task_folder": host_task_folder,
            "host_run_dir":     host_run_dir,
            "network":          "bridge" if network_access else "none",
        })

        cmd = [
            "docker", "run",
            "--rm",
            "--name", f"agent-run-{self.run_id[:12]}",
            # Mount task folder as /workspace — agent reads/writes files here
            "-v", f"{host_task_folder}:/workspace",
            # Mount run-specific dir as /run_workspace — control files go here
            "-v", f"{host_run_dir}:/run_workspace",
            "--network", "bridge" if network_access else "none",
            "--memory", f"{memory_mb}m",
            "--cpus", str(cpus),
            "--env", f"RUN_ID={self.run_id}",
            "--env", f"ENCRYPTION_KEY={os.environ.get('ENCRYPTION_KEY', '')}",
            "--env", f"TAVILY_API_KEY={os.environ.get('TAVILY_API_KEY', '')}",
            "--user", "root",
            AGENT_IMAGE,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            log.error("Sandbox timed out", extra={"run_id": self.run_id, "timeout": timeout_seconds})
            self._force_remove()
            return {"success": False, "error": f"Sandbox timed out after {timeout_seconds}s"}
        except FileNotFoundError:
            # Docker not available — fall back to in-process execution
            log.warning("Docker not found — running agent in-process (no isolation)", extra={"run_id": self.run_id})
            return self._run_inprocess(task_payload)

        if result.returncode != 0:
            log.error("Container exited with error", extra={
                "run_id": self.run_id,
                "exit_code": result.returncode,
                "stderr": result.stderr[:500],
            })
            return {
                "success": False,
                "error": f"Container exit {result.returncode}: {result.stderr[:300]}",
                "logs": result.stdout,
            }

        log.info("Sandbox completed", extra={"run_id": self.run_id})
        output = self.read_task_output()
        output["sandbox_log"] = self.read_run_log()
        return output

    def _force_remove(self) -> None:
        """Force-remove a stuck container."""
        try:
            subprocess.run(
                ["docker", "rm", "-f", f"agent-run-{self.run_id[:12]}"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

    def _run_inprocess(self, task_payload: dict) -> dict:
        """
        Fallback: run the agent directly in the current process when Docker
        is unavailable. No isolation — only for development/testing.
        """
        log.warning("In-process fallback active — no sandbox isolation", extra={"run_id": self.run_id})
        from app.sandbox.agent_runner import run_agent_task
        return run_agent_task(task_payload, workspace=self.workspace)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self, keep_workspace: bool = False) -> None:
        """Remove the workspace directory after the run."""
        if not keep_workspace and self.workspace.exists():
            import shutil
            shutil.rmtree(self.workspace, ignore_errors=True)
            log.info("Workspace cleaned up", extra={"run_id": self.run_id})
