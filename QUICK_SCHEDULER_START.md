# Quick Scheduler Start Guide

## 30-Second Setup

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Start backend
uvicorn app.main:app --reload

# 3. Open frontend
# http://localhost:5173
```

## 5-Minute Test

1. **Create a task** (if needed):
   - Go to "Task Creation" page
   - Create a simple task

2. **Create a schedule:**
   - Go to "Task Scheduler" page
   - Click ＋ button
   - Name: "Test"
   - Trigger: Manual
   - Add your task
   - Click "Create Schedule"

3. **Run it:**
   - Click "Run Now" button
   - See run history populate

## Test Interval Schedules (Without Celery)

```bash
# 1. Create interval schedule via UI
# Trigger: Interval, Value: 5, Unit: minutes

# 2. Wait 5+ minutes

# 3. Manually trigger due schedules
curl -X POST http://localhost:8000/schedules/debug/trigger-all-due

# 4. Check run history in UI
```

## Full Automation (With Celery Beat)

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start backend
cd backend
uvicorn app.main:app --reload

# Terminal 3: Start Celery worker
cd backend
celery -A app.celery_app worker --loglevel=info

# Terminal 4: Start Celery Beat
cd backend
celery -A app.celery_app beat --loglevel=info
```

Then:
1. Create interval schedule via UI
2. Wait for next_run_at time
3. Beat automatically triggers execution
4. Run history updates

## Debug Endpoints

```bash
# Check schedule status
curl http://localhost:8000/schedules/debug/status

# Manually trigger all due schedules
curl -X POST http://localhost:8000/schedules/debug/trigger-all-due

# List all schedules
curl http://localhost:8000/schedules/

# Get schedule detail
curl http://localhost:8000/schedules/1

# Get run history
curl http://localhost:8000/schedules/1/runs
```

## Trigger Types

| Type | Auto-Trigger | Config | Example |
|------|--------------|--------|---------|
| Manual | ❌ | None | Click "Run Now" |
| Interval | ✓ (with Beat) | Value + Unit | Every 5 minutes |
| Cron | ✓ (with Beat) | Expression | `*/5 * * * *` |

## Common Issues

| Issue | Solution |
|-------|----------|
| "Schedule not triggering" | Start Celery Beat: `celery -A app.celery_app beat --loglevel=info` |
| "Redis connection refused" | Start Redis: `redis-server` |
| "croniter not found" | Install: `pip install croniter==2.0.1` |
| "Task fails silently" | Check Celery worker logs for errors |

## Files to Know

- **Frontend:** `frontend/src/components/SchedulerPage.jsx`
- **Backend API:** `backend/app/routers/schedules.py`
- **Celery Task:** `backend/app/scheduler_tasks.py`
- **Database:** `backend/alembic/versions/005_scheduler.py`
- **Config:** `backend/.env` (REDIS_URL)

## What's Working ✓

- ✓ Create schedules (manual/interval/cron)
- ✓ Attach tasks to schedules
- ✓ Manual "Run Now" execution
- ✓ Run history tracking
- ✓ Debug endpoints for testing

## What's Missing ❌

- ❌ Automatic triggering (requires Celery Beat running)
- ❌ DB-backed Beat scheduler (Phase 2)

## Next Steps

1. Test manual runs (works now)
2. Test interval schedules with debug endpoint
3. Start Celery Beat for full automation
4. Implement Phase 2 (DB-backed scheduler)
