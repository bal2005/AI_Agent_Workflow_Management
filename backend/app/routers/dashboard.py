"""
Dashboard Router
================
GET /dashboard/summary  — all KPIs, recent runs, and operational metrics in one call
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, case
from app import models
from app.database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    """
    Returns everything the dashboard needs in a single efficient query set.
    Designed to be called once on page load.
    """
    now = datetime.now(timezone.utc)
    today_start  = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start   = today_start - timedelta(days=today_start.weekday())

    # ── Entity counts ─────────────────────────────────────────────────────────
    agent_count    = db.query(func.count(models.Agent.id)).scalar() or 0
    task_count     = db.query(func.count(models.Task.id)).scalar() or 0
    schedule_count = db.query(func.count(models.Schedule.id)).scalar() or 0
    domain_count   = db.query(func.count(models.Domain.id)).scalar() or 0

    active_schedules   = db.query(func.count(models.Schedule.id)).filter(models.Schedule.is_active == True).scalar() or 0
    inactive_schedules = schedule_count - active_schedules

    # Schedules that have a workflow_json with nodes
    workflow_count = db.query(func.count(models.Schedule.id)).filter(
        models.Schedule.workflow_json.isnot(None)
    ).scalar() or 0

    # ── Schedule run stats ────────────────────────────────────────────────────
    total_schedule_runs = db.query(func.count(models.ScheduleRun.id)).scalar() or 0

    sr_stats = db.query(
        models.ScheduleRun.status,
        func.count(models.ScheduleRun.id).label("cnt")
    ).group_by(models.ScheduleRun.status).all()
    sr_by_status = {row.status: row.cnt for row in sr_stats}

    runs_today = db.query(func.count(models.ScheduleRun.id)).filter(
        models.ScheduleRun.created_at >= today_start
    ).scalar() or 0

    runs_this_week = db.query(func.count(models.ScheduleRun.id)).filter(
        models.ScheduleRun.created_at >= week_start
    ).scalar() or 0

    # Average duration from ScheduleTaskRun (most granular timing)
    avg_duration_row = db.query(
        func.avg(models.ScheduleTaskRun.duration_seconds)
    ).filter(
        models.ScheduleTaskRun.duration_seconds.isnot(None),
        models.ScheduleTaskRun.status == "success",
    ).scalar()
    avg_duration = round(float(avg_duration_row), 1) if avg_duration_row else None

    # Success rate
    success_count = sr_by_status.get("success", 0)
    failed_count  = sr_by_status.get("failed", 0)
    success_rate  = round(success_count / total_schedule_runs * 100, 1) if total_schedule_runs > 0 else None

    # ── Recent schedule runs (last 5) ─────────────────────────────────────────
    recent_schedule_runs_raw = (
        db.query(models.ScheduleRun)
        .options(
            joinedload(models.ScheduleRun.schedule),
            joinedload(models.ScheduleRun.task_runs).joinedload(models.ScheduleTaskRun.task),
        )
        .order_by(models.ScheduleRun.created_at.desc())
        .limit(5)
        .all()
    )

    recent_schedule_runs = []
    for r in recent_schedule_runs_raw:
        duration = None
        if r.started_at and r.finished_at:
            duration = round((r.finished_at - r.started_at).total_seconds(), 1)
        recent_schedule_runs.append({
            "id":            r.id,
            "schedule_name": r.schedule.name if r.schedule else f"Schedule #{r.schedule_id}",
            "status":        r.status,
            "triggered_by":  r.triggered_by,
            "started_at":    r.started_at.isoformat() if r.started_at else None,
            "finished_at":   r.finished_at.isoformat() if r.finished_at else None,
            "duration_s":    duration,
            "task_count":    len(r.task_runs),
            "error":         r.error,
            "task_runs": [
                {
                    "id":         tr.id,
                    "task_name":  tr.task.name if tr.task else f"Task #{tr.task_id}",
                    "status":     tr.status,
                    "duration_s": tr.duration_seconds,
                    "started_at": tr.started_at.isoformat() if tr.started_at else None,
                    "output":     tr.output,
                    "logs":       tr.logs or [],
                }
                for tr in r.task_runs
            ],
        })

    # ── Recent task runs (last 5 from ScheduleTaskRun — most granular) ────────
    recent_task_runs_raw = (
        db.query(models.ScheduleTaskRun)
        .options(
            joinedload(models.ScheduleTaskRun.task).joinedload(models.Task.agent),
            joinedload(models.ScheduleTaskRun.run).joinedload(models.ScheduleRun.schedule),
        )
        .filter(models.ScheduleTaskRun.status.in_(["success", "failed"]))
        .order_by(models.ScheduleTaskRun.started_at.desc())
        .limit(5)
        .all()
    )

    recent_task_runs = []
    for tr in recent_task_runs_raw:
        recent_task_runs.append({
            "id":            tr.id,
            "run_id":        tr.run_id,
            "task_name":     tr.task.name if tr.task else f"Task #{tr.task_id}",
            "agent_name":    tr.task.agent.name if (tr.task and tr.task.agent) else None,
            "schedule_name": tr.run.schedule.name if (tr.run and tr.run.schedule) else None,
            "status":        tr.status,
            "started_at":    tr.started_at.isoformat() if tr.started_at else None,
            "finished_at":   tr.finished_at.isoformat() if tr.finished_at else None,
            "duration_s":    tr.duration_seconds,
            "output":        tr.output,
            "logs":          tr.logs or [],
        })

    # ── Quick insights ────────────────────────────────────────────────────────
    # Most recently run schedule
    last_run = recent_schedule_runs[0] if recent_schedule_runs else None

    # Recent failures (last 24h)
    recent_failures = db.query(func.count(models.ScheduleRun.id)).filter(
        models.ScheduleRun.status == "failed",
        models.ScheduleRun.created_at >= now - timedelta(hours=24),
    ).scalar() or 0

    # Tasks assigned to at least one schedule
    tasks_in_schedules = db.query(func.count(func.distinct(models.ScheduleTask.task_id))).scalar() or 0

    # Run trend: last 7 days, count per day
    run_trend = []
    for i in range(6, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end   = day_start + timedelta(days=1)
        cnt = db.query(func.count(models.ScheduleRun.id)).filter(
            models.ScheduleRun.created_at >= day_start,
            models.ScheduleRun.created_at < day_end,
        ).scalar() or 0
        run_trend.append({
            "date":  day_start.strftime("%m/%d"),
            "runs":  cnt,
        })

    # Status breakdown for chart
    status_breakdown = [
        {"status": "success", "count": sr_by_status.get("success", 0)},
        {"status": "failed",  "count": sr_by_status.get("failed", 0)},
        {"status": "running", "count": sr_by_status.get("running", 0)},
        {"status": "pending", "count": sr_by_status.get("pending", 0)},
    ]

    return {
        # Entity counts
        "agents":             agent_count,
        "tasks":              task_count,
        "schedules":          schedule_count,
        "domains":            domain_count,
        "workflows":          workflow_count,
        "active_schedules":   active_schedules,
        "inactive_schedules": inactive_schedules,

        # Run counts
        "total_schedule_runs": total_schedule_runs,
        "successful_runs":     success_count,
        "failed_runs":         failed_count,
        "runs_today":          runs_today,
        "runs_this_week":      runs_this_week,

        # Computed metrics
        "success_rate":        success_rate,
        "avg_duration_s":      avg_duration,

        # Recent activity
        "recent_schedule_runs": recent_schedule_runs,
        "recent_task_runs":     recent_task_runs,

        # Quick insights
        "recent_failures_24h":  recent_failures,
        "tasks_in_schedules":   tasks_in_schedules,
        "last_run":             last_run,

        # Chart data
        "run_trend":        run_trend,
        "status_breakdown": status_breakdown,
    }
