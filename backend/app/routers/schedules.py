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


def _reload_trigger(schedule_id: int, deleted: bool = False) -> None:
    """Reload or stop the filesystem trigger listener for a schedule."""
    try:
        from app.triggers.trigger_registry import registry
        if deleted:
            registry.stop_one(schedule_id)
        else:
            registry.reload(schedule_id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Trigger reload failed for schedule {schedule_id}: {e}")


def _encrypt_trigger_config(trigger_type: str, config: dict | None) -> dict | None:
    """Encrypt sensitive fields in trigger_config before storing."""
    if not config or trigger_type != "email_imap":
        return config
    result = dict(config)
    raw_password = result.get("password", "")
    if raw_password:
        try:
            from app.crypto import encrypt, decrypt
            from cryptography.fernet import InvalidToken
            # Only encrypt if not already encrypted (idempotent on update)
            try:
                decrypt(raw_password)
                # If decrypt succeeds without error it's already a Fernet token — leave it
                # But we can't distinguish plaintext from token reliably, so always re-encrypt
                # plaintext that doesn't look like a Fernet token (starts with "gAAAAA")
            except Exception:
                pass
            if not raw_password.startswith("gAAAAA"):
                result["password"] = encrypt(raw_password)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Password encryption failed: {e}")
    return result


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


@router.get("/all-runs", response_model=list[schemas.ScheduleRunOut])
def list_all_runs(
    limit: int = 100,
    status: str = None,
    triggered_by: str = None,
    db: Session = Depends(get_db),
):
    """Return all schedule runs across all schedules, newest first."""
    q = (
        db.query(models.ScheduleRun)
        .options(
            joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task),
            joinedload(models.ScheduleRun.schedule),
        )
        .order_by(models.ScheduleRun.created_at.desc())
    )
    if status:
        q = q.filter(models.ScheduleRun.status == status)
    if triggered_by:
        q = q.filter(models.ScheduleRun.triggered_by == triggered_by)
    runs = q.limit(limit).all()

    # Manually build response dicts so schedule_name is always populated
    result = []
    for run in runs:
        d = schemas.ScheduleRunOut.model_validate(run)
        if not d.schedule_name and run.schedule:
            d.schedule_name = run.schedule.name
        result.append(d)
    return result


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
        workflow_json=payload.workflow_json,
        trigger_config=_encrypt_trigger_config(payload.trigger_type, payload.trigger_config),
    )
    db.add(schedule)
    db.flush()

    if payload.task_ids:
        _sync_tasks(schedule, payload.task_ids, db)

    schedule.next_run_at = _compute_next_run(schedule)
    db.commit()

    # Reload filesystem trigger listener if applicable
    _reload_trigger(schedule.id)

    return _load(schedule.id, db)


@router.get("/runs/{run_id}", response_model=schemas.ScheduleRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = (
        db.query(models.ScheduleRun)
        .options(
            joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task),
            joinedload(models.ScheduleRun.schedule),
        )
        .filter(models.ScheduleRun.id == run_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    d = schemas.ScheduleRunOut.model_validate(run)
    if not d.schedule_name and run.schedule:
        d.schedule_name = run.schedule.name
    return d


@router.get("/trigger-status")
def trigger_status():
    """Return status of all active filesystem listeners."""
    try:
        from app.triggers.trigger_registry import registry
        return {"listeners": registry.status()}
    except Exception as e:
        return {"listeners": [], "error": str(e)}


@router.get("/{schedule_id}", response_model=schemas.ScheduleOut)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    return _load(schedule_id, db)


@router.patch("/{schedule_id}", response_model=schemas.ScheduleOut)
def update_schedule(schedule_id: int, payload: schemas.ScheduleUpdate, db: Session = Depends(get_db)):
    import logging
    logger = logging.getLogger(__name__)
    schedule = _load(schedule_id, db)
    data = payload.model_dump(exclude_unset=True)
    logger.info(f"[PATCH schedule {schedule_id}] received fields: {list(data.keys())}")
    logger.info(f"[PATCH schedule {schedule_id}] workflow_json in payload: {'workflow_json' in data}, value: {data.get('workflow_json')}")
    task_ids = data.pop("task_ids", None)

    for k, v in data.items():
        if k == "workflow_json" and v is None and schedule.workflow_json is not None:
            continue
        if k == "trigger_config":
            v = _encrypt_trigger_config(data.get("trigger_type") or schedule.trigger_type, v)
        setattr(schedule, k, v)

    if task_ids is not None:
        _sync_tasks(schedule, task_ids, db)

    schedule.next_run_at = _compute_next_run(schedule)
    db.commit()
    result = _load(schedule_id, db)
    logger.info(f"[PATCH schedule {schedule_id}] after save workflow_json: {result.workflow_json}")

    # Reload filesystem trigger listener if applicable
    _reload_trigger(schedule_id)

    return result

@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(s)
    db.commit()
    # Stop filesystem listener if one was running
    _reload_trigger(schedule_id, deleted=True)


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
        run_schedule.delay(schedule_id, "manual", run.id)
    except Exception:
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
    runs = (
        db.query(models.ScheduleRun)
        .options(
            joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task),
            joinedload(models.ScheduleRun.schedule),
        )
        .filter(models.ScheduleRun.schedule_id == schedule_id)
        .order_by(models.ScheduleRun.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for run in runs:
        d = schemas.ScheduleRunOut.model_validate(run)
        if not d.schedule_name and run.schedule:
            d.schedule_name = run.schedule.name
        result.append(d)
    return result


# ── Filesystem Trigger endpoints ──────────────────────────────────────────────

@router.get("/{schedule_id}/trigger-logs")
def get_trigger_logs(schedule_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Return recent filesystem trigger events for a schedule."""
    from app import models as m
    logs = (
        db.query(m.TriggerLog)
        .filter(m.TriggerLog.schedule_id == schedule_id)
        .order_by(m.TriggerLog.triggered_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":             l.id,
            "event_type":     l.event_type,
            "file_path":      l.file_path,
            "matched":        l.matched,
            "debounced":      l.debounced,
            "workflow_fired": l.workflow_fired,
            "notes":          l.notes,
            "triggered_at":   l.triggered_at.isoformat() if l.triggered_at else None,
        }
        for l in logs
    ]


@router.get("/{schedule_id}/email-trigger-logs")
def get_email_trigger_logs(schedule_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Return recent email trigger state rows (processed messages) for a schedule."""
    from app import models as m
    rows = (
        db.query(m.EmailTriggerState)
        .filter(m.EmailTriggerState.schedule_id == schedule_id)
        .order_by(m.EmailTriggerState.seen_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":          r.id,
            "message_uid": r.message_uid,
            "sender":      r.sender,
            "subject":     r.subject,
            "seen_at":     r.seen_at.isoformat() if r.seen_at else None,
        }
        for r in rows
    ]


@router.post("/test-imap")
def test_imap(payload: dict, db: Session = Depends(get_db)):
    """
    Test IMAP connectivity from an unsaved config dict.
    Accepts the same shape as trigger_config for email_imap.
    Password is treated as plaintext here (not yet stored/encrypted).
    """
    from app.crypto import decrypt
    import imaplib, ssl as _ssl

    host     = (payload.get("host") or "").strip()
    port     = int(payload.get("port") or 993)
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    use_ssl  = payload.get("use_ssl", True)
    mailbox  = (payload.get("mailbox") or "INBOX").strip() or "INBOX"

    if not host or not username:
        return {"ok": False, "message": "host and username are required"}

    try:
        if use_ssl:
            ctx = _ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        else:
            conn = imaplib.IMAP4(host, port)
            conn.starttls()
        conn.login(username, password)
        status, data = conn.select(mailbox, readonly=True)
        msg_count = int(data[0]) if data and data[0] else 0
        conn.logout()
        return {"ok": True, "message": f"Connected to {host}. {msg_count} message(s) in {mailbox}."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


@router.patch("/{schedule_id}/trigger-enabled")
def set_trigger_enabled(schedule_id: int, payload: dict, db: Session = Depends(get_db)):
    """Enable or pause the trigger for a schedule without a full update."""
    schedule = _load(schedule_id, db)
    config = dict(schedule.trigger_config or {})
    config["enabled"] = bool(payload.get("enabled", True))
    schedule.trigger_config = config
    db.commit()
    _reload_trigger(schedule_id)
    return {"ok": True, "enabled": config["enabled"]}


@router.post("/{schedule_id}/test-email-connection")
def test_email_connection(schedule_id: int, db: Session = Depends(get_db)):
    """
    Test IMAP connectivity for an email_imap schedule.
    Returns success/error without triggering any workflow.
    """
    schedule = _load(schedule_id, db)
    config = schedule.trigger_config or {}
    if schedule.trigger_type != "email_imap":
        raise HTTPException(status_code=400, detail="Schedule is not email_imap type")

    from app.crypto import decrypt
    import imaplib, ssl as _ssl

    host     = config.get("host", "").strip()
    port     = int(config.get("port", 993))
    username = config.get("username", "").strip()
    password = decrypt(config.get("password", ""))
    use_ssl  = config.get("use_ssl", True)
    mailbox  = config.get("mailbox", "INBOX")

    try:
        if use_ssl:
            ctx = _ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        else:
            conn = imaplib.IMAP4(host, port)
            conn.starttls()
        conn.login(username, password)
        status, data = conn.select(mailbox, readonly=True)
        msg_count = int(data[0]) if data and data[0] else 0
        conn.logout()
        return {"ok": True, "message": f"Connected. {msg_count} message(s) in {mailbox}."}
    except Exception as e:
        return {"ok": False, "message": str(e)}
