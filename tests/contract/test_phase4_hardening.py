from __future__ import annotations

import asyncio
import json

from medium_mcp_server.adapters import export as export_adapter
from medium_mcp_server.config import load_settings
from medium_mcp_server.domain.validation import MAX_CONTENT_LENGTH, MAX_TITLE_LENGTH
from medium_mcp_server.server import create_server


def _payload(result: object) -> dict:
    if isinstance(result, tuple) and len(result) == 2:
        _content, structured = result
        return structured if isinstance(structured, dict) else {}
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    if isinstance(result, dict):
        return result
    return {}


def _prepared() -> dict:
    result = export_adapter.prepare_post(
        title="Hardening Post",
        content="Body",
        content_format="markdown",
    )
    assert result["ok"] is True
    return result["data"]["prepared_post"]


def test_export_bundle_rejects_path_writes_including_traversal() -> None:
    prepared = _prepared()
    for args in (
        {"prepared_post": prepared, "path": "../secrets/out.md"},
        {"prepared_post": prepared, "path": "..\\..\\Windows\\system.ini"},
        {"prepared_post": prepared, "output": "path"},
    ):
        res = export_adapter.export_post_bundle(**args)
        assert res["ok"] is False
        assert res["error"]["code"] == "unsupported_capability"
        assert res["next_actions"]
        assert "inline" in " ".join(res["next_actions"]).lower()


def test_prepare_post_enforces_oversized_input_bounds() -> None:
    too_long_title = "t" * (MAX_TITLE_LENGTH + 1)
    res_title = export_adapter.prepare_post(
        title=too_long_title,
        content="ok",
        content_format="markdown",
    )
    assert res_title["ok"] is False
    assert res_title["error"]["code"] == "validation_error"
    assert any(e.get("field") == "title" for e in res_title["data"]["validation"]["errors"])

    too_long_content = "c" * (MAX_CONTENT_LENGTH + 1)
    res_content = export_adapter.prepare_post(
        title="ok",
        content=too_long_content,
        content_format="markdown",
    )
    assert res_content["ok"] is False
    assert res_content["error"]["code"] == "validation_error"
    assert any(e.get("field") == "content" for e in res_content["data"]["validation"]["errors"])


def test_official_tools_fail_closed_with_alternatives_without_token() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    for name, args in (
        ("get_profile", {}),
        ("list_publications", {}),
        ("create_draft", {"title": "T", "content": "Hi", "content_format": "markdown"}),
        ("upload_image", {"image_bytes_base64": "ZmFrZQ==", "media_type": "image/png"}),
        ("publish_post", {"confirm": True, "title": "T", "content": "Hi", "content_format": "markdown", "publish_status": "public"}),
    ):
        result = _payload(asyncio.run(mcp.call_tool(name, args)))
        assert result.get("ok") is False
        assert result.get("mode") == "official_api"
        assert result.get("error", {}).get("code") == "unsupported_capability"
        actions = " ".join(result.get("next_actions") or []).lower()
        assert "export" in actions or "prepare" in actions or "feed" in actions


def test_publish_post_confirmation_gate_no_side_effect_contract() -> None:
    settings, _ = load_settings([])
    settings.medium_token = "test-token"  # type: ignore[attr-defined]
    mcp, _ = create_server(settings)

    result = _payload(
        asyncio.run(
            mcp.call_tool(
                "publish_post",
                {
                    "title": "T",
                    "content": "Hi",
                    "content_format": "markdown",
                    "publish_status": "public",
                },
            )
        )
    )
    assert result.get("ok") is False
    assert result.get("error", {}).get("code") == "confirmation_required"
    assert result.get("mode") == "official_api"


def test_doctor_redacts_token_and_reports_streamable_http_posture() -> None:
    from medium_mcp_server.__main__ import _doctor_output

    settings, _ = load_settings(
        [
            "doctor",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            "8123",
            "--path",
            "rpc",
        ]
    )
    settings.medium_token = "super-secret-token"  # type: ignore[attr-defined]
    _mcp, capability_manager = create_server(settings)

    payload = _doctor_output(settings, capability_manager)
    dumped = json.dumps(payload, ensure_ascii=False)

    assert "super-secret-token" not in dumped
    assert payload["settings"]["medium_token"] == "***redacted***"
    assert payload["settings"]["http_path"] == "/rpc"

    checks = {c["name"]: c for c in payload.get("checks", [])}
    assert checks["http_bind"]["status"] == "ok"
    assert checks["secrets_redaction"]["status"] == "ok"
    assert "deployment" in checks["http_deployment"]["message"].lower()
    assert checks["medium_token"]["status"] in {"info", "ok", "warn"}
