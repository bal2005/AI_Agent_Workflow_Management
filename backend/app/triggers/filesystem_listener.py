"""
FilesystemListener — one watchdog Observer per schedule trigger.

Each schedule with trigger_type="filesystem" gets its own Observer thread
watching the configured path. When an event fires:
  1. TriggerMatcher checks if it matches the rules
  2. Debouncer suppresses rapid duplicate events
  3. A TriggerLog entry is written to the DB
  4. run_schedule.delay() is called to execute the workflow

The event handler never executes workflow logic directly — it only
enqueues a Celery task, keeping the handler fast and non-blocking.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.triggers.trigger_matcher import matches, event_type_str

log = logging.getLogger("triggers.filesystem")


class Debouncer:
    """
    Prevents the same schedule from firing multiple times within a short window.
    Thread-safe using a lock.
    """
    def __init__(self):
        self._last: dict[int, float] = {}
        self._lock = threading.Lock()

    def should_fire(self, schedule_id: int, debounce_seconds: float) -> bool:
        """Return True if enough time has passed since the last fire."""
        now = time.monotonic()
        with self._lock:
            last = self._last.get(schedule_id, 0.0)
            if now - last < debounce_seconds:
                return False
            self._last[schedule_id] = now
            return True

    def reset(self, schedule_id: int) -> None:
        with self._lock:
            self._last.pop(schedule_id, None)


# Global debouncer shared across all listeners
_debouncer = Debouncer()


class FileTriggerHandler:
    """
    watchdog event handler for one schedule trigger.

    Receives all filesystem events for the watched path and:
    - filters them through TriggerMatcher
    - applies debounce
    - writes a TriggerLog
    - fires run_schedule.delay()
    """

    def __init__(self, schedule_id: int, config: dict):
        self.schedule_id = schedule_id
        self.config = config
        self.debounce_seconds = float(config.get("debounce_seconds", 3))

    def dispatch(self, event) -> None:
        """Called by watchdog for every filesystem event."""
        matched, reason = matches(event, self.config)
        evt_type = event_type_str(event)
        path_str = getattr(event, "dest_path", None) or getattr(event, "src_path", "")

        log.debug(f"[schedule={self.schedule_id}] event={evt_type} path={path_str} → {reason}")

        if not matched:
            self._write_log(evt_type, path_str, matched=False, debounced=False,
                            workflow_fired=False, notes=reason)
            return

        # Debounce check
        if not _debouncer.should_fire(self.schedule_id, self.debounce_seconds):
            log.info(f"[schedule={self.schedule_id}] debounced: {path_str}")
            self._write_log(evt_type, path_str, matched=True, debounced=True,
                            workflow_fired=False, notes=f"debounced ({self.debounce_seconds}s window)")
            return

        # Fire the workflow
        log.info(f"[schedule={self.schedule_id}] TRIGGER FIRED: {evt_type} on {path_str}")
        self._write_log(evt_type, path_str, matched=True, debounced=False,
                        workflow_fired=True, notes=reason)
        self._fire_workflow(evt_type, path_str)

    def _fire_workflow(self, evt_type: str, path_str: str) -> None:
        """Enqueue the workflow via Celery — never execute inline."""
        try:
            from app.scheduler_tasks import run_schedule
            run_schedule.delay(self.schedule_id, "filesystem")
            log.info(f"[schedule={self.schedule_id}] workflow enqueued (filesystem trigger)")
        except Exception as e:
            log.error(f"[schedule={self.schedule_id}] failed to enqueue workflow: {e}")

    def _write_log(self, evt_type: str, path_str: str,
                   matched: bool, debounced: bool, workflow_fired: bool, notes: str) -> None:
        """Write a TriggerLog entry. Uses a short-lived DB session."""
        try:
            from app.database import SessionLocal
            from app import models
            db = SessionLocal()
            try:
                entry = models.TriggerLog(
                    schedule_id=self.schedule_id,
                    event_type=evt_type,
                    file_path=path_str[:1000] if path_str else None,
                    matched=matched,
                    debounced=debounced,
                    workflow_fired=workflow_fired,
                    notes=notes[:500] if notes else None,
                    triggered_at=datetime.now(timezone.utc),
                )
                db.add(entry)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            log.warning(f"[schedule={self.schedule_id}] could not write trigger log: {e}")


class FilesystemListener:
    """
    Manages one watchdog Observer for a single schedule trigger.

    Lifecycle:
      start()  → creates Observer, attaches handler, begins watching
      stop()   → stops Observer thread cleanly
      restart() → stop + start (used when config changes)
    """

    def __init__(self, schedule_id: int, config: dict):
        self.schedule_id = schedule_id
        self.config = config
        self._observer = None

    def start(self) -> bool:
        """
        Start watching. Returns True on success, False if path doesn't exist.

        Uses PollingObserver by default — inotify/FSEvents are unreliable on
        Docker Desktop bind mounts (the kernel events never reach the container).
        Polling adds a small latency (~5s) but is 100% reliable across platforms.
        """
        try:
            from watchdog.observers.polling import PollingObserver
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            log.error("watchdog not installed. Run: pip install watchdog")
            return False

        watch_path = self.config.get("watch_path", "")
        if not watch_path:
            log.warning(f"[schedule={self.schedule_id}] no watch_path configured")
            return False

        path = Path(watch_path)
        if not path.exists():
            log.warning(f"[schedule={self.schedule_id}] watch path does not exist: {path}")

        recursive = bool(self.config.get("recursive", True))
        handler = FileTriggerHandler(self.schedule_id, self.config)

        # Wrap our handler in a watchdog-compatible class
        class _WatchdogAdapter(FileSystemEventHandler):
            def __init__(self, inner):
                self._inner = inner
            def dispatch(self, event):
                self._inner.dispatch(event)

        observer = PollingObserver()
        try:
            observer.schedule(_WatchdogAdapter(handler), str(path), recursive=recursive)
        except Exception as e:
            log.error(f"[schedule={self.schedule_id}] failed to schedule observer: {e}")
            return False

        observer.start()
        self._observer = observer
        log.info(f"[schedule={self.schedule_id}] polling {path} (recursive={recursive})")
        return True

    def stop(self) -> None:
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception as e:
                log.warning(f"[schedule={self.schedule_id}] error stopping observer: {e}")
            self._observer = None
            log.info(f"[schedule={self.schedule_id}] observer stopped")

    def restart(self, new_config: dict) -> bool:
        self.stop()
        self.config = new_config
        _debouncer.reset(self.schedule_id)
        return self.start()

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
