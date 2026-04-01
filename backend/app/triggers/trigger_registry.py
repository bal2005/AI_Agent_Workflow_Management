"""
TriggerRegistry — manages all active filesystem listeners.

Maintains a dict of { schedule_id: FilesystemListener }.
Called by:
  - app startup (load all active filesystem triggers from DB)
  - schedule save/update (reload the specific trigger)
  - schedule delete (stop the listener)
  - app shutdown (stop all listeners)

Thread-safe: uses a lock for all mutations.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

log = logging.getLogger("triggers.registry")


class TriggerRegistry:
    """Singleton registry of all active filesystem listeners."""

    def __init__(self):
        self._listeners: dict[int, object] = {}  # schedule_id → FilesystemListener
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_all(self) -> None:
        """Load all active filesystem triggers from DB and start listeners."""
        try:
            from app.database import SessionLocal
            from app import models
            db = SessionLocal()
            try:
                schedules = (
                    db.query(models.Schedule)
                    .filter(
                        models.Schedule.trigger_type == "filesystem",
                        models.Schedule.is_active == True,
                    )
                    .all()
                )
                log.info(f"[registry] loading {len(schedules)} filesystem trigger(s)")
                for s in schedules:
                    config = s.trigger_config or {}
                    if config.get("enabled", True):
                        self._start(s.id, config)
            finally:
                db.close()
        except Exception as e:
            log.error(f"[registry] failed to load triggers: {e}")

    def stop_all(self) -> None:
        """Stop all active listeners (called on app shutdown)."""
        with self._lock:
            for sid, listener in list(self._listeners.items()):
                listener.stop()
            self._listeners.clear()
        log.info("[registry] all listeners stopped")

    # ── Per-schedule operations ───────────────────────────────────────────────

    def reload(self, schedule_id: int) -> None:
        """
        Reload the listener for a specific schedule.
        Called after a schedule is created or updated.
        Reads the latest config from DB.
        """
        try:
            from app.database import SessionLocal
            from app import models
            db = SessionLocal()
            try:
                s = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
                if not s:
                    self.stop_one(schedule_id)
                    return

                if s.trigger_type != "filesystem" or not s.is_active:
                    self.stop_one(schedule_id)
                    return

                config = s.trigger_config or {}
                if not config.get("enabled", True):
                    self.stop_one(schedule_id)
                    return

                self._restart(schedule_id, config)
            finally:
                db.close()
        except Exception as e:
            log.error(f"[registry] reload failed for schedule {schedule_id}: {e}")

    def stop_one(self, schedule_id: int) -> None:
        """Stop and remove the listener for a specific schedule."""
        with self._lock:
            listener = self._listeners.pop(schedule_id, None)
            if listener:
                listener.stop()
                log.info(f"[registry] stopped listener for schedule {schedule_id}")

    def status(self) -> list[dict]:
        """Return status of all registered listeners (for API/UI)."""
        with self._lock:
            return [
                {
                    "schedule_id": sid,
                    "running": listener.is_running,
                    "watch_path": listener.config.get("watch_path"),
                }
                for sid, listener in self._listeners.items()
            ]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _start(self, schedule_id: int, config: dict) -> None:
        from app.triggers.filesystem_listener import FilesystemListener
        with self._lock:
            # Stop existing if any
            existing = self._listeners.get(schedule_id)
            if existing:
                existing.stop()
            listener = FilesystemListener(schedule_id, config)
            if listener.start():
                self._listeners[schedule_id] = listener
            else:
                log.warning(f"[registry] listener for schedule {schedule_id} did not start")

    def _restart(self, schedule_id: int, config: dict) -> None:
        from app.triggers.filesystem_listener import FilesystemListener
        with self._lock:
            existing = self._listeners.get(schedule_id)
            if existing:
                existing.restart(config)
                log.info(f"[registry] restarted listener for schedule {schedule_id}")
            else:
                listener = FilesystemListener(schedule_id, config)
                if listener.start():
                    self._listeners[schedule_id] = listener


# Global singleton — imported by main.py and schedule router
registry = TriggerRegistry()
