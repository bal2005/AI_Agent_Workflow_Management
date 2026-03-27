"""
Celery tasks for the scheduler.
run_schedule(schedule_id) — fetches schedule, runs tasks sequentially via
workflow_runner, records ScheduleRun + ScheduleTaskRun rows.
"""
import time
from datetime import datetime, timezone

from app.celery_app import celery
from app.database import SessionLocal
from app import models


@celery.task(bind=True, name="app.scheduler_tasks.run_schedule")
def run_schedule(self, schedule_id: int, triggered_by: str = "scheduler"):
    db = SessionLocal()
    try:
        schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
        if not schedule:
            return {"error": f"Schedule {schedule_id} not found"}

        # Snapshot task_id + position as plain values immediately.
        # Do NOT hold references to ScheduleTask ORM objects across commits —
        # _sync_tasks deletes and re-inserts rows, which detaches those instances.
        ordered_task_refs = [
            (st.task_id, st.position)
            for st in sorted(schedule.schedule_tasks, key=lambda st: st.position)
        ]

        # Create ScheduleRun record
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
        # Workflow context: accumulates prior task outputs for data flow
        workflow_context: dict[int, dict] = {}  # position → structured result

        for task_id, position in ordered_task_refs:
            task = db.query(models.Task).filter(models.Task.id == task_id).first()
            if not task:
                continue

            # Eagerly load agent + domain
            if task.agent_id:
                from sqlalchemy.orm import joinedload
                task.agent = (
                    db.query(models.Agent)
                    .options(joinedload(models.Agent.domain))
                    .filter(models.Agent.id == task.agent_id)
                    .first()
                )

            # Resolve prior task output for data flow
            prior_output: str | None = None
            if workflow_context:
                last_pos = max(workflow_context.keys())
                prior_result = workflow_context[last_pos]
                prior_output = prior_result.get("final_text", "")

            task_run = models.ScheduleTaskRun(
                run_id=run.id,
                task_id=task.id,
                position=position,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(task_run)
            db.commit()
            db.refresh(task_run)

            t_start = time.time()
            try:
                from app.workflow_runner import run_task_in_workflow
                result = run_task_in_workflow(task, db, prior_output=prior_output)

                if result.get("success"):
                    task_run.status = "success"
                else:
                    task_run.status = "failed"
                    overall_status = "failed"
                    run_error = result.get("error", "Task returned failure")

                task_run.output = result.get("final_text", "")
                task_run.logs = result.get("logs", [])
                workflow_context[st.position] = result

            except Exception as e:
                task_run.status = "failed"
                task_run.output = str(e)
                task_run.logs = [f"Exception: {e}"]
                overall_status = "failed"
                run_error = str(e)

            task_run.finished_at = datetime.now(timezone.utc)
            task_run.duration_seconds = round(time.time() - t_start, 2)
            db.commit()

            # Phase 1 failure policy: stop on first failure
            if overall_status == "failed":
                break

        # Finalise run
        run.status = overall_status
        run.finished_at = datetime.now(timezone.utc)
        run.error = run_error
        _update_next_run(schedule)
        db.commit()

        return {"run_id": run.id, "status": overall_status}

    except Exception as e:
        try:
            run.status = "failed"
            run.error = str(e)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        db.close()


def _update_next_run(schedule: models.Schedule):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    if schedule.trigger_type == "interval" and schedule.interval_value:
        unit = schedule.interval_unit or "minutes"
        delta = {
            "minutes": timedelta(minutes=schedule.interval_value),
            "hours":   timedelta(hours=schedule.interval_value),
            "days":    timedelta(days=schedule.interval_value),
        }.get(unit, timedelta(minutes=schedule.interval_value))
        schedule.next_run_at = now + delta
    elif schedule.trigger_type == "cron" and schedule.cron_expression:
        try:
            from croniter import croniter
            schedule.next_run_at = croniter(schedule.cron_expression, now).get_next(datetime)
        except Exception:
            pass


@celery.task(name="app.scheduler_tasks.poll_due_schedules")
def poll_due_schedules():
    """Runs every 60s via Celery Beat. Fires run_schedule for all due schedules."""
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
            _update_next_run(schedule)
            db.commit()
            run_schedule.delay(schedule.id, "scheduler")
            fired.append(schedule.id)
        return {"fired": fired, "count": len(fired)}
    finally:
        db.close()
