from __future__ import annotations

from medium_mcp_server.adapters import export as export_adapter


def _prepared() -> dict:
    result = export_adapter.prepare_post(
        title="Hello Medium",
        content="Line 1\n\nLine 2",
        content_format="markdown",
        tags=["mcp", "python"],
        canonical_url="https://example.com/original",
        license="all-rights-reserved",
        publish_status_intent="draft",
        idempotency_key="idem-123",
    )
    assert result["ok"] is True
    return result["data"]["prepared_post"]


def test_prepare_post_success_and_validation_failure() -> None:
    ok = export_adapter.prepare_post(
        title="T",
        content="C",
        content_format="markdown",
        tags=["a", "b", "a", "c", "d", "e", "f"],
    )
    assert ok["ok"] is True
    assert ok["mode"] == "export"
    assert ok["data"]["medium_ready"] is True
    assert ok["data"]["prepared_post"]["tags"] == ["a", "b", "c", "d", "e"]
    assert ok["data"]["validation"]["ok"] is True
    assert any(w.get("field") == "tags" for w in ok["data"]["validation"]["warnings"])

    bad = export_adapter.prepare_post(title="", content="", content_format="pdf")
    assert bad["ok"] is False
    assert bad["error"]["code"] == "validation_error"
    assert bad["data"]["medium_ready"] is False
    assert bad["data"]["prepared_post"] is None
    assert bad["data"]["validation"]["ok"] is False


def test_render_medium_content_from_prepared_and_raw() -> None:
    prepared = _prepared()
    rendered = export_adapter.render_medium_content(prepared_post=prepared, target_format="markdown")
    assert rendered["ok"] is True
    assert rendered["mode"] == "export"
    assert rendered["data"]["title"] == "Hello Medium"
    assert rendered["data"]["content_format"] == "markdown"
    assert "Line 1" in rendered["data"]["content"]
    assert rendered["data"]["metadata"]["canonical_url"] == "https://example.com/original"

    rendered_raw = export_adapter.render_medium_content(
        title="Raw",
        content="Hello",
        content_format="markdown",
    )
    assert rendered_raw["ok"] is True
    assert rendered_raw["data"]["title"] == "Raw"

    bad = export_adapter.render_medium_content(title="", content="", content_format="markdown")
    assert bad["ok"] is False
    assert bad["error"]["code"] == "validation_error"


def test_export_post_bundle_inline_only_and_deterministic() -> None:
    prepared = _prepared()
    first = export_adapter.export_post_bundle(prepared_post=prepared)
    second = export_adapter.export_post_bundle(prepared_post=prepared)
    assert first["ok"] is True
    assert second["ok"] is True
    assert "bundle" in first["data"]
    assert "manifest" in first["data"]
    assert first["data"]["bundle"]["format"] == "medium-export-bundle/v1"
    assert "title.txt" in first["data"]["bundle"]["artifacts"]
    assert "content.md" in first["data"]["bundle"]["artifacts"]
    assert "metadata.json" in first["data"]["bundle"]["artifacts"]
    assert first["data"]["manifest"]["content_sha256"] == second["data"]["manifest"]["content_sha256"]
    assert first["data"]["bundle"]["artifacts"] == second["data"]["bundle"]["artifacts"]

    no_manifest = export_adapter.export_post_bundle(prepared_post=prepared, include_manifest=False)
    assert no_manifest["ok"] is True
    assert no_manifest["data"]["manifest"] is None


def test_export_post_bundle_rejects_path_writes() -> None:
    prepared = _prepared()
    by_path = export_adapter.export_post_bundle(prepared_post=prepared, path="/tmp/out")
    assert by_path["ok"] is False
    assert by_path["error"]["code"] == "unsupported_capability"
    assert by_path["next_actions"]

    by_output = export_adapter.export_post_bundle(prepared_post=prepared, output="path")
    assert by_output["ok"] is False
    assert by_output["error"]["code"] == "unsupported_capability"


def test_latest_export_metadata_updates() -> None:
    export_adapter._LATEST_EXPORT = None  # reset module-level runtime state for test isolation
    assert export_adapter.get_latest_export_metadata() is None
    prepared = _prepared()
    assert export_adapter.get_latest_export_metadata()["type"] == "prepared_post"
    export_adapter.export_post_bundle(prepared_post=prepared)
    latest = export_adapter.get_latest_export_metadata()
    assert latest is not None
    assert latest["type"] == "export_bundle"
    assert "content_sha256" in latest
