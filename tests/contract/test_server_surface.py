from __future__ import annotations

import asyncio
import json

from medium_mcp_server.config import load_settings
from medium_mcp_server.server import create_server

PHASE3_TOOLS = [
    "get_capabilities",
    "prepare_post",
    "render_medium_content",
    "export_post_bundle",
    "read_public_feed",
    "get_profile",
    "list_publications",
    "create_draft",
    "upload_image",
    "publish_post",
]


def test_phase3_tools_resources_prompts_registered_without_token() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    tools = asyncio.run(mcp.list_tools())
    tool_names = [getattr(t, "name", None) for t in tools]
    assert tool_names == PHASE3_TOOLS

    resources = asyncio.run(mcp.list_resources())
    uris = {str(getattr(r, "uri", "")) for r in resources}
    assert "medium://capabilities" in uris
    assert "medium://templates/post" in uris
    assert "medium://exports/latest" in uris
    # Official resources are only exposed when token is configured.
    assert "medium://profile" not in uris
    assert "medium://publications" not in uris

    prompts = asyncio.run(mcp.list_prompts())
    prompt_names = {getattr(p, "name", None) for p in prompts}
    assert "draft_medium_post" in prompt_names
    assert "crosspost_checklist" in prompt_names
    assert "preflight_publish" in prompt_names


def test_phase3_tools_and_resources_registered_with_token() -> None:
    settings, _ = load_settings([])
    settings = settings.model_copy(update={"medium_token": "test-token"}) if hasattr(settings, "model_copy") else settings
    if not hasattr(settings, "model_copy"):
        settings.medium_token = "test-token"  # type: ignore[attr-defined]
    mcp, _ = create_server(settings)

    tools = asyncio.run(mcp.list_tools())
    tool_names = [getattr(t, "name", None) for t in tools]
    assert tool_names == PHASE3_TOOLS

    resources = asyncio.run(mcp.list_resources())
    uris = {str(getattr(r, "uri", "")) for r in resources}
    assert "medium://profile" in uris
    assert "medium://publications" in uris


def test_capabilities_tool_and_resource_payloads_phase3() -> None:
    settings, _ = load_settings([])
    mcp, manager = create_server(settings)

    result = asyncio.run(mcp.call_tool("get_capabilities", {}))
    payload = None
    if isinstance(result, tuple) and len(result) == 2:
        _content, structured = result
        payload = structured
    elif isinstance(result, dict):
        payload = result
    else:
        payload = manager.get_report().to_dict()

    assert isinstance(payload, dict)
    assert payload.get("supported_tools") == PHASE3_TOOLS
    assert "export" in (payload.get("active_capabilities") or [])
    assert "feed_read" in (payload.get("active_capabilities") or [])
    assert payload.get("version") == "0.1.0"

    contents = asyncio.run(mcp.read_resource("medium://capabilities"))
    assert contents
    text = getattr(contents[0], "content", None) or getattr(contents[0], "text", None)
    assert text is not None
    resource_payload = json.loads(text)
    assert resource_payload["supported_tools"] == payload["supported_tools"]
    assert resource_payload["auth"]["configured"] is False

    template_contents = asyncio.run(mcp.read_resource("medium://templates/post"))
    assert template_contents
    template_text = getattr(template_contents[0], "content", None) or getattr(
        template_contents[0], "text", None
    )
    assert template_text is not None
    template = json.loads(template_text)
    assert template["name"] == "medium-post-template"
    assert "checklist" in template
    assert "template" in template
