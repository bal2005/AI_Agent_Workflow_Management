"""
TriggerMatcher — pure matching logic, no side effects.

Checks whether a watchdog filesystem event matches the rules
configured for a schedule's trigger_config.

trigger_config shape:
{
  "watch_path":        "/incoming",
  "recursive":         true,
  "events":            ["created", "modified"],   # any of: created|modified|deleted|moved
  "extension_filter":  [".pdf", ".txt"],           # null = all extensions
  "filename_pattern":  "report_*",                # null = all filenames (fnmatch)
  "debounce_seconds":  3,
  "enabled":           true,
  "target":            "file"                     # "file" | "folder" | "both"
}
"""
from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("triggers.matcher")

# Map watchdog event class names → our simple event type strings
_EVENT_TYPE_MAP = {
    "FileCreatedEvent":    "created",
    "FileModifiedEvent":   "modified",
    "FileDeletedEvent":    "deleted",
    "FileMovedEvent":      "moved",
    "DirCreatedEvent":     "created",
    "DirModifiedEvent":    "modified",
    "DirDeletedEvent":     "deleted",
    "DirMovedEvent":       "moved",
}


def event_type_str(event) -> str:
    """Convert a watchdog event object to our simple type string."""
    return _EVENT_TYPE_MAP.get(type(event).__name__, "unknown")


def is_dir_event(event) -> bool:
    return getattr(event, "is_directory", False)


def matches(event, config: dict) -> tuple[bool, str]:
    """
    Check whether a watchdog event matches the trigger config.

    Returns (matched: bool, reason: str).
    reason explains why it was accepted or rejected — useful for logs.
    """
    if not config.get("enabled", True):
        return False, "trigger disabled"

    # ── Event type check ──────────────────────────────────────────────────────
    allowed_events = config.get("events") or ["created", "modified", "deleted", "moved"]
    evt_type = event_type_str(event)
    if evt_type not in allowed_events:
        return False, f"event type '{evt_type}' not in {allowed_events}"

    # ── File vs folder check ──────────────────────────────────────────────────
    target = config.get("target", "both")
    is_dir = is_dir_event(event)
    if target == "file" and is_dir:
        return False, "event is a directory, target=file"
    if target == "folder" and not is_dir:
        return False, "event is a file, target=folder"

    # ── Get the relevant path ─────────────────────────────────────────────────
    # For moved events, use dest_path; otherwise use src_path
    path_str = getattr(event, "dest_path", None) or getattr(event, "src_path", "")
    path = Path(path_str)
    filename = path.name

    # ── Extension filter ──────────────────────────────────────────────────────
    ext_filter = config.get("extension_filter")
    if ext_filter and not is_dir:
        # Normalise: ensure all start with "."
        normalised = [e if e.startswith(".") else f".{e}" for e in ext_filter]
        if path.suffix.lower() not in [e.lower() for e in normalised]:
            return False, f"extension '{path.suffix}' not in {normalised}"

    # ── Filename pattern filter ───────────────────────────────────────────────
    pattern = config.get("filename_pattern")
    if pattern:
        if not fnmatch.fnmatch(filename, pattern):
            return False, f"filename '{filename}' does not match pattern '{pattern}'"

    return True, f"matched: {evt_type} on {path_str}"
