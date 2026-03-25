"""
Tasks Router
============
CRUD for task definitions + dry-run execution.

GET    /tasks/                  — list all tasks
POST   /tasks/                  — create task
GET    /tasks/{task_id}         — get single task
PATCH  /tasks/{task_id}         — update task
DELETE /tasks/{task_id}         — delete task
POST   /tasks/{task_id}/dry-run — run task without saving execution
POST   /tasks/dry-run           — dry-run from inline payload (unsaved)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.database import get_db
from app.crypto import decrypt

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_task(task_id: int, db: Session) -> models.Task:
    task = (
        db.query(models.Task)
        .options(joinedload(models.Task.agent).joinedload(models.Agent.domain))
        .filter(models.Task.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _resolve_config(
    llm_config_id, llm_provider, llm_model, llm_temperature, llm_max_tokens, llm_top_p, db: Session
) -> dict:
    """Return a plain dict of LLM config fields with per-task overrides applied."""
    if llm_config_id:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.id == llm_config_id).first()
    else:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()

    if not cfg:
        raise HTTPException(
            status_code=400,
            detail="No LLM config available. Set an active config or specify llm_config_id.",
        )

    # Build a plain dict — never mutate the ORM object
    data = {
        "provider": cfg.provider,
        "base_url": cfg.base_url,
        "api_key": decrypt(cfg.api_key) if cfg.api_key else "",
        "model_name": cfg.model_name,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "top_p": cfg.top_p,
        "top_k": cfg.top_k,
    }
    # Apply per-task overrides
    if llm_provider:
        data["provider"] = llm_provider
    if llm_model:
        data["model_name"] = llm_model
    if llm_temperature is not None:
        data["temperature"] = llm_temperature
    if llm_max_tokens is not None:
        data["max_tokens"] = llm_max_tokens
    if llm_top_p is not None:
        data["top_p"] = llm_top_p
    return data


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return (
        db.query(models.Task)
        .options(joinedload(models.Task.agent).joinedload(models.Agent.domain))
        .order_by(models.Task.created_at.desc())
        .all()
    )


@router.post("/", response_model=schemas.TaskOut, status_code=201)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Task name is required")
    if not payload.description.strip():
        raise HTTPException(status_code=422, detail="Task description is required")
    if payload.agent_id and not db.query(models.Agent).filter(models.Agent.id == payload.agent_id).first():
        raise HTTPException(status_code=404, detail="Agent not found")

    task = models.Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return _load_task(task.id, db)


# NOTE: /dry-run must be declared BEFORE /{task_id} to avoid "dry-run" being parsed as an int
@router.post("/dry-run", response_model=schemas.TaskDryRunResponse)
async def dry_run_inline(payload: schemas.TaskDryRunRequest, db: Session = Depends(get_db)):
    return await _execute_dry_run(
        description=payload.description,
        agent_id=payload.agent_id,
        llm_config_id=payload.llm_config_id,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        llm_temperature=payload.llm_temperature,
        llm_max_tokens=payload.llm_max_tokens,
        llm_top_p=payload.llm_top_p,
        llm_system_behavior=payload.llm_system_behavior,
        tool_usage_mode=payload.tool_usage_mode,
        workflow=payload.workflow,
        folder_path=payload.folder_path,
        db=db,
    )


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return _load_task(task_id, db)


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = _load_task(task_id, db)
    data = payload.model_dump(exclude_unset=True)
    if "agent_id" in data and data["agent_id"] and not db.query(models.Agent).filter(models.Agent.id == data["agent_id"]).first():
        raise HTTPException(status_code=404, detail="Agent not found")
    for k, v in data.items():
        setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return _load_task(task.id, db)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()


# ── Dry Run ───────────────────────────────────────────────────────────────────

async def _execute_dry_run(
    description: str,
    agent_id,
    llm_config_id,
    llm_provider,
    llm_model,
    llm_temperature,
    llm_max_tokens,
    llm_top_p,
    llm_system_behavior,
    tool_usage_mode,
    workflow,
    folder_path,
    db: Session,
) -> schemas.TaskDryRunResponse:
    from pathlib import Path
    from types import SimpleNamespace
    from app.routers.task_playground import _build_fs_tools, _run_agent_loop

    agent = None
    if agent_id:
        agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

    cfg_dict = _resolve_config(llm_config_id, llm_provider, llm_model, llm_temperature, llm_max_tokens, llm_top_p, db)
    cfg = SimpleNamespace(**cfg_dict)

    skill = (agent.system_prompt if agent else "") + "\n\n" + (llm_system_behavior or "")
    skill = skill.strip() or "You are a helpful assistant."

    # Build tools based on tool_usage_mode
    tools = []
    if tool_usage_mode != "none" and folder_path:
        root = Path(folder_path)
        if root.exists() and root.is_dir():
            perms = ["read_files", "browse_folders"]
            if tool_usage_mode == "allowed":
                perms += ["write_files"]
            tools = _build_fs_tools(root, perms)

    # Prepend workflow to task description if provided
    task_text = description
    if workflow and workflow.strip():
        task_text = f"{description}\n\nFollow these steps:\n{workflow}"

    if folder_path:
        task_text += f"\n\nWorking directory: {folder_path}"

    result, steps = await _run_agent_loop(cfg, skill, task_text, Path(folder_path or "."), tools)
    return schemas.TaskDryRunResponse(result=result, steps=steps)


@router.post("/{task_id}/dry-run", response_model=schemas.TaskDryRunResponse)
async def dry_run_saved(task_id: int, db: Session = Depends(get_db)):
    task = _load_task(task_id, db)
    return await _execute_dry_run(
        description=task.description,
        agent_id=task.agent_id,
        llm_config_id=task.llm_config_id,
        llm_provider=task.llm_provider,
        llm_model=task.llm_model,
        llm_temperature=task.llm_temperature,
        llm_max_tokens=task.llm_max_tokens,
        llm_top_p=task.llm_top_p,
        llm_system_behavior=task.llm_system_behavior,
        tool_usage_mode=task.tool_usage_mode,
        workflow=task.workflow,
        folder_path=task.folder_path,
        db=db,
    )


@router.post("/dry-run", response_model=schemas.TaskDryRunResponse)
async def dry_run_inline(payload: schemas.TaskDryRunRequest, db: Session = Depends(get_db)):
    return await _execute_dry_run(
        description=payload.description,
        agent_id=payload.agent_id,
        llm_config_id=payload.llm_config_id,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        llm_temperature=payload.llm_temperature,
        llm_max_tokens=payload.llm_max_tokens,
        llm_top_p=payload.llm_top_p,
        llm_system_behavior=payload.llm_system_behavior,
        tool_usage_mode=payload.tool_usage_mode,
        workflow=payload.workflow,
        folder_path=payload.folder_path,
        db=db,
    )
