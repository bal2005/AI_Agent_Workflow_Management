"""
Celery application instance.
On Windows use --pool=solo (no multiprocessing).
On Linux/Docker use default prefork or gevent.

  Local Windows:
    celery -A app.celery_app worker --pool=solo --loglevel=info
    celery -A app.celery_app beat   --loglevel=info

  Docker (Linux):
    celery -A app.celery_app worker --loglevel=info --concurrency=2
    celery -A app.celery_app beat   --loglevel=info
"""
import os
import sys
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "agent_studio",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.scheduler_tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # On Windows, solo pool avoids the billiard PermissionError
    worker_pool="solo" if sys.platform == "win32" else "prefork",
    beat_schedule={
        "poll-due-schedules-every-minute": {
            "task": "app.scheduler_tasks.poll_due_schedules",
            "schedule": 60.0,
        },
    },
)
