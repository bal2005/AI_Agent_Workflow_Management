"""
Permission checker for agent tool access.

Permissions are loaded from the database at execution time — never from
the HTTP request or frontend payload. This ensures the frontend cannot
escalate its own permissions.

Usage:
    checker = PermissionChecker.from_db(db, agent_id)
    checker.require("filesystem", "write_files")   # raises if denied
    checker.allowed("shell", "execute_commands")   # returns bool
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from app.sandbox.logging_config import get_logger

log = get_logger("permissions")


class PermissionDenied(Exception):
    """Raised when an agent attempts a tool call it is not permitted to make."""
    def __init__(self, agent_id: int, tool_key: str, permission: str):
        self.agent_id   = agent_id
        self.tool_key   = tool_key
        self.permission = permission
        super().__init__(
            f"Agent {agent_id} does not have '{permission}' on tool '{tool_key}'"
        )


@dataclass
class PermissionChecker:
    """
    Holds the resolved permission set for one agent during a workflow run.
    Built once per task from the database, then used for all tool calls.
    """
    agent_id: int
    # { tool_key: set of granted permission keys }
    grants: dict[str, set[str]] = field(default_factory=dict)

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def from_db(cls, db, agent_id: int) -> "PermissionChecker":
        """
        Load permissions from the database for the given agent.
        Always reads fresh — never caches across requests.
        """
        from app import models

        rows = (
            db.query(models.AgentToolAccess)
            .filter(models.AgentToolAccess.agent_id == agent_id)
            .all()
        )
        grants: dict[str, set[str]] = {}
        for row in rows:
            tool_key = row.tool.key if row.tool else str(row.tool_id)
            grants[tool_key] = set(row.granted_permissions or [])

        log.debug(
            "Loaded permissions",
            extra={"agent": agent_id, "grants": {k: list(v) for k, v in grants.items()}},
        )
        return cls(agent_id=agent_id, grants=grants)

    @classmethod
    def deny_all(cls, agent_id: int) -> "PermissionChecker":
        """Convenience: create a checker that denies everything (no agent configured)."""
        return cls(agent_id=agent_id, grants={})

    # ── Checks ───────────────────────────────────────────────────────────────

    def allowed(self, tool_key: str, permission: str) -> bool:
        """Return True if the agent has the given permission for the tool."""
        return permission in self.grants.get(tool_key, set())

    def require(self, tool_key: str, permission: str, run_id: Optional[str] = None) -> None:
        """
        Assert the agent has permission. Raises PermissionDenied if not.
        Always logs the outcome so denied attempts are visible in run logs.
        """
        extra = {"agent": self.agent_id, "tool": tool_key, "permission": permission}
        if run_id:
            extra["run_id"] = run_id

        if self.allowed(tool_key, permission):
            log.debug("Permission granted", extra=extra)
        else:
            log.warning("Permission DENIED", extra=extra)
            raise PermissionDenied(self.agent_id, tool_key, permission)
