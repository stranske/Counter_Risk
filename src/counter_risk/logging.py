"""Structured logging configuration for Counter Risk."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format records as JSON objects for deterministic logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


def _resolve_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    normalized = level.upper()
    resolved = logging.getLevelName(normalized)
    if isinstance(resolved, int):
        return resolved
    msg = f"Unsupported log level: {level}"
    raise ValueError(msg)


def configure_logging(
    *,
    log_level: str | int = "INFO",
    log_file: str | Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """Configure root logger with structured console/file handlers."""

    root = logging.getLogger()
    root.setLevel(_resolve_level(log_level))
    root.handlers.clear()

    formatter = JsonFormatter()

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    return root
