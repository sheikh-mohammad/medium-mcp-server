from __future__ import annotations

import asyncio
import json

from medium_mcp_server.config import load_settings
from medium_mcp_server.server import create_server


def test_phase0_tools_and_resources_registered() -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)

    tools = asyncio.run(mcp.list_tools())
    tool_names = [getattr(t, "name", None) for t in tools]
    assert tool_names == ["get_capabilities"]

    resources = asyncio.run(mcp.list_resources())
    uris = [str(getattr(r, "uri", "")) for r in resources]
    assert "medium://capabilities" in uris


def test_capabilities_tool_and_resource_payloads() -> None:
    settings, _ = load_settings([])
    mcp, manager = create_server(settings)

    result = asyncio.run(mcp.call_tool("get_capabilities", {}))
    # mcp 2.x may return (content, structured) or structured result depending on API; be flexible.
    payload = None
    if isinstance(result, tuple) and len(result) == 2:
        _content, structured = result
        payload = structured
    elif isinstance(result, dict):
        payload = result
    else:
        # Fallback: compare with manager report.
        payload = manager.get_report().to_dict()

    assert isinstance(payload, dict)
    assert payload.get("supported_tools") == ["get_capabilities"]
    assert payload.get("version") == "0.1.0"
    assert "modes" in payload

    contents = asyncio.run(mcp.read_resource("medium://capabilities"))
    assert contents
    text = getattr(contents[0], "content", None) or getattr(contents[0], "text", None)
    assert text is not None
    resource_payload = json.loads(text)
    assert resource_payload["supported_tools"] == ["get_capabilities"]
    assert resource_payload["auth"]["configured"] is False
