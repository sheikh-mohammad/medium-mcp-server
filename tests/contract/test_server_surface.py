from __future__ import annotations

import asyncio
import json

from medium_mcp_server.config import load_settings
from medium_mcp_server.server import create_server


def test_phase1_tools_resources_prompts_registered() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    tools = asyncio.run(mcp.list_tools())
    tool_names = [getattr(t, "name", None) for t in tools]
    assert tool_names == [
        "get_capabilities",
        "prepare_post",
        "render_medium_content",
        "export_post_bundle",
    ]

    resources = asyncio.run(mcp.list_resources())
    uris = {str(getattr(r, "uri", "")) for r in resources}
    assert "medium://capabilities" in uris
    assert "medium://templates/post" in uris
    assert "medium://exports/latest" in uris

    prompts = asyncio.run(mcp.list_prompts())
    prompt_names = {getattr(p, "name", None) for p in prompts}
    assert "draft_medium_post" in prompt_names
    assert "crosspost_checklist" in prompt_names
    assert "preflight_publish" in prompt_names


def test_capabilities_tool_and_resource_payloads_phase1() -> None:
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
    assert payload.get("supported_tools") == [
        "get_capabilities",
        "prepare_post",
        "render_medium_content",
        "export_post_bundle",
    ]
    assert "export" in (payload.get("active_capabilities") or [])
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
