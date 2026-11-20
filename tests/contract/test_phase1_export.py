from __future__ import annotations

import asyncio
import json

from medium_mcp_server.config import load_settings
from medium_mcp_server.server import create_server


def _call_tool(mcp, name: str, arguments: dict):
    return asyncio.run(mcp.call_tool(name, arguments))


def _structured(result):
    # mcp 1.x style: (content, structured)
    if isinstance(result, tuple) and len(result) == 2:
        return result[1]
    # mcp 2.x style: CallToolResult
    if hasattr(result, "structured_content"):
        sc = getattr(result, "structured_content", None)
        if isinstance(sc, dict):
            return sc
    # Some APIs may return dict directly
    if isinstance(result, dict):
        return result
    # Fallback: try to parse text content
    if hasattr(result, "content"):
        content = getattr(result, "content", None)
        if isinstance(content, list) and content:
            text = getattr(content[0], "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except Exception:
                    return None
    return None


def _text_content(result):
    # (content_list, structured?) shape in mcp 2.x
    if isinstance(result, tuple) and result:
        content = result[0]
        if isinstance(content, list) and content:
            item = content[0]
            return getattr(item, "text", None) or getattr(item, "content", None)
    if isinstance(result, list) and result:
        return getattr(result[0], "text", None) or getattr(result[0], "content", None)
    return None


def test_prepare_render_export_contract_and_determinism() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    prep = _structured(
        _call_tool(
            mcp,
            "prepare_post",
            {
                "title": "Contract Post",
                "content": "# Hello\n\nThis is deterministic.",
                "content_format": "markdown",
                "tags": ["one", "two"],
                "canonical_url": "https://example.com/source",
                "license": "all-rights-reserved",
                "publish_status_intent": "draft",
                "idempotency_key": "contract-1",
            },
        )
    )
    assert prep["ok"] is True
    assert prep["mode"] == "export"
    assert prep["data"]["medium_ready"] is True
    prepared_post = prep["data"]["prepared_post"]
    assert prepared_post["title"] == "Contract Post"
    assert prepared_post["content_format"] == "markdown"

    rendered = _structured(
        _call_tool(mcp, "render_medium_content", {"prepared_post": prepared_post})
    )
    assert rendered["ok"] is True
    assert rendered["data"]["title"] == "Contract Post"
    assert "content" in rendered["data"]
    assert "warnings" in rendered["data"]

    exp1 = _structured(_call_tool(mcp, "export_post_bundle", {"prepared_post": prepared_post}))
    exp2 = _structured(_call_tool(mcp, "export_post_bundle", {"prepared_post": prepared_post}))
    assert exp1["ok"] is True and exp2["ok"] is True
    assert exp1["data"]["bundle"]["artifacts"] == exp2["data"]["bundle"]["artifacts"]
    assert (
        exp1["data"]["manifest"]["content_sha256"]
        == exp2["data"]["manifest"]["content_sha256"]
    )

    # exports/latest should now be available in runtime context
    latest = asyncio.run(mcp.read_resource("medium://exports/latest"))
    latest_text = getattr(latest[0], "content", None) or getattr(latest[0], "text", None)
    latest_payload = json.loads(latest_text)
    assert latest_payload["type"] == "export_bundle"
    assert latest_payload["title"] == "Contract Post"


def test_export_bundle_inline_only_rejections_contract() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    prep = _structured(
        _call_tool(
            mcp,
            "prepare_post",
            {"title": "T", "content": "C", "content_format": "markdown"},
        )
    )
    prepared_post = prep["data"]["prepared_post"]

    for args in (
        {"prepared_post": prepared_post, "output": "path"},
        {"prepared_post": prepared_post, "path": "/tmp/out.md"},
    ):
        res = _structured(_call_tool(mcp, "export_post_bundle", args))
        assert res["ok"] is False
        assert res["error"]["code"] == "unsupported_capability"
        assert res["next_actions"]
        assert "inline" in " ".join(res["next_actions"]).lower()


def test_prepare_post_validation_error_contract() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)
    res = _structured(
        _call_tool(
            mcp,
            "prepare_post",
            {"title": "", "content": "", "content_format": "markdown"},
        )
    )
    assert res["ok"] is False
    assert res["error"]["code"] == "validation_error"
    assert res["data"]["medium_ready"] is False
    assert res["data"]["validation"]["ok"] is False
    assert res["data"]["prepared_post"] is None
