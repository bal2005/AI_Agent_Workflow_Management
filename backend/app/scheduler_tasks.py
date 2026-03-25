"""
Celery tasks for the scheduler.
run_schedule(schedule_id) — fetches schedule, runs tasks sequentially,
records ScheduleRun + ScheduleTaskRun rows.
"""
import time
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.celery_app import celery
from app.database import SessionLocal
from app import models
from app.crypto import decrypt


def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _resolve_cfg(task: models.Task, db) -> SimpleNamespace:
    """Build a plain config namespace for the LLM runner."""
    if task.llm_config_id:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.id == task.llm_config_id).first()
    else:
        cfg = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()

    if not cfg:
        raise RuntimeError("No active LLM config found")

    return SimpleNamespace(
        provider=task.llm_provider or cfg.provider,
        base_url=cfg.base_url,
        api_key=decrypt(cfg.api_key) if cfg.api_key else "",
        model_name=task.llm_model or cfg.model_name,
        temperature=task.llm_temperature if task.llm_temperature is not None else cfg.temperature,
        max_tokens=task.llm_max_tokens if task.llm_max_tokens is not None else cfg.max_tokens,
        top_p=task.llm_top_p if task.llm_top_p is not None else cfg.top_p,
        top_k=cfg.top_k,
    )


def _run_task_sync(task: models.Task, db) -> tuple[str, list[str]]:
    """Execute a single task synchronously, return (result, steps)."""
    from pathlib import Path
    from app.routers.task_playground import _build_fs_tools, _run_agent_loop

    cfg = _resolve_cfg(task, db)

    skill = task.agent.system_prompt if task.agent else ""
    if task.llm_system_behavior:
        skill = skill + "\n\n" + task.llm_system_behavior
    skill = skill.strip() or "You are a helpful assistant."

    task_text = task.description
    if task.workflow and task.workflow.strip():
        task_text += f"\n\nFollow these steps:\n{task.workflow}"
    if task.folder_path:
        task_text += f"\n\nWorking directory: {task.folder_path}"

    tools = []
    if task.tool_usage_mode != "none" and task.folder_path:
        root = Path(task.folder_path)
        if root.exists() and root.is_dir():
            perms = ["read_files", "browse_folders"]
            if task.tool_usage_mode == "allowed":
                perms += ["write_files"]
            tools = _build_fs_tools(root, perms)

    root_path = Path(task.folder_path) if task.folder_path else Path(".")
    result, steps = asyncio.run(_run_agent_loop(cfg, skill, task_text, root_path, tools))
    return result, steps


@celery.task(bind=True, name="app.scheduler_tasks.run_schedule")
def run_schedule(self, schedule_id: int, triggered_by: str = "scheduler"):
    db = SessionLocal()
    try:
        # 1. Fetch schedule with tasks
        schedule = (
            db.query(models.Schedule)
            .filter(models.Schedule.id == schedule_id)
            .first()
        )
        if not schedule:
            return {"error": f"Schedule {schedule_id} not found"}

        ordered_tasks = sorted(schedule.schedule_tasks, key=lambda st: st.position)

        # 2. Create ScheduleRun
        run = models.ScheduleRun(
            schedule_id=schedule_id,
            status="running",
            triggered_by=triggered_by,
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        overall_status = "success"
        run_error = None

        # 3. Execute tasks sequentially
        for st in ordered_tasks:
            task = db.query(models.Task).filter(models.Task.id == st.task_id).first()
            if not task:
                continue

            # Eagerly load agent
            if task.agent_id:
                task.agent = db.query(models.Agent).filter(models.Agent.id == task.agent_id).first()

            task_run = models.ScheduleTaskRun(
                run_id=run.id,
                task_id=task.id,
                position=st.position,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(task_run)
            db.commit()
            db.refresh(task_run)

            t_start = time.time()
            try:
                result, steps = _run_task_sync(task, db)
                task_run.status = "success"
                task_run.output = result
                task_run.logs = steps
            except Exception as e:
                task_run.status = "failed"
                task_run.output = str(e)
                task_run.logs = []
                overall_status = "failed"
                run_error = str(e)

            task_run.finished_at = datetime.now(timezone.utc)
            task_run.duration_seconds = round(time.time() - t_start, 2)
            db.commit()

        # 4. Finalise run
        run.status = overall_status
        run.finished_at = datetime.now(timezone.utc)
        run.error = run_error

        # 5. Update next_run_at for interval/cron schedules
        _update_next_run(schedule)
        db.commit()

        return {"run_id": run.id, "status": overall_status}

    except Exception as e:
        if 'run' in dir() and run.id:
            run.status = "failed"
            run.error = str(e)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return {"error": str(e)}
    finally:
        db.close()


def _update_next_run(schedule: models.Schedule):
    """Compute and set next_run_at after a successful execution."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)

    if schedule.trigger_type == "interval" and schedule.interval_value:
        unit = schedule.interval_unit or "minutes"
        delta = {
            "minutes": timedelta(minutes=schedule.interval_value),
            "hours": timedelta(hours=schedule.interval_value),
            "days": timedelta(days=schedule.interval_value),
        }.get(unit, timedelta(minutes=schedule.interval_value))
        schedule.next_run_at = now + delta

    elif schedule.trigger_type == "cron" and schedule.cron_expression:
        try:
            from croniter import croniter
            cron = croniter(schedule.cron_expression, now)
            schedule.next_run_at = cron.get_next(datetime)
        except Exception:
            pass


@celery.task(name="app.scheduler_tasks.poll_due_schedules")
def poll_due_schedules():
    """
    Runs every 60 seconds via Celery Beat.
    Finds all active interval/cron schedules whose next_run_at <= now
    and dispatches run_schedule() for each one.
    Also advances next_run_at immediately (optimistic lock) so a second
    Beat tick within the same window won't double-fire.
    """
    from datetime import timedelta
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(models.Schedule)
            .filter(
                models.Schedule.is_active == True,
                models.Schedule.trigger_type != "manual",
                models.Schedule.next_run_at != None,
                models.Schedule.next_run_at <= now,
            )
            .all()
        )

        fired = []
        for schedule in due:
            # Advance next_run_at BEFORE dispatching so a concurrent poll
            # won't pick it up again.
            _update_next_run(schedule)
            db.commit()

            run_schedule.delay(schedule.id, "scheduler")
            fired.append(schedule.id)

        return {"fired": fired, "count": len(fired)}
    finally:
        db.close()
