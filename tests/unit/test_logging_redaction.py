from __future__ import annotations

import json
import logging

from medium_mcp_server.config import Settings
from medium_mcp_server.logging import (
    JsonFormatter,
    RedactionFilter,
    audit_log,
    get_logger,
    hash_identifier,
    new_correlation_id,
    redact_text,
    redact_value,
)


def test_redact_text_masks_secrets() -> None:
    text = "Authorization: Bearer secret-token MEDIUM_TOKEN=abc cookie=session123 token=xyz"
    redacted = redact_text(text)
    assert "secret-token" not in redacted
    assert "abc" not in redacted
    assert "session123" not in redacted
    assert "xyz" not in redacted
    assert "***redacted***" in redacted


def test_redact_value_masks_sensitive_keys_and_nested_values() -> None:
    payload = {
        "medium_token": "topsecret",
        "nested": {"authorization": "Bearer abc", "ok": "Bearer def", "cookie": "sid=1"},
        "list": [{"password": "p"}, "token=inline"],
    }
    redacted = redact_value(payload)
    assert redacted["medium_token"] == "***redacted***"
    assert redacted["nested"]["authorization"] == "***redacted***"
    assert redacted["nested"]["cookie"] == "***redacted***"
    assert "def" not in redacted["nested"]["ok"]
    assert redacted["list"][0]["password"] == "***redacted***"
    assert "inline" not in redacted["list"][1]


def test_logging_filter_and_formatter_redact_and_include_audit_fields() -> None:
    logger = get_logger("test.redaction")
    handler = logging.StreamHandler()
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    handler.addFilter(RedactionFilter())

    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg="Bearer secret-token token=abc",
        args=(),
        exc_info=None,
        extra={
            "correlation_id": "cid123",
            "tool": "publish_post",
            "mode": "official_api",
            "action": "publish_post",
            "outcome": "error:confirmation_required",
            "duration_ms": 7,
            "target": "public:user",
            "idempotency_key_hash": "hash123",
        },
    )
    assert handler.filter(record)
    rendered = handler.format(record)
    payload = json.loads(rendered)

    assert "secret-token" not in rendered
    assert "abc" not in rendered
    assert payload["message"].count("***redacted***") >= 1
    assert payload["correlation_id"] == "cid123"
    assert payload["tool"] == "publish_post"
    assert payload["mode"] == "official_api"
    assert payload["action"] == "publish_post"
    assert payload["outcome"] == "error:confirmation_required"
    assert payload["duration_ms"] == 7
    assert payload["target"] == "public:user"
    assert payload["idempotency_key_hash"] == "hash123"


def test_audit_helpers_and_settings_redaction() -> None:
    cid = new_correlation_id()
    assert len(cid) == 16
    assert hash_identifier("  my-key  ") == hash_identifier("my-key")
    assert hash_identifier("") is None
    assert hash_identifier(None) is None

    settings = Settings(medium_token="secret-token")
    redacted = settings.redacted_dict()
    assert redacted["medium_token"] == "***redacted***"

    logger = logging.getLogger("test.audit.emit")
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        audit_log(
            logger,
            correlation_id=cid,
            tool="create_draft",
            action="create_draft",
            mode="official_api",
            outcome="ok",
            duration_ms=3,
            target="user",
            idempotency_key_hash=hash_identifier("k1"),
        )
    finally:
        logger.removeHandler(handler)

    assert records
    rec = records[-1]
    assert rec.msg == "audit"
    assert rec.correlation_id == cid
    assert rec.tool == "create_draft"
    assert rec.outcome == "ok"
    assert rec.idempotency_key_hash == hash_identifier("k1")
