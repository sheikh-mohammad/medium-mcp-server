"""Error taxonomy and safe error/result helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "validation_error"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    CONFIRMATION_REQUIRED = "confirmation_required"
    AUTH_ERROR = "auth_error"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    UPSTREAM_ERROR = "upstream_error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    INTERNAL_ERROR = "internal_error"


@dataclass(slots=True)
class ToolError(Exception):
    code: ErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        if self.next_actions:
            payload["next_actions"] = self.next_actions
        return payload


def validation_error(message: str, **details: Any) -> ToolError:
    return ToolError(ErrorCode.VALIDATION_ERROR, message, details=details)


def unsupported_capability(message: str, alternatives: list[str] | None = None, **details: Any) -> ToolError:
    return ToolError(
        ErrorCode.UNSUPPORTED_CAPABILITY,
        message,
        details=details,
        next_actions=alternatives or [],
    )


def confirmation_required(message: str, **details: Any) -> ToolError:
    return ToolError(
        ErrorCode.CONFIRMATION_REQUIRED,
        message,
        details=details,
        next_actions=[
            "Review the prepared content and warnings, then call publish_post again with confirm=true."
        ],
    )


def auth_error(message: str, **details: Any) -> ToolError:
    return ToolError(
        ErrorCode.AUTH_ERROR,
        message,
        details=details,
        next_actions=[
            "Check MEDIUM_TOKEN configuration/capabilities or use export/prepare and feed_read modes."
        ],
    )


def not_found(message: str, **details: Any) -> ToolError:
    return ToolError(ErrorCode.NOT_FOUND, message, details=details)


def unavailable(message: str, **details: Any) -> ToolError:
    return ToolError(ErrorCode.UNAVAILABLE, message, details=details)


def upstream_error(message: str, **details: Any) -> ToolError:
    return ToolError(ErrorCode.UPSTREAM_ERROR, message, details=details)


def rate_limited(message: str, **details: Any) -> ToolError:
    return ToolError(
        ErrorCode.RATE_LIMITED,
        message,
        details=details,
        next_actions=["Wait and retry later for safe read operations. Do not blindly retry create/publish."],
    )


def timeout_error(message: str, **details: Any) -> ToolError:
    return ToolError(
        ErrorCode.TIMEOUT,
        message,
        details=details,
        next_actions=["Retry safe read operations if appropriate. Do not blindly retry create/publish."],
    )


def internal_error(message: str = "An internal error occurred.", **details: Any) -> ToolError:
    return ToolError(ErrorCode.INTERNAL_ERROR, message, details=details)


def error_result(mode: str, err: ToolError | Exception, warnings: list[str] | None = None) -> dict[str, Any]:
    if isinstance(err, ToolError):
        payload = err.to_dict()
        next_actions = payload.pop("next_actions", [])
        return {
            "ok": False,
            "mode": mode,
            "data": None,
            "warnings": warnings or [],
            "next_actions": next_actions,
            "error": payload,
        }
    return {
        "ok": False,
        "mode": mode,
        "data": None,
        "warnings": warnings or [],
        "next_actions": [],
        "error": {"code": ErrorCode.INTERNAL_ERROR.value, "message": "An internal error occurred."},
    }


def success_result(
    mode: str,
    data: Any = None,
    *,
    warnings: list[str] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": mode,
        "data": data,
        "warnings": warnings or [],
        "next_actions": next_actions or [],
        "error": None,
    }
