"""Structured logging with redaction and stdio-safe routing."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import REDACTED, Settings

_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(token[\"'=:\s]+)([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"(MEDIUM_TOKEN[\"'=:\s]+)([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"(authorization[\"'=:\s]+)([^\"'\s,}]+)", re.IGNORECASE),
    re.compile(r"(cookie[\"'=:\s]+)([^\"'\s,}]+)", re.IGNORECASE),
]


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if any(s in key_lower for s in ("token", "secret", "authorization", "cookie", "password")):
                out[k] = REDACTED if v not in (None, "") else v
            else:
                out[k] = redact_value(v)
        return out
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            record.msg = redact_text(str(record.msg))
            if record.args:
                if isinstance(record.args, dict):
                    record.args = redact_value(record.args)
                elif isinstance(record.args, tuple):
                    record.args = tuple(redact_value(a) for a in record.args)
                else:
                    record.args = redact_value(record.args)
            # Redact extra fields commonly used for structured context.
            for key in list(vars(record).keys()):
                if key.startswith("_"):
                    continue
                if key in {
                    "msg",
                    "args",
                    "name",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                }:
                    continue
                setattr(record, key, redact_value(getattr(record, key)))
        except Exception:
            # Never let logging/redaction break the server.
            pass
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Include selected structured extras (audit/correlation friendly).
        for key in (
            "correlation_id",
            "tool",
            "mode",
            "action",
            "outcome",
            "duration_ms",
            "target",
            "idempotency_key_hash",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings) -> None:
    """Configure root logging. For stdio transport, logs must not go to stdout."""
    level_name = (settings.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    formatter = JsonFormatter()
    redaction = RedactionFilter()

    stream_target = sys.stderr if settings.transport == "stdio" else sys.stderr
    stream_handler = logging.StreamHandler(stream_target)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(redaction)
    root.addHandler(stream_handler)

    if settings.log_file:
        try:
            file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(redaction)
            root.addHandler(file_handler)
        except Exception:
            # If file logging cannot be configured, continue with stderr logging.
            root.exception("Failed to configure log file handler")

    # Quiet noisy libraries by default unless DEBUG.
    if level > logging.DEBUG:
        for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


def hash_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def audit_log(
    logger: logging.Logger,
    *,
    correlation_id: str,
    tool: str,
    action: str,
    mode: str,
    outcome: str,
    duration_ms: int | None = None,
    target: str | None = None,
    idempotency_key_hash: str | None = None,
) -> None:
    extra: dict[str, Any] = {
        "correlation_id": correlation_id,
        "tool": tool,
        "action": action,
        "mode": mode,
        "outcome": outcome,
    }
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if target is not None:
        extra["target"] = target
    if idempotency_key_hash is not None:
        extra["idempotency_key_hash"] = idempotency_key_hash
    logger.info("audit", extra=extra)
