# Documentation

Research and reference docs for building a Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for Medium, intended to be connectable to coding agents, terminal CLIs, desktop apps, and web-based AI clients (ChatGPT, Claude, Gemini, etc.).

## Research docs

- [Medium platform integration research (2026)](./research-medium-platform.md) — official Medium API status/capabilities/limitations, unofficial/community alternatives (feeds, libraries, automation), realistic feasibility, auth UX, and risks/ToS considerations.
- [MCP, Python implementation, and client compatibility](./research-mcp-python-and-compatibility.md) — MCP primitives/lifecycle/transports, Python SDK/FastMCP implementation guidance, stdio vs Streamable HTTP compatibility across client types, deployment/auth/security, testing/debugging, and pitfalls.
- [Existing servers/integrations and recommended architecture](./research-existing-servers-and-architecture.md) — survey of Medium-adjacent blogging/CMS MCP patterns, lessons learned, and a recommended capability-gated architecture/MVP plan for this project.

## Planned implementation guides

- Installation and Medium token/setup configuration
- Claude Desktop and Claude Code
- ChatGPT connectors and web-based AI client notes
- Gemini and other MCP-capable clients
- Cursor, VS Code, and other IDE-based agents
- Terminal and custom MCP clients
- Streamable HTTP and remote deployment
- Tool/resource/prompt reference and examples

Documentation is being expanded alongside implementation. For project overview and roadmap, see the [project README](../README.md).
