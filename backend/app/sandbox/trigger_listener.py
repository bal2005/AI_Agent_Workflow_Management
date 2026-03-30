"""
Trigger Listener — monitors for events that should start a workflow run.

Three trigger sources:
  1. FileWatcher   — uses watchdog to detect file create/modify in a directory
  2. CronTrigger   — already handled by Celery Beat (poll_due_schedules)
  3. WebhookTrigger — FastAPI route that accepts POST /triggers/webhook/{token}

When a trigger fires:
  - The trigger is mapped to a schedule_id via the DB
  - run_schedule.delay(schedule_id, triggered_by) is called
  - A 1-second debounce prevents duplicate fires for the same schedule

Usage (start file watcher as a background thread):
    listener = FileWatcherListener(db_session_factory=SessionLocal)
    listener.start()
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Optional

from app.sandbox.logging_config import get_logger

log = get_logger("trigger_listener")

# Debounce window in seconds — ignore duplicate triggers within this window
DEBOUNCE_SECONDS = 1.0


class TriggerDebouncer:
    """
    Prevents the same schedule from being triggered multiple times
    within DEBOUNCE_SECONDS (e.g. a file save that fires multiple events).
    """
    def __init__(self):
        self._last_fired: dict[int, float] = {}
        self._lock = threading.Lock()

    def should_fire(self, schedule_id: int) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_fired.get(schedule_id, 0)
            if now - last < DEBOUNCE_SECONDS:
                return False
            self._last_fired[schedule_id] = now
            return True


_debouncer = TriggerDebouncer()


def _dispatch_trigger(schedule_id: int, triggered_by: str, metadata: dict) -> None:
    """
    Central dispatch: enqueue a workflow run for the given schedule.
    Called by all trigger sources.
    """
    if not _debouncer.should_fire(schedule_id):
        log.debug(f"Debounced trigger for schedule {schedule_id}")
        return

    log.info(
        f"Trigger fired → schedule {schedule_id}",
        extra={"trigger": triggered_by, "metadata": str(metadata)},
    )

    try:
        from app.scheduler_tasks import run_schedule
        run_schedule.delay(schedule_id, triggered_by)
        log.info(f"Workflow enqueued for schedule {schedule_id}")
    except Exception as e:
        log.error(f"Failed to enqueue workflow for schedule {schedule_id}: {e}")


# ── 1. File Watcher ───────────────────────────────────────────────────────────

class FileWatcherListener:
    """
    Watches a directory for file create/modify events.
    Maps watched paths to schedule IDs via the database.

    Requires: pip install watchdog
    """

    def __init__(self, db_session_factory):
        self._db_factory = db_session_factory
        self._observer   = None

    def start(self) -> None:
        """Start the file watcher in a background thread."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            log.warning("watchdog not installed — file trigger disabled. Run: pip install watchdog")
            return

        # Load all schedules that have a file_watch_path configured
        watched_paths = self._load_watched_paths()
        if not watched_paths:
            log.info("No file-watch triggers configured")
            return

        observer = Observer()

        for watch_path, schedule_ids in watched_paths.items():
            handler = _FileEventHandler(watch_path, schedule_ids)
            observer.schedule(handler, str(watch_path), recursive=False)
            log.info(f"Watching {watch_path} → schedules {schedule_ids}")

        observer.start()
        self._observer = observer
        log.info("File watcher started")

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def _load_watched_paths(self) -> dict:
        """
        Query DB for schedules that have trigger_type='file_watch'.
        Returns { Path: [schedule_id, ...] }

        Note: file_watch trigger_type is a future extension — currently
        schedules use manual/interval/cron. This is the hook point.
        """
        from app import models
        db = self._db_factory()
        try:
            schedules = (
                db.query(models.Schedule)
                .filter(
                    models.Schedule.is_active == True,
                    models.Schedule.trigger_type == "file_watch",
                )
                .all()
            )
            result: dict = defaultdict(list)
            for s in schedules:
                if s.file_watch_path:
                    from pathlib import Path
                    result[Path(s.file_watch_path)].append(s.id)
            return dict(result)
        finally:
            db.close()


class _FileEventHandler:
    """watchdog event handler — fires trigger on file create/modify."""

    def __init__(self, watch_path, schedule_ids: list[int]):
        # Import here to avoid hard dependency at module level
        from watchdog.events import FileSystemEventHandler as Base
        self._schedule_ids = schedule_ids
        self._watch_path   = watch_path

        # Dynamically create a proper subclass
        outer = self

        class _Handler(Base):
            def on_created(self, event):
                if not event.is_directory:
                    outer._on_event("file_created", event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    outer._on_event("file_modified", event.src_path)

        self._handler = _Handler()

    def _on_event(self, event_type: str, src_path: str) -> None:
        log.info(f"File event: {event_type} {src_path}")
        for schedule_id in self._schedule_ids:
            _dispatch_trigger(
                schedule_id,
                triggered_by=f"file_{event_type}",
                metadata={"path": src_path},
            )

    # Delegate watchdog protocol to inner handler
    def dispatch(self, event):
        self._handler.dispatch(event)


# ── 2. Webhook Trigger (FastAPI route) ────────────────────────────────────────

def make_webhook_router():
    """
    Returns a FastAPI router with a webhook endpoint.
    Mount this in main.py: app.include_router(make_webhook_router())

    POST /triggers/webhook/{token}
    Body: { "schedule_id": 5, "metadata": {...} }  (optional)
    """
    from fastapi import APIRouter, HTTPException, Request
    from app import models
    from app.database import get_db
    from fastapi import Depends
    from sqlalchemy.orm import Session

    router = APIRouter(prefix="/triggers", tags=["triggers"])

    @router.post("/webhook/{token}")
    async def webhook_trigger(
        token: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        """
        Accepts a webhook POST and fires the matching schedule.
        The token is matched against schedule.webhook_token in the DB.
        """
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        # Find schedule by webhook token
        schedule = (
            db.query(models.Schedule)
            .filter(
                models.Schedule.webhook_token == token,
                models.Schedule.is_active == True,
            )
            .first()
        )
        if not schedule:
            raise HTTPException(status_code=404, detail="No active schedule for this token")

        _dispatch_trigger(
            schedule.id,
            triggered_by="webhook",
            metadata={"token": token, "body": body},
        )
        return {"status": "queued", "schedule_id": schedule.id}

    return router
