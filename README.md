# Medium MCP Server

A Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that connects the Medium blogging platform to AI assistants and coding agents.

> **Status:** Under active development. This repository is being scaffolded now; install commands, tool names, and configuration examples will be finalized as the implementation lands.

## What is this?

MCP is an open standard that lets AI applications talk to external tools and data sources in a consistent way. This server exposes Medium's publishing capabilities as MCP **tools**, so an AI assistant can help you write, publish, and manage your Medium content from wherever you already work.

The server is written in Python and is designed to work with **any MCP-compatible host**, including:

| Host type | Examples |
| --- | --- |
| Coding agents & IDEs | Claude Code, Cursor, VS Code, Windsurf, Gemini CLI, OpenAI Codex CLI |
| Desktop apps | Claude Desktop, other desktop MCP clients |
| Web-based AIs | ChatGPT connectors, Claude.ai, Gemini and other MCP-capable web assistants |
| Terminal & custom clients | MCP Inspector, scripts, and your own agents using the MCP Python SDK |

## Planned capabilities

- Authenticate with Medium using a personal integration token
- Get the current user's profile and publication list
- Create posts and drafts on your profile or in a publication
- List posts and inspect published content
- Accept content in Markdown or HTML
- Work locally over **stdio** (for desktop/terminal agents) and over **Streamable HTTP** (for remote/web hosts)

The exact set of tools and their parameters will be documented here once implemented.

## Why an MCP server for Medium?

- **Write and publish in flow** — stay in your editor or AI chat instead of switching tabs.
- **One integration, many clients** — a single server works across desktop, terminal, IDE, and web assistants.
- **You stay in control** — your token, your content, and explicit tool calls before anything is published.

## Configuration (planned)

MCP hosts typically launch a local server over stdio or connect to a remote HTTP endpoint. A host configuration will look roughly like this:

```json
{
  "mcpServers": {
    "medium": {
      "command": "<python-or-uv-command>",
      "args": ["<server-entrypoint>"],
      "env": {
        "MEDIUM_TOKEN": "<your-medium-integration-token>"
      }
    }
  }
}
```

Exact commands, environment variables, and per-client setup guides (Claude Desktop, Cursor, ChatGPT, Gemini, etc.) will be added to [`docs/`](docs/) as the server is built.

## Getting started

Implementation is in progress. Once released, the flow will be:

1. Generate a Medium integration token from your Medium settings.
2. Install the package (`pip install ...` / `uvx ...`).
3. Add the server to your MCP host using the configuration above.
4. Ask your assistant to publish a draft or list your publications.

## Roadmap

- [ ] Core MCP server scaffold (Python, stdio + Streamable HTTP)
- [ ] Medium API client with token authentication
- [ ] Tools for profile, publications, and posts
- [ ] Markdown/HTML content conversion
- [ ] Setup guides for popular MCP hosts
- [ ] Tests, packaging, and PyPI release
- [ ] Remote hosted deployment option

## Project documents

- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Documentation index](docs/README.md)

## Contributing

Contributions are welcome. This project is at an early stage — open an issue to discuss a feature before sending a large pull request. Please never commit real API tokens; use environment variables instead.

## License

Released under the [MIT License](LICENSE).
