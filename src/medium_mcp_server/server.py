"""MCP server assembly for the Medium MCP server."""

from __future__ import annotations

import json
from typing import Any

from . import __version__
from .capabilities import CapabilityManager, build_capability_manager
from .config import Settings

SERVER_INSTRUCTIONS = (
    "Medium MCP server. Capability-gated and draft-first. "
    "Use get_capabilities and medium://capabilities to understand available modes, "
    "limitations, and supported operations before taking actions."
)


def _build_mcp_server(name: str, instructions: str, version: str) -> Any:
    """Create an MCP server instance across supported/likely SDK APIs."""
    errors: list[Exception] = []

    # mcp 2.x API
    try:
        from mcp.server.mcpserver import MCPServer

        try:
            return MCPServer(name=name, instructions=instructions, version=version)
        except TypeError:
            return MCPServer(name=name, instructions=instructions)
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(exc)

    # mcp 1.x / FastMCP-compatible API
    for mod_name, attr in (
        ("mcp.server.fastmcp", "FastMCP"),
        ("mcp.server.fastmcp.server", "FastMCP"),
        ("fastmcp", "FastMCP"),
    ):
        try:
            module = __import__(mod_name, fromlist=[attr])
            FastMCP = getattr(module, attr)
            for kwargs in (
                {"name": name, "instructions": instructions},
                {"instructions": instructions},
                {},
            ):
                try:
                    return FastMCP(name, **{k: v for k, v in kwargs.items() if k != "name"})
                except TypeError:
                    continue
            return FastMCP(name)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(exc)

    detail = f": {errors[-1]}" if errors else ""
    raise RuntimeError(
        "Unable to create MCP server with the installed 'mcp' SDK. "
        f"Install a compatible official MCP Python SDK{detail}"
    ) from (errors[-1] if errors else None)


def create_server(settings: Settings) -> tuple[Any, CapabilityManager]:
    """Create and configure the MCP server with Phase 0 surface."""
    capability_manager = build_capability_manager(settings)
    mcp = _build_mcp_server(
        name="medium-mcp-server",
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
    )

    _register_capabilities_tool(mcp, capability_manager)
    _register_capabilities_resource(mcp, capability_manager)

    # Phase 1+ tools/resources/prompts will be registered here.
    return mcp, capability_manager


def _register_capabilities_tool(mcp: Any, capability_manager: CapabilityManager) -> None:
    description = (
        "Report enabled modes, auth state (redacted), supported operations, and important limitations/warnings."
    )

    def get_capabilities() -> dict[str, Any]:
        return capability_manager.get_report().to_dict()

    # Prefer decorator APIs (MCPServer 2.x / FastMCP-style).
    if hasattr(mcp, "tool"):
        tool_attr = mcp.tool
        try:
            decorator = tool_attr(name="get_capabilities", description=description)
            decorator(get_capabilities)
            return
        except TypeError:
            pass
        except Exception:
            # Fall through to alternatives.
            pass
        try:
            decorator = tool_attr()
            decorator(get_capabilities)
            return
        except Exception:
            pass

    if hasattr(mcp, "add_tool"):
        try:
            mcp.add_tool(get_capabilities, name="get_capabilities", description=description)
            return
        except Exception:
            pass

    raise RuntimeError("Unable to register get_capabilities tool with installed MCP SDK API")


def _register_capabilities_resource(mcp: Any, capability_manager: CapabilityManager) -> None:
    uri = "medium://capabilities"
    name = "capabilities"
    description = "Current modes, supported operations, limitations, and redacted auth status."
    mime_type = "application/json"

    def capabilities_resource() -> str:
        return json.dumps(capability_manager.get_report().to_dict(), ensure_ascii=False)

    if hasattr(mcp, "resource"):
        resource_attr = mcp.resource
        try:
            decorator = resource_attr(
                uri,
                name=name,
                description=description,
                mime_type=mime_type,
            )
            decorator(capabilities_resource)
            return
        except Exception:
            pass
        try:
            decorator = resource_attr(uri)
            decorator(capabilities_resource)
            return
        except Exception:
            pass

    if hasattr(mcp, "add_resource"):
        try:
            mcp.add_resource(
                capabilities_resource,
                uri=uri,
                name=name,
                description=description,
                mime_type=mime_type,
            )
            return
        except Exception:
            pass

    raise RuntimeError("Unable to register medium://capabilities resource with installed MCP SDK API")

