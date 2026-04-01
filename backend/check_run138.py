from app.database import SessionLocal
from app import models
db = SessionLocal()
run = db.query(models.ScheduleRun).filter_by(id=138).first()
print("Run error:", run.error)
for tr in run.task_runs:
    print(f"\nTask: {tr.task.name} status={tr.status}")
    print("Output:", (tr.output or "")[:300])
    print("Logs:", tr.logs[:3] if tr.logs else [])
db.close()
