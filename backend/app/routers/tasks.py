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


@router.post("/{task_id}/run", response_model=schemas.TaskRunOut)
async def run_task(task_id: int, db: Session = Depends(get_db)):
    """Manually execute a saved task and record the result."""
    from datetime import datetime, timezone
    import time
    from app.workflow_runner import run_task_in_workflow
    from sqlalchemy.orm import joinedload

    task = (
        db.query(models.Task)
        .options(joinedload(models.Task.agent).joinedload(models.Agent.domain))
        .filter(models.Task.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    run = models.TaskRun(
        task_id=task_id,
        triggered_by="manual",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    t_start = time.time()
    try:
        from fastapi.concurrency import run_in_threadpool
        result = await run_in_threadpool(run_task_in_workflow, task, db, None)
        run.status = "success" if result.get("success") else "failed"
        run.output = result.get("final_text", "")
        run.logs = result.get("logs", [])
        if not result.get("success"):
            run.error = result.get("error", "Task failed")
    except Exception as e:
        run.status = "failed"
        run.error = str(e)
        run.logs = []

    run.finished_at = datetime.now(timezone.utc)
    run.duration_seconds = round(time.time() - t_start, 2)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{task_id}/runs", response_model=list[schemas.TaskRunOut])
def list_task_runs(task_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Return run history for a task (standalone runs only)."""
    _load_task(task_id, db)  # 404 if not found
    return (
        db.query(models.TaskRun)
        .filter(models.TaskRun.task_id == task_id)
        .order_by(models.TaskRun.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/{task_id}/schedules")
def get_task_schedules(task_id: int, db: Session = Depends(get_db)):
    """Return schedules that include this task."""
    _load_task(task_id, db)
    links = (
        db.query(models.ScheduleTask)
        .filter(models.ScheduleTask.task_id == task_id)
        .all()
    )
    result = []
    for link in links:
        sched = db.query(models.Schedule).filter(models.Schedule.id == link.schedule_id).first()
        if sched:
            result.append({
                "schedule_id": sched.id,
                "schedule_name": sched.name,
                "trigger_type": sched.trigger_type,
                "position": link.position,
                "is_active": sched.is_active,
            })
    return result


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
    from app.prompt_utils import compose_agent_prompt
    from sqlalchemy.orm import joinedload

    agent = None
    if agent_id:
        agent = (
            db.query(models.Agent)
            .options(joinedload(models.Agent.domain))
            .filter(models.Agent.id == agent_id)
            .first()
        )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

    cfg_dict = _resolve_config(llm_config_id, llm_provider, llm_model, llm_temperature, llm_max_tokens, llm_top_p, db)
    cfg = SimpleNamespace(**cfg_dict)

    domain_prompt = agent.domain.domain_prompt if (agent and agent.domain) else None
    agent_prompt = (agent.system_prompt if agent else "") + ("\n\n" + llm_system_behavior if llm_system_behavior else "")
    system, _ = compose_agent_prompt(domain_prompt, agent_prompt)

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

    result, steps = await _run_agent_loop(cfg, system, task_text, Path(folder_path or "."), tools)
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
