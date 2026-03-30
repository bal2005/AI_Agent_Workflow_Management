"""
Structured logging for sandbox workflow execution.
All log entries are JSON lines so they can be parsed, stored, and displayed in the UI.
"""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        # Attach any extra fields passed via extra={...}
        for key in ("run_id", "task_id", "agent", "tool", "permission", "sandbox"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes structured JSON to stdout."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
