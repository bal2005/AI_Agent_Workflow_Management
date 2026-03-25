"""
Scheduler integration test.
Run from backend/ with:
    python test_scheduler_setup.py

Tests:
  1. Redis connectivity
  2. Celery broker reachable
  3. poll_due_schedules task can be called directly
  4. A schedule with next_run_at in the past gets picked up
  5. ScheduleRun row is created in DB
"""
import os, sys, time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── 1. Redis ──────────────────────────────────────────────────────────────────
print("\n[1] Testing Redis connection...")
try:
    import redis
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    r.ping()
    print("    ✓ Redis is reachable")
except Exception as e:
    print(f"    ✗ Redis FAILED: {e}")
    print("      → Start Redis: docker run -d -p 6379:6379 redis:7-alpine")
    sys.exit(1)

# ── 2. Celery broker ──────────────────────────────────────────────────────────
print("\n[2] Testing Celery broker...")
try:
    from app.celery_app import celery
    conn = celery.connection()
    conn.ensure_connection(max_retries=3)
    conn.close()
    print("    ✓ Celery broker connected")
except Exception as e:
    print(f"    ✗ Celery broker FAILED: {e}")
    sys.exit(1)

# ── 3. DB connection ──────────────────────────────────────────────────────────
print("\n[3] Testing DB connection...")
try:
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.execute(__import__("sqlalchemy").text("SELECT 1"))
    print("    ✓ Database connected")
except Exception as e:
    print(f"    ✗ DB FAILED: {e}")
    sys.exit(1)

# ── 4. Create a test schedule due NOW ─────────────────────────────────────────
print("\n[4] Creating test schedule due immediately...")
try:
    # Clean up any previous test schedule
    existing = db.query(models.Schedule).filter(models.Schedule.name == "__test_scheduler__").first()
    if existing:
        db.delete(existing)
        db.commit()

    schedule = models.Schedule(
        name="__test_scheduler__",
        description="Auto-created by test_scheduler_setup.py",
        trigger_type="interval",
        interval_value=1,
        interval_unit="minutes",
        is_active=True,
        next_run_at=datetime.now(timezone.utc) - timedelta(seconds=10),  # already due
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    print(f"    ✓ Schedule created: id={schedule.id}, next_run_at={schedule.next_run_at}")
except Exception as e:
    print(f"    ✗ Schedule creation FAILED: {e}")
    sys.exit(1)

# ── 5. Call poll_due_schedules directly ───────────────────────────────────────
print("\n[5] Calling poll_due_schedules() directly (no Celery worker needed)...")
try:
    from app.scheduler_tasks import poll_due_schedules
    result = poll_due_schedules()
    print(f"    ✓ poll_due_schedules returned: {result}")
    if schedule.id in result.get("fired", []):
        print(f"    ✓ Schedule {schedule.id} was fired!")
    else:
        print(f"    ⚠ Schedule {schedule.id} was NOT in fired list: {result}")
except Exception as e:
    print(f"    ✗ poll_due_schedules FAILED: {e}")

# ── 6. Check ScheduleRun was created ─────────────────────────────────────────
print("\n[6] Checking ScheduleRun was created in DB...")
time.sleep(2)
try:
    db.expire_all()
    run = db.query(models.ScheduleRun).filter(
        models.ScheduleRun.schedule_id == schedule.id
    ).order_by(models.ScheduleRun.id.desc()).first()

    if run:
        print(f"    ✓ ScheduleRun found: id={run.id}, status={run.status}, triggered_by={run.triggered_by}")
    else:
        print("    ⚠ No ScheduleRun found yet (worker may still be processing)")
        print("      → If Celery worker is running, check its logs")
        print("      → If no worker, run_schedule was queued in Redis but not executed")
except Exception as e:
    print(f"    ✗ DB check FAILED: {e}")

# ── 7. Verify beat_schedule config ───────────────────────────────────────────
print("\n[7] Verifying Celery Beat config...")
from app.celery_app import celery as celery_app
beat = celery_app.conf.beat_schedule
if "poll-due-schedules-every-minute" in beat:
    entry = beat["poll-due-schedules-every-minute"]
    print(f"    ✓ Beat entry found: task={entry['task']}, schedule={entry['schedule']}s")
else:
    print("    ✗ Beat entry missing!")

# ── Cleanup ───────────────────────────────────────────────────────────────────
print("\n[8] Cleaning up test schedule...")
try:
    db.delete(schedule)
    db.commit()
    print("    ✓ Test schedule deleted")
except Exception:
    pass
finally:
    db.close()

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("""
To run the full scheduler:

  Option A — Docker (recommended, single container):
    docker build -t agent-studio ./backend
    docker run -d -p 8000:8000 --name agent-studio agent-studio
    docker logs -f agent-studio

  Option B — Local (3 terminals):
    Terminal 1: uvicorn app.main:app --reload
    Terminal 2: celery -A app.celery_app worker --loglevel=info
    Terminal 3: celery -A app.celery_app beat   --loglevel=info

  Check Beat is firing:
    docker exec agent-studio tail -f /var/log/supervisor/celery-beat.log

  Check Worker is executing:
    docker exec agent-studio tail -f /var/log/supervisor/celery-worker.log

  Check all processes:
    docker exec agent-studio supervisorctl status
""")
