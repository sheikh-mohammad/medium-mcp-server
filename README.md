# Medium MCP Server

A Python [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for working with Medium content from MCP-capable coding agents, terminals, desktop apps, and (where supported) remote/web AI clients.

This server is **capability-gated** and **draft-first**. It is designed to stay useful even when Medium official API access is unavailable by providing deterministic content preparation/export and best-effort public feed reads, while exposing official Medium API write/read operations only when explicitly configured and available.

> **Status:** MVP implemented (Phases 0–4 complete). Official Medium API availability for tokens/accounts is legacy/uncertain in practice; the server fails closed and provides export/manual alternatives when capabilities are unavailable.

## What it provides

- **Always-on export/prepare mode (no credentials):** validate/normalize drafts, render Medium-compatible content with warnings, and generate inline export bundles/manifests.
- **Public feed read mode (no credentials):** best-effort public RSS/Atom feed reading for user/publication/tag/URL sources with bounds and warnings.
- **Official Medium API mode (optional, token-gated):** profile/publications lookup, draft creation, optional image upload, and explicit-confirm publish when a valid legacy token is configured and usable.
- **Transports:** `stdio` (local baseline) and `Streamable HTTP` (remote-capable, localhost/deployment-hook posture in MVP).
- **Safety model:** explicit capability reporting, draft-first defaults, `publish_post` requires `confirm=true`, no blind create retries, short-lived local dedupe safeguards, redacted diagnostics/logging, and actionable fail-closed errors.

## Requirements

- Python **3.10+**
- `pip` (or compatible installer such as `uv`)
- Optional: a legacy Medium integration token (`MEDIUM_TOKEN`) **only** if you want to attempt official API operations

## Installation

### From source (recommended for this repo)

```bash
python -m venv .venv
# Windows PowerShell
. .venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -e .
```

For development and verification:

```bash
pip install -e ".[dev]"
```

For Streamable HTTP fallback/runtime helpers (optional):

```bash
pip install -e ".[http]"
```

## Quickstart

### 1) Check diagnostics (redacted)

```bash
medium-mcp-server doctor
# or
python -m medium_mcp_server doctor
```

This prints effective transport/config (redacted), capability/mode status, and actionable setup notes.

### 2) Run over stdio (local MCP hosts)

```bash
medium-mcp-server serve --transport stdio
# or
python -m medium_mcp_server --transport stdio
```

- Protocol messages use stdout; logs go to stderr/file.
- Export/prepare and public feed tools work without `MEDIUM_TOKEN`.

### 3) Run over Streamable HTTP (local dev / remote-capable)

```bash
medium-mcp-server serve --transport streamable-http --host 127.0.0.1 --port 8000 --path /mcp
```

Defaults are localhost-safe for local development. For remote deployments, place behind TLS and reverse-proxy authentication/origin protections/rate limiting (see [Security & deployment](#security--deployment-notes)).

## MCP client configuration examples

> Exact host-specific config formats vary by client/version. Verify with your client docs and the [compatibility matrix](docs/compatibility-matrix.md).

### Stdio example (generic MCP host)

```json
{
  "mcpServers": {
    "medium": {
      "command": "medium-mcp-server",
      "args": ["serve", "--transport", "stdio"],
      "env": {
        "MEDIUM_TOKEN": "<optional-legacy-medium-integration-token>"
      }
    }
  }
}
```

Alternative module form:

```json
{
  "mcpServers": {
    "medium": {
      "command": "python",
      "args": ["-m", "medium_mcp_server", "serve", "--transport", "stdio"],
      "env": {
        "MEDIUM_TOKEN": "<optional-legacy-medium-integration-token>"
      }
    }
  }
}
```

### Streamable HTTP example (local endpoint)

Run the server:

```bash
medium-mcp-server serve --transport streamable-http --host 127.0.0.1 --port 8000 --path /mcp
```

Then configure your MCP client/connector to connect to:

- `http://127.0.0.1:8000/mcp`

(Clients that support remote MCP endpoints differ; many local hosts prefer stdio.)

## Configuration

Precedence: **CLI args > environment variables > defaults**.

| Setting | CLI / env | Default | Purpose |
|---|---|---|---|
| Transport | `--transport` / `MCP_TRANSPORT` (`stdio` \| `streamable-http`) | `stdio` | MCP transport to run |
| HTTP host | `--host` / `MCP_HTTP_HOST` | `127.0.0.1` | Streamable HTTP bind host |
| HTTP port | `--port` / `MCP_HTTP_PORT` | `8000` | Streamable HTTP bind port |
| HTTP path | `--path` / `MCP_HTTP_PATH` | `/mcp` | Streamable HTTP endpoint path |
| Log level | `--log-level` / `LOG_LEVEL` | `INFO` | Logging verbosity |
| Log file | `--log-file` / `MEDIUM_MCP_LOG_FILE` | unset | Optional log file path (in addition to stderr) |
| Request timeout | `--request-timeout-seconds` / `REQUEST_TIMEOUT_SECONDS` | `30` | Timeout for upstream/feed/API requests |
| Medium API base URL | `--medium-api-base-url` / `MEDIUM_API_BASE_URL` | `https://api.medium.com/v1` | Override for testing/compat |
| Medium token | `MEDIUM_TOKEN` | unset | Legacy official API token (redacted in diagnostics/logs) |
| Unofficial mode flag | `MEDIUM_ENABLE_UNOFFICIAL` | `false` | Reserved; unofficial automation is **not implemented** in MVP |

> `MCP_HTTP_AUTH_TOKEN` is not enforced as built-in server auth in this MVP. Use deployment-level protections for remote HTTP.

## Capability model

- **`export` / `prepare` (always on):** no Medium credentials required.
- **`feed_read` (public, best-effort):** public RSS/Atom reads only; bounded, may be partial/unavailable.
- **`official_api` (optional):** enabled only when `MEDIUM_TOKEN` is configured and runtime capability/auth checks succeed; operations fail closed with alternatives when unavailable.

Use the `get_capabilities` tool or `medium://capabilities` resource to inspect effective modes, redacted auth state, limitations, and warnings at runtime.

## MCP surface (current)

### Tools

- `get_capabilities`
- `prepare_post`
- `render_medium_content`
- `export_post_bundle` (**inline-only in MVP**; path writes rejected)
- `read_public_feed`
- `get_profile` (official API, capability-gated)
- `list_publications` (official API, capability-gated)
- `create_draft` (official API, capability-gated, draft-first)
- `upload_image` (official API, capability-gated, support may vary)
- `publish_post` (official API, capability-gated, **requires `confirm=true`** for `public`/`unlisted`)

### Resources

- `medium://capabilities`
- `medium://templates/post`
- `medium://exports/latest` (when available in current runtime context)
- `medium://profile` (exposed when token is configured; read fails closed if unavailable)
- `medium://publications` (exposed when token is configured; read fails closed if unavailable)

### Prompts

- `draft_medium_post`
- `crosspost_checklist`
- `preflight_publish` (guidance only; never auto-publishes)

## Safety & deployment notes

- **Draft-first:** prefer `create_draft`; `publish_post` is confirmation-gated (`confirm=true`) and capability-gated.
- **No blind retries on create/upload/publish:** local short-lived dedupe safeguards reduce duplicate risk, but Medium has no native idempotency guarantee.
- **Fail closed:** unsupported/missing-auth operations return structured errors with alternatives (export/prepare/feed/manual steps).
- **Secret safety:** tokens/authorization/cookie/secret values are redacted in diagnostics and logs.
- **Content is untrusted input:** external feed/post content should be treated as data, not executable instructions.
- **Streamable HTTP (MVP posture):** localhost defaults; no built-in multi-tenant auth. For remote/shared use, deploy behind TLS and reverse-proxy auth, apply origin/DNS-rebinding protections, rate limiting, and request/size limits, and restrict network exposure.

## Development & verification

```bash
# tests
python -m pytest -q

# lint
python -m ruff check src tests

# type check
python -m mypy src

# diagnostics
python -m medium_mcp_server doctor --log-level WARNING
```

CI workflow: `.github/workflows/ci.yml` (ruff, mypy, pytest across supported Python versions).

## Docker (optional, Streamable HTTP)

A basic `Dockerfile` is included for Streamable HTTP deployments. Example:

```bash
docker build -t medium-mcp-server .
docker run --rm -p 8000:8000 \
  -e MEDIUM_TOKEN="$MEDIUM_TOKEN" \
  medium-mcp-server
```

In production, run behind TLS/reverse-proxy auth and appropriate network/origin/rate-limit controls.

## Limitations

- No guaranteed Medium post list/read/edit/delete parity (official API is limited/legacy).
- Official API token issuance/availability may be restricted or change without notice.
- Public feed reads are best-effort and public-only.
- Web/remote MCP connector support is host/product-specific and evolving (see compatibility matrix).
- `export_post_bundle` is inline-only in MVP (no filesystem path writes).

## Project documents

- [Product & technical spec](docs/spec.md)
- [Documentation index](docs/README.md)
- [Compatibility matrix](docs/compatibility-matrix.md)
- [MVP implementation plan (phases 0–4)](docs/medium-mcp-server-mvp-implementation-plan.md)
- [Changelog](CHANGELOG.md)
- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)

## License

Released under the [MIT License](LICENSE).
