"""
Tools Management Router
=======================
Endpoints:
  GET  /tools/                              — list all tools with their permissions
  GET  /tools/{tool_key}                    — single tool spec
  GET  /tools/agents/{agent_id}/access      — all tool access records for an agent
  PUT  /tools/agents/{agent_id}/access      — bulk save/update tool permissions for an agent
  GET  /tools/domains/{domain_id}/agents    — agents filtered by domain (for the assignment UI)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/tools", tags=["tools"])


# ── Tool Specifications ───────────────────────────────────────────────────────

@router.get("/", response_model=list[schemas.ToolOut])
def list_tools(db: Session = Depends(get_db)):
    """Return all tool definitions with their permission flags."""
    return (
        db.query(models.Tool)
        .options(joinedload(models.Tool.permissions))
        .order_by(models.Tool.id)
        .all()
    )


# ── Domain-filtered agent list (for the assignment dropdowns) ─────────────────
# NOTE: must be declared BEFORE /{tool_key} to avoid the catch-all swallowing it

@router.get("/domains/{domain_id}/agents", response_model=list[schemas.AgentOut])
def agents_by_domain(domain_id: int, db: Session = Depends(get_db)):
    """Return agents that belong to a specific domain."""
    if not db.query(models.Domain).filter(models.Domain.id == domain_id).first():
        raise HTTPException(status_code=404, detail="Domain not found")
    return (
        db.query(models.Agent)
        .options(joinedload(models.Agent.domain))
        .filter(models.Agent.domain_id == domain_id)
        .order_by(models.Agent.name)
        .all()
    )


# ── Agent Tool Access ─────────────────────────────────────────────────────────

def _access_to_out(access: models.AgentToolAccess) -> schemas.AgentToolAccessOut:
    """Map ORM row → response schema, adding tool_key for convenience."""
    return schemas.AgentToolAccessOut(
        id=access.id,
        agent_id=access.agent_id,
        tool_id=access.tool_id,
        tool_key=access.tool.key,
        granted_permissions=access.granted_permissions or [],
        config=access.config or {},
    )


@router.get("/agents/{agent_id}/access", response_model=list[schemas.AgentToolAccessOut])
def get_agent_access(agent_id: int, db: Session = Depends(get_db)):
    """Return all tool access records for a given agent."""
    if not db.query(models.Agent).filter(models.Agent.id == agent_id).first():
        raise HTTPException(status_code=404, detail="Agent not found")
    rows = (
        db.query(models.AgentToolAccess)
        .options(joinedload(models.AgentToolAccess.tool))
        .filter(models.AgentToolAccess.agent_id == agent_id)
        .all()
    )
    return [_access_to_out(r) for r in rows]

@router.put("/agents/{agent_id}/access", response_model=list[schemas.AgentToolAccessOut])
def save_agent_access(
    agent_id: int,
    payload: schemas.AgentToolAccessBulkSave,
    db: Session = Depends(get_db),
):
    """
    Bulk upsert tool permissions for an agent.
    Sends the full list of tool entries — each entry is inserted or updated.
    Tools not mentioned in the payload are left unchanged.
    """
    if not db.query(models.Agent).filter(models.Agent.id == agent_id).first():
        raise HTTPException(status_code=404, detail="Agent not found")

    updated: list[int] = []  # collect access row IDs
    for entry in payload.entries:
        # Resolve tool by key — eagerly load permissions for validation
        tool = (
            db.query(models.Tool)
            .options(joinedload(models.Tool.permissions))
            .filter(models.Tool.key == entry.tool_key)
            .first()
        )
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{entry.tool_key}' not found")

        # Validate that all permission keys exist for this tool
        valid_keys = {p.key for p in tool.permissions}
        invalid = set(entry.granted_permissions) - valid_keys
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid permission keys for '{entry.tool_key}': {sorted(invalid)}",
            )

        # Upsert
        access = (
            db.query(models.AgentToolAccess)
            .filter_by(agent_id=agent_id, tool_id=tool.id)
            .first()
        )
        if access:
            access.granted_permissions = entry.granted_permissions
            access.config = entry.config or {}
        else:
            access = models.AgentToolAccess(
                agent_id=agent_id,
                tool_id=tool.id,
                granted_permissions=entry.granted_permissions,
                config=entry.config or {},
            )
            db.add(access)

        db.flush()
        updated.append(access.id)  # store id, re-query after commit

    db.commit()

    # Re-fetch with eager load after commit to avoid lazy-load issues
    result_rows = (
        db.query(models.AgentToolAccess)
        .options(joinedload(models.AgentToolAccess.tool))
        .filter(
            models.AgentToolAccess.agent_id == agent_id,
            models.AgentToolAccess.id.in_(updated),
        )
        .all()
    )
    return [_access_to_out(r) for r in result_rows]


# ── Single tool by key — MUST be last to avoid swallowing other routes ────────

@router.get("/{tool_key}", response_model=schemas.ToolOut)
def get_tool(tool_key: str, db: Session = Depends(get_db)):
    """Return a single tool spec by its stable key (e.g. 'filesystem')."""
    tool = (
        db.query(models.Tool)
        .options(joinedload(models.Tool.permissions))
        .filter(models.Tool.key == tool_key)
        .first()
    )
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_key}' not found")
    return tool
