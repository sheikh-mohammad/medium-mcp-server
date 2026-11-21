# Documentation

Research, specification, planning, and compatibility docs for the Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) Medium server in this repository.

For install, quickstart, configuration, and current tool/resource/prompt surface, see the [project README](../README.md).

## Specification & planning

- [Medium MCP Server — Product & Technical Specification](./spec.md) — draft v0.1 source of truth for goals/non-goals, capability modes, MCP surface, safety model, transports, testing, and roadmap.
- [MVP implementation plan (phases 0–4)](./medium-mcp-server-mvp-implementation-plan.md) — implementation-oriented plan, phase breakdown, and verification notes.

## Compatibility & operations

- [Compatibility matrix](./compatibility-matrix.md) — verified vs unverified host/client/transport status and guidance for recording manual verification evidence.

## Packaging & release

- [Project README: Packaging & release](../README.md#packaging--release) — local build/pip install verification, release workflow triggers, and required PyPI/TestPyPI/GitHub Packages/GHCR setup.

## Research docs

- [Medium platform integration research (2026)](./research-medium-platform.md) — official Medium API status/capabilities/limitations, unofficial/community alternatives, feasibility, auth UX, and ToS/risk considerations.
- [MCP, Python implementation, and client compatibility](./research-mcp-python-and-compatibility.md) — MCP primitives/lifecycle/transports, Python SDK implementation guidance, transport compatibility, deployment/auth/security, testing, and pitfalls.
- [Existing servers/integrations and recommended architecture](./research-existing-servers-and-architecture.md) — adjacent blogging/CMS MCP patterns, lessons learned, and recommended capability-gated architecture.

## Reference material

- [Connector-Native Apps: A Remote MCP Server Whose Customer Is an AI](./af-v1-chap.md) — external reference on connector-native MCP design (gateway, verified identity, fail-closed behavior, session gating). Source: [Agent Factory](https://agentfactory1.panaversity.org/docs/connector-native-apps).

## Notes

- Host/client MCP support (especially remote/web connectors) is evolving; treat unverified entries in the compatibility matrix as requiring validation for your target environment.
- If implementation changes the MCP surface, safety model, or capability claims, update `docs/spec.md` accordingly.
