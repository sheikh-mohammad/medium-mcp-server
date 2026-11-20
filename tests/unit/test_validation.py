from __future__ import annotations

from medium_mcp_server.domain.validation import (
    MAX_TAGS,
    SUPPORTED_LICENSES,
    detect_fidelity_warnings,
    normalize_tags,
    validate_and_normalize_post,
)


def test_normalize_tags_keeps_first_five_valid_unique() -> None:
    tags = [" python ", "MCP", "python", "", "AI", "tools", "writing", "extra"]
    normalized, notes, warnings = normalize_tags(tags)
    assert normalized == ["python", "MCP", "AI", "tools", "writing"]
    assert any("duplicate" in n.lower() for n in notes)
    assert any("invalid" in n.lower() or "empty" in n.lower() for n in notes)
    assert any(str(MAX_TAGS) in w for w in warnings)


def test_validate_and_normalize_post_success() -> None:
    prepared, result = validate_and_normalize_post(
        title="  My Post  ",
        content="Hello\r\n\r\nWorld",
        content_format="markdown",
        tags=["one", "two", "one", "three", "four", "five", "six"],
        canonical_url="https://example.com/original",
        license=SUPPORTED_LICENSES[0],
        publish_status_intent="draft",
        publication_id="pub-123",
        idempotency_key="idem-1",
    )
    assert result.ok is True
    assert result.errors == []
    assert prepared is not None
    assert prepared.title == "My Post"
    assert prepared.content == "Hello\n\nWorld"
    assert prepared.tags == ["one", "two", "three", "four", "five"]
    assert prepared.canonical_url == "https://example.com/original"
    assert prepared.license == SUPPORTED_LICENSES[0]
    assert prepared.publish_status_intent == "draft"
    assert prepared.publication_id == "pub-123"
    assert prepared.idempotency_key == "idem-1"
    assert any("Normalized line endings" in n for n in prepared.normalization_notes)
    assert any(w.field == "tags" for w in result.warnings)


def test_validate_rejects_missing_required_and_invalid_fields() -> None:
    prepared, result = validate_and_normalize_post(
        title="   ",
        content="",
        content_format="txt",
        tags=["ok"],
        canonical_url="not-a-url",
        license="not-a-license",
        publish_status_intent="published",
    )
    assert result.ok is False
    assert prepared is None
    fields = {e.field for e in result.errors}
    assert {"title", "content", "content_format", "canonical_url", "license", "publish_status_intent"} <= fields


def test_detect_fidelity_warnings_for_unsafe_html() -> None:
    warnings = detect_fidelity_warnings('<p onclick="x()">hi</p><script>alert(1)</script>', "html")
    assert warnings
    assert any("unsupported" in w.lower() or "unsafe" in w.lower() for w in warnings)
