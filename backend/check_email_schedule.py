from app.database import SessionLocal
from app import models
from datetime import datetime, timezone

db = SessionLocal()
now = datetime.now(timezone.utc)
schedules = db.query(models.Schedule).filter(models.Schedule.trigger_type == "email_imap").all()
print(f"Found {len(schedules)} email_imap schedule(s)")
for s in schedules:
    cfg = s.trigger_config or {}
    print(f"\nid={s.id} name={s.name} active={s.is_active}")
    print(f"  next_run_at={s.next_run_at}")
    if s.next_run_at:
        diff = (s.next_run_at - now).total_seconds()
        print(f"  due_in={diff:.0f}s ({'OVERDUE' if diff < 0 else 'not yet due'})")
    else:
        print("  next_run_at=None — will be skipped by poll_email_triggers!")
    print(f"  enabled={cfg.get('enabled')} host={cfg.get('host')} user={cfg.get('username')} has_pw={bool(cfg.get('password'))}")
    print(f"  poll_interval_minutes={cfg.get('poll_interval_minutes', 5)}")

# Also check recent trigger logs
logs = db.query(models.TriggerLog).filter(models.TriggerLog.event_type == "email").order_by(models.TriggerLog.triggered_at.desc()).limit(5).all()
print(f"\nRecent email trigger logs ({len(logs)}):")
for l in logs:
    print(f"  schedule={l.schedule_id} matched={l.matched} fired={l.workflow_fired} notes={l.notes} at={l.triggered_at}")

db.close()
