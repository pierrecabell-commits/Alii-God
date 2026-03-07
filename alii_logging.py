"""
Alii-God — Unified Logging System

Replaces per-file `def log(msg)` functions with a single, structured,
JSON-based logging facility built entirely on stdlib.

Usage:
    from alii_logging import get_logger
    log = get_logger("alfred")
    log.info("Service started", extra={"service": "distributed-brain"})
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_WORKDIR = Path(os.environ.get("ALII_WORKDIR", Path(__file__).parent.resolve()))
_LOG_DIR = _WORKDIR / "logs"

_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT: int = 5
_DEFAULT_LEVEL: str = os.environ.get("ALII_LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------------------
# Correlation / request ID  (set per-request or per-task)
# ---------------------------------------------------------------------------

correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set (or generate) a correlation ID for the current context.  Returns the ID."""
    cid = cid or uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Return the current correlation ID, or ``None``."""
    return correlation_id.get()


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------

class _JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        obj: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
                        .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "thread": record.threadName,
            "pid": record.process,
        }

        # Attach correlation ID when available.
        cid = correlation_id.get(None)
        if cid is not None:
            obj["correlation_id"] = cid

        # Merge caller-supplied extra keys (skip internal LogRecord attrs).
        _RESERVED = set(logging.LogRecord(
            "", 0, "", 0, "", (), None
        ).__dict__.keys()) | {"message"}
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                obj[key] = value

        # Exception info
        if record.exc_info and record.exc_info[1] is not None:
            obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# Logger registry (one logger per name, configured once)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_configured: Dict[str, logging.Logger] = {}


def get_logger(
    name: str,
    *,
    level: Optional[str] = None,
    log_dir: Optional[Path] = None,
    max_bytes: int = _MAX_BYTES,
    backup_count: int = _BACKUP_COUNT,
    console: bool = True,
) -> logging.Logger:
    """Return a configured logger for *name*.

    Parameters
    ----------
    name:
        Logical name (e.g. ``"alfred"``, ``"security"``).  Used as both the
        Python logger name and the base filename.
    level:
        Override the default level (``ALII_LOG_LEVEL`` env var, default INFO).
    log_dir:
        Override the default log directory (``{WORKDIR}/logs``).
    max_bytes:
        Maximum size per log file before rotation.
    backup_count:
        Number of rotated backups to keep.
    console:
        If ``True`` (default), also log to stderr.
    """
    with _lock:
        if name in _configured:
            return _configured[name]

        effective_level = getattr(logging, (level or _DEFAULT_LEVEL), logging.INFO)
        target_dir = log_dir or _LOG_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(f"alii.{name}")
        logger.setLevel(effective_level)
        logger.propagate = False  # avoid duplicate output from root logger

        formatter = _JSONFormatter()

        # --- Rotating file handler ---
        file_handler = RotatingFileHandler(
            filename=str(target_dir / f"{name}.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(effective_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # --- Console (stderr) handler ---
        if console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(effective_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        _configured[name] = logger
        return logger
