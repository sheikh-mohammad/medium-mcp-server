from __future__ import annotations

import asyncio

import httpx

from medium_mcp_server.config import load_settings
from medium_mcp_server.server import create_server


def _tool_payload(result: object) -> dict:
    if isinstance(result, tuple) and len(result) == 2:
        _content, structured = result
        return structured if isinstance(structured, dict) else {}
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    if isinstance(result, dict):
        return result
    return {}


def test_official_tools_fail_closed_without_token() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    for name, args in (
        ("get_profile", {}),
        ("list_publications", {}),
        ("create_draft", {"title": "T", "content": "# Hi", "content_format": "markdown"}),
        ("upload_image", {"image_path": "nope.png"}),
        ("publish_post", {"confirm": True, "title": "T", "content": "# Hi", "content_format": "markdown"}),
    ):
        payload = _tool_payload(asyncio.run(mcp.call_tool(name, args)))
        assert payload.get("ok") is False
        assert payload.get("mode") == "official_api"
        assert payload.get("error", {}).get("code") == "unsupported_capability"


def test_publish_post_requires_confirmation() -> None:
    settings, _ = load_settings([])
    settings = settings.model_copy(update={"medium_token": "test-token"}) if hasattr(settings, "model_copy") else settings
    if not hasattr(settings, "model_copy"):
        settings.medium_token = "test-token"  # type: ignore[attr-defined]
    mcp, _ = create_server(settings)

    payload = _tool_payload(
        asyncio.run(
            mcp.call_tool(
                "publish_post",
                {"title": "T", "content": "# Hi", "content_format": "markdown", "publish_status": "public"},
            )
        )
    )
    assert payload.get("ok") is False
    assert payload.get("error", {}).get("code") == "confirmation_required"


def test_official_api_create_draft_mocked_and_deduped(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path.endswith("/v1/me"):
            return httpx.Response(
                200,
                json={"data": {"id": "u1", "username": "user", "name": "User", "url": "https://medium.com/@user"}},
            )
        if request.method == "POST" and request.url.path.endswith("/v1/users/u1/posts"):
            return httpx.Response(
                201,
                json={
                    "data": {
                        "id": "p1",
                        "url": "https://medium.com/p/p1",
                        "publishStatus": "draft",
                        "canonicalUrl": "",
                        "tags": ["mcp"],
                    }
                },
            )
        return httpx.Response(404, json={"errors": [{"message": "not found"}]})

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", client_factory)

    settings, _ = load_settings([])
    settings = settings.model_copy(update={"medium_token": "test-token"}) if hasattr(settings, "model_copy") else settings
    if not hasattr(settings, "model_copy"):
        settings.medium_token = "test-token"  # type: ignore[attr-defined]
    mcp, _ = create_server(settings)

    args = {"title": "Draft", "content": "# Hello", "content_format": "markdown", "tags": ["mcp"], "idempotency_key": "k1"}
    first = _tool_payload(asyncio.run(mcp.call_tool("create_draft", args)))
    assert first.get("ok") is True
    assert first.get("mode") == "official_api"
    assert first.get("data", {}).get("post", {}).get("id") == "p1"

    second = _tool_payload(asyncio.run(mcp.call_tool("create_draft", args)))
    assert second.get("ok") is True
    assert second.get("data", {}).get("dedupe", {}).get("status") == "hit"
    # probe + create once; second call served from dedupe (no extra create)
    assert calls.count(("POST", "/v1/users/u1/posts")) == 1
