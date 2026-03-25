"""
Schedules Router
================
GET    /schedules/                        — list all schedules
POST   /schedules/                        — create schedule
GET    /schedules/{id}                    — get schedule detail
PATCH  /schedules/{id}                    — update schedule
DELETE /schedules/{id}                    — delete schedule
POST   /schedules/{id}/run-now            — trigger immediate run
GET    /schedules/{id}/runs               — run history for schedule
GET    /schedules/runs/{run_id}           — single run detail
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/schedules", tags=["schedules"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(schedule_id: int, db: Session) -> models.Schedule:
    s = (
        db.query(models.Schedule)
        .options(
            joinedload(models.Schedule.schedule_tasks).joinedload(models.ScheduleTask.task)
        )
        .filter(models.Schedule.id == schedule_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


def _compute_next_run(schedule: models.Schedule) -> datetime | None:
    now = datetime.now(timezone.utc)
    if schedule.trigger_type == "interval" and schedule.interval_value:
        unit = schedule.interval_unit or "minutes"
        delta = {
            "minutes": timedelta(minutes=schedule.interval_value),
            "hours": timedelta(hours=schedule.interval_value),
            "days": timedelta(days=schedule.interval_value),
        }.get(unit, timedelta(minutes=schedule.interval_value))
        return now + delta
    if schedule.trigger_type == "cron" and schedule.cron_expression:
        try:
            from croniter import croniter
            return croniter(schedule.cron_expression, now).get_next(datetime)
        except Exception:
            pass
    return None


def _sync_tasks(schedule: models.Schedule, task_items: list, db: Session):
    """Replace schedule_tasks with the new ordered list."""
    db.query(models.ScheduleTask).filter(
        models.ScheduleTask.schedule_id == schedule.id
    ).delete()
    for item in task_items:
        # item may be a ScheduleTaskItem pydantic model or a plain dict
        task_id = item.task_id if hasattr(item, "task_id") else item["task_id"]
        position = item.position if hasattr(item, "position") else item.get("position", 0)
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        db.add(models.ScheduleTask(
            schedule_id=schedule.id,
            task_id=task_id,
            position=position,
        ))


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[schemas.ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return (
        db.query(models.Schedule)
        .options(joinedload(models.Schedule.schedule_tasks).joinedload(models.ScheduleTask.task))
        .order_by(models.Schedule.created_at.desc())
        .all()
    )


@router.post("/", response_model=schemas.ScheduleOut, status_code=201)
def create_schedule(payload: schemas.ScheduleCreate, db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Schedule name is required")

    schedule = models.Schedule(
        name=payload.name.strip(),
        description=payload.description,
        trigger_type=payload.trigger_type,
        interval_value=payload.interval_value,
        interval_unit=payload.interval_unit,
        cron_expression=payload.cron_expression,
        is_active=payload.is_active,
    )
    db.add(schedule)
    db.flush()  # get id before syncing tasks

    if payload.task_ids:
        _sync_tasks(schedule, payload.task_ids, db)

    schedule.next_run_at = _compute_next_run(schedule)
    db.commit()
    return _load(schedule.id, db)


@router.get("/runs/{run_id}", response_model=schemas.ScheduleRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(models.ScheduleRun)
        .options(
            joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task)
        )
        .filter(models.ScheduleRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{schedule_id}", response_model=schemas.ScheduleOut)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return _load(schedule_id, db)


@router.patch("/{schedule_id}", response_model=schemas.ScheduleOut)
def update_schedule(schedule_id: int, payload: schemas.ScheduleUpdate, db: Session = Depends(get_db)):
    schedule = _load(schedule_id, db)
    data = payload.model_dump(exclude_unset=True)
    task_ids = data.pop("task_ids", None)

    for k, v in data.items():
        setattr(schedule, k, v)

    if task_ids is not None:
        _sync_tasks(schedule, task_ids, db)

    schedule.next_run_at = _compute_next_run(schedule)
    db.commit()
    return _load(schedule_id, db)


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(s)
    db.commit()


# ── Run Now ───────────────────────────────────────────────────────────────────

@router.post("/{schedule_id}/run-now", response_model=schemas.ScheduleRunOut)
def run_now(schedule_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    schedule = _load(schedule_id, db)

    # Create a pending run immediately so the UI can show it
    run = models.ScheduleRun(
        schedule_id=schedule_id,
        status="pending",
        triggered_by="manual",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Try Celery first, fall back to background task
    try:
        from app.scheduler_tasks import run_schedule
        run_schedule.delay(schedule_id, "manual")
    except Exception:
        # Celery not available — run in FastAPI background thread
        background_tasks.add_task(_run_in_background, schedule_id, run.id)

    # Re-fetch with task_runs loaded
    return (
        db.query(models.ScheduleRun)
        .options(joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task))
        .filter(models.ScheduleRun.id == run.id)
        .first()
    )


def _run_in_background(schedule_id: int, run_id: int):
    """Fallback: run schedule synchronously in a background thread (no Celery)."""
    from app.scheduler_tasks import run_schedule as _rs
    # Call the underlying function directly (bypasses Celery broker)
    _rs.run(schedule_id, "manual")


# ── Debug / Testing ───────────────────────────────────────────────────────────

@router.post("/debug/trigger-all-due")
def debug_trigger_all_due(db: Session = Depends(get_db)):
    """
    DEBUG ENDPOINT: Manually trigger all schedules that are due.
    Use this to test interval/cron schedules without running Celery Beat.
    """
    from app.scheduler_tasks import run_schedule
    now = datetime.now(timezone.utc)
    
    schedules = db.query(models.Schedule).filter(
        models.Schedule.is_active == True,
        models.Schedule.trigger_type != "manual",
        models.Schedule.next_run_at <= now,
    ).all()
    
    triggered = []
    for schedule in schedules:
        try:
            run_schedule.delay(schedule.id, "scheduler")
            triggered.append({"id": schedule.id, "name": schedule.name, "status": "queued"})
        except Exception as e:
            triggered.append({"id": schedule.id, "name": schedule.name, "status": f"error: {str(e)}"})
    
    return {
        "now": now.isoformat(),
        "triggered_count": len(triggered),
        "schedules": triggered,
    }


@router.get("/debug/status")
def debug_status(db: Session = Depends(get_db)):
    """
    DEBUG ENDPOINT: Show all schedules and their next run times.
    """
    schedules = db.query(models.Schedule).all()
    now = datetime.now(timezone.utc)
    
    return {
        "now": now.isoformat(),
        "schedules": [
            {
                "id": s.id,
                "name": s.name,
                "trigger_type": s.trigger_type,
                "is_active": s.is_active,
                "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                "is_due": s.next_run_at and s.next_run_at <= now if s.trigger_type != "manual" else False,
                "interval": f"{s.interval_value} {s.interval_unit}" if s.interval_value else None,
                "cron": s.cron_expression,
                "task_count": len(s.schedule_tasks),
            }
            for s in schedules
        ],
    }


# ── Run History ───────────────────────────────────────────────────────────────

@router.get("/{schedule_id}/runs", response_model=list[schemas.ScheduleRunOut])
def list_runs(schedule_id: int, limit: int = 20, db: Session = Depends(get_db)):
    _load(schedule_id, db)  # 404 check
    return (
        db.query(models.ScheduleRun)
        .options(
            joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task)
        )
        .filter(models.ScheduleRun.schedule_id == schedule_id)
        .order_by(models.ScheduleRun.created_at.desc())
        .limit(limit)
        .all()
    )
