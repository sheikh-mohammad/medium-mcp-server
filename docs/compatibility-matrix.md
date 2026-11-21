# Medium MCP Server — Compatibility Matrix (MVP)

This matrix records **verified** and **unverified** MCP host/client compatibility for the current release (`1.0.0`, phases 0–4 complete). The server targets portable MCP behavior over **stdio** (local) and **Streamable HTTP** (remote), but real-world host support and connector UX vary by client/version.

> **Status date:** 2026-11-19  
> **Verification basis:** automated tests/contract checks and local CLI diagnostics in this repository (`pytest`, `ruff`, `mypy`, `doctor`, server surface/contract tests). Interactive per-host UI verification is mostly not automated here and is marked accordingly.

## Verified in-repo (automated/local)

| Target | Transport | Status | What was verified | Notes / limitations |
|---|---|---|---|---|
| Python package CLI (`python -m medium_mcp_server`, `medium-mcp-server`) | stdio / streamable-http (config) | **Verified** | `--help`, `--version`, `doctor` output, redacted config diagnostics, capability reporting without token | `doctor` is a local diagnostic command, not an MCP client session by itself. |
| MCP server assembly & surface (SDK in-process harness) | n/a (in-process) | **Verified** | Tool/resource/prompt registration and contracts, capability/resource payloads, export/prepare/feed/official-api-gated behavior, publish confirmation enforcement | Verified via contract/integration/unit tests in `tests/`. |
| Export/prepare modes (no credentials) | stdio-capable surface | **Verified** | `prepare_post`, `render_medium_content`, `export_post_bundle` (inline-only), template/latest-export resources, deterministic outputs | No Medium credentials required. |
| Public feed read mode | stdio-capable surface | **Verified** | `read_public_feed` normalization, bounds, warnings, mocked HTTP/fixture parsing and error handling | Public-only, best-effort; live Medium feed behavior may vary. |
| Official API mode (gated) | stdio-capable surface | **Verified (mocked)** | Token/config gating, fail-closed unsupported/auth behavior, profile/publications/draft/upload/publish flows, confirmation gate, local dedupe safeguards | Live Medium legacy API/token availability is **uncertain** and not verified in CI here. |
| Streamable HTTP runtime wiring | Streamable HTTP | **Partially verified** | Code paths support SDK run/async/app fallbacks; localhost-safe defaults and deployment guidance documented | Full protocol/session interoperability against external MCP clients is **not** fully verified in this environment. |

## Host/client matrix (manual verification status)

| Host/client | Transport(s) | Auth/config mode | Status | Verified now? | Notes |
|---|---|---|---|---|---|
| MCP Inspector (local) | stdio, Streamable HTTP | env/CLI config | **Unverified (manual)** | No | Recommended for interactive smoke tests (`tools/list`, resources, prompts, calls) against both transports. |
| Claude Desktop | stdio (local) | env `MEDIUM_TOKEN` optional | **Unverified** | No | Expected to work with standard local stdio command config; verify in-app tool discovery and calls. |
| Claude Code | stdio (local) | env/host config | **Unverified** | No | Expected compatible for local MCP stdio servers; verify with your Claude Code MCP configuration. |
| Cursor | stdio (local) | env/host config | **Unverified** | No | Verify MCP server registration, tool discovery, and `doctor`-guided setup. |
| VS Code (MCP-capable agents/extensions) | stdio (local), possibly HTTP depending client | env/host config | **Unverified** | No | Behavior depends on the specific MCP-enabled extension/client. |
| Windsurf | stdio (local) | env/host config | **Unverified** | No | Verify with Windsurf MCP configuration and local command launch. |
| OpenAI Codex CLI / terminal MCP clients | stdio (local), Streamable HTTP (if supported) | env/CLI config | **Unverified** | No | Stdio is the safest baseline; confirm client-specific MCP support/version. |
| ChatGPT (web/desktop connectors) | Streamable HTTP / product-specific | remote deployment + product auth/config | **Unverified / product-specific** | No | Support for arbitrary third-party remote MCP servers is client/product-dependent and evolving. Do not assume parity. |
| Claude web / other web AI surfaces | Streamable HTTP / product-specific | remote deployment + product auth/config | **Unverified / product-specific** | No | Verify per product; remote server must be deployed securely (TLS/proxy/auth/origin protections). |
| Gemini surfaces/tools | varies by product | varies | **Unverified / product-specific** | No | MCP support differs by Gemini product/tooling; verify current capabilities. |

## Configuration notes (for verification)

- **Stdio:** launch `python -m medium_mcp_server` or `medium-mcp-server` with env vars (e.g. `MEDIUM_TOKEN`) and no stdout logging contamination (enforced by design).
- **Streamable HTTP:** `medium-mcp-server serve --transport streamable-http --host 127.0.0.1 --port 8000 --path /mcp` for local dev. Remote deployments must add TLS, reverse-proxy auth/origin/DNS-rebinding protections, rate limiting, and request/size controls.
- **No built-in multi-tenant auth:** MVP Streamable HTTP is localhost/deployment-hook oriented.
- **Capability model:** export/prepare and public feed read work without credentials; official Medium API tools are capability-gated and may be unavailable depending on token/account/Medium platform state.

## How to update this matrix

When verifying a host/client, record: client name + version/date, OS, transport, config used (redacted), tools/resources/prompts tested, pass/fail notes, and known limitations. Update rows from **Unverified** to **Verified** only with concrete evidence.
