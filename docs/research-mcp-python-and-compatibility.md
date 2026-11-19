# MCP, Python Implementation, and Client Compatibility Research (2026)

*Research date: 2026-11-19. Scope: design inputs for a **Python** MCP server for Medium that should be connectable to coding agents, terminal CLIs, desktop apps, and web-based AIs (ChatGPT, Claude, Gemini, etc.).*

## Executive summary

- **MCP** standardizes how AI hosts/clients discover and use external capabilities exposed by servers over JSON-RPC. The core primitives are **tools** (model-invoked actions), **resources** (application/client-supplied context), and **prompts** (user-invoked templates); optional capabilities include **sampling**, **roots**, **logging**, **progress/cancellation**, and other negotiated features.
- **Transports:** **stdio** is the simplest and most broadly supported transport for local servers launched by a host (IDE/CLI/desktop). **Streamable HTTP** is the current remote/network transport in modern MCP specs and is the right choice for hosted/shared servers. Legacy **HTTP+SSE** appears in older implementations but should not be the primary target for new builds.
- **Python options:** the official Python SDK (`mcp`, [`modelcontextprotocol/python-sdk`](https://github.com/modelcontextprotocol/python-sdk)) is the baseline choice. It includes a high-level server API (FastMCP-style ergonomics in modern SDKs) for defining tools/resources/prompts with Python types/schemas, plus lower-level primitives and transport helpers. For production servers, pair it with explicit validation, structured errors, stderr/file logging, and `pyproject.toml`-based packaging.
- **"Connect to all types" reality (Confirmed vs evolving):** stdio support is broad across local coding agents, terminals, and desktop MCP hosts. Streamable HTTP enables remote connectivity, but support for connecting arbitrary third-party remote MCP servers from web-based assistants (ChatGPT/Claude/Gemini web surfaces) is **client/product-specific and evolving**. A practical compatibility strategy is to **ship both stdio and Streamable HTTP**, keep tool schemas portable, provide copy-paste host configs, and document per-client limitations.
- **Recommended baseline for this project:** Python 3.10+ (verify current SDK requirement), official `mcp` SDK, stdio + Streamable HTTP transports, capability-gated tools (given Medium API constraints), strong secret handling, and MCP Inspector + automated contract tests.

> **Evidence note:** Some client-integration details (especially web-hosted ChatGPT/Claude/Gemini connector behavior) change frequently. This document distinguishes generally confirmed MCP/spec/SDK facts from client-specific or evolving areas and includes canonical sources for verification.

## 1) MCP overview (implementation-relevant)

### 1.1 Architecture and roles

| Role | Responsibility | Examples |
|---|---|---|
| **Host** | User-facing application; manages UX, permissions/consent, model choice, and one or more MCP clients | IDE agent, desktop AI app, chat client, CLI agent runtime |
| **Client** | Protocol endpoint inside the host; maintains a 1:1 session with a server and exchanges JSON-RPC messages | Built-in MCP connector/runtime in the host |
| **Server** | Exposes capabilities/context (tools/resources/prompts) and executes domain logic | Local filesystem/DB server, SaaS/blogging server, remote API adapter |

**Key properties**
- **JSON-RPC 2.0** request/response/notification semantics over a transport.
- **Stateful session** after initialization/capability negotiation.
- **Capability negotiation:** server and client declare supported features; unsupported features must not be assumed.
- **Host policy boundary:** hosts decide whether/how to surface tools, request approval, and pass results to models.

### 1.2 Core primitives

| Primitive | Controlled by (typical) | Purpose | Common operations |
|---|---|---|---|
| **Tools** | Model (with host/user approval policies) | Perform actions / computations / side effects | `tools/list`, `tools/call` |
| **Resources** | Application/client-supplied context | Expose readable data/context by URI (files, records, docs, generated context) | `resources/list`, `resources/read`, `resources/templates/list` (if supported), subscriptions/updates (capability-dependent) |
| **Prompts** | User-invoked workflows/templates | Reusable prompt templates with arguments that guide consistent interactions | `prompts/list`, `prompts/get` |
| **Sampling** | Server-initiated (via client/host, capability-dependent) | Ask the client/host to run LLM generation on the server's behalf | e.g. `sampling/createMessage` patterns (verify exact method/capability names for target spec/SDK) |
| **Roots** | Client-declared | Communicate filesystem/workspace boundaries relevant to server operations | capability/notification patterns vary by spec/client |
| **Logging / progress / cancellation** | Mixed | Diagnostics, long-running operation updates, cooperative cancellation | notifications/requests as supported |

**Design guidance**
- Prefer **tools** for explicit operations (especially writes) with narrow, well-described schemas.
- Prefer **resources** for browsable/readable context and stable URI-addressable data.
- Prefer **prompts** for repeatable user workflows (draft generation, preflight checks) without hiding side effects.
- Treat **sampling/roots/subscriptions** as optional enhancements; implement graceful fallback when unsupported.

### 1.3 Lifecycle and capability negotiation (high level)

1. **Connect/launch:** host starts server process (stdio) or connects to endpoint (HTTP).
2. **Initialize:** client/server exchange protocol version and capabilities.
3. **Operate:** discovery (`*/list`), reads (`resources/read`, `prompts/get`), invocations (`tools/call`), notifications (progress/logs), optional subscriptions.
4. **Shutdown:** transport/session closes; server releases resources (DB pools, handles, temp files).

**Implementation implications**
- Handlers must be safe under repeated/invalid calls and respect negotiated capabilities.
- For remote servers, plan session/state handling per transport/SDK behavior.
- Distinguish protocol errors from domain/tool errors and return actionable, sanitized messages.

### 1.4 Transports: stdio, Streamable HTTP, legacy SSE

| Transport | Best for | Pros | Trade-offs / requirements |
|---|---|---|---|
| **stdio** | Local servers launched by host (CLI, IDE, desktop) | Simple deployment, no network exposure, easy env-based secrets, broadly supported | Tied to host process; **stdout must be protocol-only** (logs to stderr); local-only unless wrapped |
| **Streamable HTTP** (current remote transport) | Remote/shared/hosted servers, web or multi-client access | Network-accessible, standard HTTP infra, supports streaming semantics per spec/SDK | Requires authn/authz, TLS, origin/session protections, rate limiting, ops/observability |
| **HTTP+SSE** (legacy/older pattern) | Backward compatibility with older clients/servers | Historical ecosystem presence | Superseded for new designs in modern spec lines; avoid as primary unless a target client requires it |

**Transport selection for this project**
- **Must-have:** stdio (max compatibility with coding agents/terminal/desktop hosts).
- **Strongly recommended:** Streamable HTTP (remote/web-hosted and future-facing client integrations).
- **Optional:** legacy SSE only if a specific required client cannot use Streamable HTTP (verify before adding complexity).

## 2) Python implementation options and best practices

### 2.1 SDK choices

| Option | Status / fit | Notes |
|---|---|---|
| **Official Python SDK: `mcp`** (`modelcontextprotocol/python-sdk`) | **Recommended baseline** | Canonical implementation path, protocol/types/transports, examples, and ongoing spec alignment. Prefer this for long-term compatibility. |
| **FastMCP-style API** | **Recommended developer experience (where provided by SDK/version)** | High-level decorators/registration patterns for tools/resources/prompts; reduces boilerplate. Modern Python MCP ecosystems commonly use FastMCP ergonomics; confirm exact import/API in the installed `mcp` version. |
| **Low-level SDK server primitives** | Use when needed | More control for custom transports, advanced capability handling, or specialized runtimes. Higher implementation effort. |

**Practical recommendation:** target the official `mcp` SDK and pin versions; prefer its high-level API for rapid, typed tool/resource/prompt definitions, but keep domain logic in transport-agnostic modules.

### 2.2 Suggested project structure

```text
medium-mcp-server/
  pyproject.toml
  README.md
  src/
    medium_mcp_server/
      __init__.py
      __main__.py              # CLI entrypoint (stdio / http)
      server.py                # MCP server assembly (register tools/resources/prompts)
      config.py                # settings/env parsing (no secret logging)
      domain/
        models.py              # post/profile/publication models
        transforms.py          # markdown/html/canonical/tag normalization
      adapters/
        medium_official.py     # official API adapter (capability-gated)
        medium_feeds.py        # RSS/Atom read adapter
        export.py              # export/draft bundle fallback
      auth/
        tokens.py              # token loading/validation abstractions
      errors.py                # domain -> MCP/tool error mapping
  tests/
    unit/
    integration/
    contract/
```

**Principles**
- Keep **domain/adapters** independent from MCP transport so stdio and HTTP share the same behavior.
- Centralize config and secret loading; validate early with actionable errors.
- Make capabilities explicit (e.g. `export-only`, `feed-read`, `official-api`) based on available credentials/backends.

### 2.3 Defining tools, resources, and prompts (Python)

#### Tools
- Use clear verb-oriented names: `get_profile`, `list_publications`, `create_draft`, `prepare_post`, `render_export`.
- Define **typed input schemas** (type hints / Pydantic / JSON-schema-compatible models as supported by SDK version) and validate business rules server-side.
- Separate **read/prepare** from **mutating/publishing** tools; require explicit confirmation flags for publish actions.
- Return bounded, structured results (IDs, URLs, warnings, capability flags) plus concise text content.

#### Resources
- Use stable URIs, e.g. `medium://capabilities`, `medium://profile`, `medium://publications`, `medium://feeds/{handle}` (if implemented).
- Enforce scope/visibility (public feed vs authenticated data).
- Paginate and summarize large reads.

#### Prompts
- Provide reusable workflows: "draft a Medium post from notes", "cross-post with canonical URL checklist", "preflight before publish".
- Keep prompts deterministic in structure; no hidden side effects.

**Illustrative (conceptual) shape — verify exact API for installed SDK version:**
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("medium-mcp-server")

@mcp.tool()
def get_capabilities() -> dict:
    """Report enabled backends and supported operations."""
    return {"mode": "export-only", "can_publish": False}

@mcp.resource("medium://capabilities")
def capabilities_resource() -> str:
    return '{"mode":"export-only","can_publish":false}'
```

### 2.4 Schemas, validation, and error handling

- **Schema first:** required/optional fields, enums, bounds (e.g. tag count, content format), URL validation for canonical links.
- **Layered validation:** (1) protocol/schema, (2) domain rules/authz scope, (3) upstream API/feed checks.
- **Error taxonomy:** validation/user-correctable, auth/permission, not found, unsupported-in-current-mode, rate-limit/upstream transient, timeout/cancelled, internal.
- **Sanitization:** never expose secrets, raw tokens, cookies, stack traces, or sensitive upstream payloads in tool results.
- **Idempotency:** Medium create operations may lack idempotency keys; accept a client-provided idempotency key/source hash and dedupe where possible to reduce duplicate drafts on retries.

### 2.5 Logging, observability, and runtime behavior

- **stdio rule:** never write non-protocol output to stdout; log to **stderr** or files.
- Use structured logs with correlation/request identifiers and redaction.
- Record audit events for mutating operations (create/upload/publish attempts, outcomes) without storing secrets/content unnecessarily.
- Set timeouts, bounded retries (safe/idempotent reads only, or carefully guarded writes), and payload/response size limits.

### 2.6 Auth patterns

| Context | Recommended pattern |
|---|---|
| Local stdio (single user) | Token/credentials from env vars or host secret store (e.g. `MEDIUM_TOKEN`), loaded at startup/on demand |
| Remote Streamable HTTP (shared/multi-user) | Strong request authentication/authorization (bearer/OAuth patterns per current MCP auth guidance), per-user/session scoping, TLS, token rotation/expiry |
| Optional/legacy OAuth app flows | Only if registration/credentials are actually available and maintainable; isolate in auth module |

**Security baseline:** least privilege, draft-first defaults, explicit confirmation for publish, secret redaction, and clear capability reporting when auth is missing/invalid.

### 2.7 Packaging and distribution (Python)

- Use `pyproject.toml` (PEP 621) with pinned/compatible dependency ranges and a console script entrypoint (e.g. `medium-mcp-server`).
- Support easy local execution via `python -m ...`, `pip`, and ideally `pipx`/`uvx` for stdio host configs.
- Publish to PyPI when stable; provide container image for remote Streamable HTTP deployments.
- Ship copy-paste host configuration snippets (stdio command/args/env and HTTP URL/auth) and a `--help`/capabilities/doctor command if feasible.
- Version tool schemas/capabilities carefully; document breaking changes.

## 3) Client and transport compatibility (broad support strategy)

### 3.1 Compatibility matrix (practical)

| Client category | Typical transport | Support level (general) | Notes |
|---|---|---|---|
| **Terminal/CLI coding agents** (agent runtimes, local tools) | stdio (local process) | **Broadly supported / confirmed pattern** | Configure command + args + env; best initial target for developers. |
| **IDE coding agents** (Cursor, VS Code, Windsurf, JetBrains-integrated tools, etc.) | stdio; sometimes HTTP depending on client | **Broad and growing (confirmed pattern), client-specific config UX** | Provide stdio-first config; document workspace/env handling. |
| **Claude Desktop / local desktop MCP hosts** | stdio (common), remote options evolving by product | **Broad for local stdio (confirmed pattern)** | Local stdio is the safest interoperability baseline. |
| **Claude Code / developer CLIs** | stdio | **Broad for local stdio (confirmed pattern)** | Good fit for repo-local workflows and publishing automation with approvals. |
| **ChatGPT (web/desktop/app integrations)** | Product-specific connectors/remote integrations | **Client/product-specific, evolving** | Do not assume arbitrary local stdio or arbitrary remote MCP URL works in every ChatGPT surface; verify current connector/MCP support and auth requirements per product mode. |
| **Gemini (web/CLI/IDE ecosystem)** | Varies by tool/product | **Client/product-specific, evolving** | Some Gemini developer tools support MCP patterns; web-app support for arbitrary third-party MCP servers may differ. Provide Streamable HTTP endpoint and verify per target client. |
| **Other web-based AI clients** | Usually remote HTTP/connector frameworks | **Varies widely** | Streamable HTTP + standards-compliant auth and clear schemas maximize chances, but conformance must be tested per client. |

### 3.2 How to maximize "connect to all types"

1. **Implement both transports:** stdio for universal local interoperability; Streamable HTTP for remote/web-hosted clients.
2. **Keep the core MCP surface portable:** standard tools/resources/prompts, simple JSON-schema-compatible inputs, deterministic outputs, no client-specific extensions required.
3. **Offer multiple config presets:** local stdio (`command/args/env`) and remote HTTP (`url` + auth headers/tokens) examples.
4. **Graceful capability degradation:** expose `capabilities` so clients/models understand what is currently possible (e.g. draft-only vs export-only).
5. **Test against representative hosts:** at least one CLI agent flow, one desktop host, one IDE host, and (when available) one remote/web client path via Streamable HTTP.
6. **Document reality clearly:** mark which integrations are verified vs unverified for specific ChatGPT/Gemini/Claude web surfaces at release time.

## 4) Deployment and connectivity patterns

| Pattern | Use case | Notes |
|---|---|---|
| **Local stdio process** | Personal/dev workflows, coding agents, desktop apps | Lowest latency/setup friction; secrets via env/host config; no inbound network exposure |
| **Remote Streamable HTTP server** | Shared/team use, centralized credentials/policies, web clients | Run behind TLS (reverse proxy) with auth, rate limits, logging, and health checks |
| **Tunnel/proxy to local server** (ngrok, Cloudflare Tunnel, etc.) | Development/demo of remote clients against local machine | Convenient but operationally sensitive; secure with auth, short-lived URLs, and least-privilege tokens |
| **Containerized deployment** | Reproducible remote hosting/CI | Good for HTTP mode; inject config/secrets at runtime; include readiness/liveness and observability |

**Remote security checklist (Streamable HTTP)**
- TLS for non-local traffic; bind to localhost for local-dev HTTP unless remote access is intentional.
- Authenticate and authorize every request; scope credentials per user/tenant where applicable.
- Validate `Origin` / apply DNS-rebinding protections as required by spec and deployment context.
- Protect session identifiers/state; implement rate limiting and abuse controls.
- Redact secrets and sensitive content in logs/errors; audit mutating actions.

## 5) Testing and debugging

### 5.1 MCP Inspector (interactive)
- **MCP Inspector** is the standard tool for interactively exercising MCP servers: list tools/resources/prompts, invoke calls, inspect request/response behavior, and debug schema/transport issues.
- Typical local usage involves launching Inspector (commonly via `npx`) against your server command/transport; verify against current Inspector docs for exact invocation.
- Use it to validate both **stdio** and **Streamable HTTP** modes (if supported), including failure paths.

### 5.2 Automated testing strategy

| Layer | Focus | Examples |
|---|---|---|
| **Unit** | Pure logic, transforms, validators, error mapping | Markdown/HTML normalization, tag/canonical validation, capability gating |
| **Integration** | Adapters and server handlers with mocked upstreams | Official API client behavior, RSS parsing, auth failures/timeouts, retry/idempotency guards |
| **Contract** | MCP surface stability | `tools/list` schema snapshots, tool I/O contracts, resource URI behavior |
| **Transport/E2E** | Real MCP client-session flows | stdio session via SDK/client harness; Streamable HTTP request/stream handling |
| **Security/negative** | Abuse and leakage prevention | secret redaction, invalid origins/auth, prompt-injection-influenced unsafe publish attempts blocked by confirmation/capability checks |

### 5.3 Common pitfalls
- Writing logs/debug prints to **stdout** in stdio mode (corrupts protocol).
- Relying on capabilities not negotiated/supported by the client.
- Oversized/unbounded tool outputs (hurts reliability and model context).
- Treating schema validation as authorization (must enforce server-side checks).
- Assuming Medium supports edit/delete/list via official API (it generally does not) or assuming web AI clients all support the same MCP connection method.
- Missing timeouts/retries/idempotency safeguards for upstream/network operations.

## 6) Practical recommendations for this project

- **Transport:** implement `stdio` and `Streamable HTTP` from day one behind shared server/core logic.
- **SDK/runtime:** official Python `mcp` SDK, pinned version, Python 3.10+ (verify), `pyproject.toml` packaging with console entrypoint.
- **MCP surface:** capability-aware tools/resources/prompts; draft-first and export-safe defaults due to Medium constraints.
- **Compatibility posture:** "works everywhere local MCP stdio works; works remotely where Streamable HTTP MCP clients/connectors are supported" — publish verified client matrix over time.
- **Quality gates:** MCP Inspector checks, schema/contract tests, and security/redaction tests before release.

## Sources

### Official MCP specification and documentation
- [Model Context Protocol — Official site](https://modelcontextprotocol.io/)
- [MCP Specification (latest entry point)](https://modelcontextprotocol.io/specification/latest)
- [MCP Specification — 2025-11-25 (index)](https://spec.modelcontextprotocol.io/specification/2025-11-25/)
- [MCP Basic: Transports (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/transports/)
- [MCP Basic: Lifecycle (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle/)
- [MCP Basic: Authorization (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/authorization/)
- [MCP Server: Tools (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/server/tools/)
- [MCP Server: Resources (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/server/resources/)
- [MCP Server: Prompts (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/server/prompts/)
- [MCP Docs: Build a server](https://modelcontextprotocol.io/docs/develop/build-server)
- [MCP Docs: Connect local servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [MCP Specification repository](https://github.com/modelcontextprotocol/specification)

### Official SDKs, tools, and ecosystem references
- [MCP Python SDK (`modelcontextprotocol/python-sdk`)](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Python SDK package (`mcp` on PyPI)](https://pypi.org/project/mcp/)
- [MCP TypeScript SDK (`modelcontextprotocol/typescript-sdk`)](https://github.com/modelcontextprotocol/typescript-sdk) *(useful cross-reference for transport/client behavior and examples)*
- [MCP Inspector (`modelcontextprotocol/inspector`)](https://github.com/modelcontextprotocol/inspector)
- [MCP servers/examples repository (`modelcontextprotocol/servers`)](https://github.com/modelcontextprotocol/servers)
- [FastMCP (community/project documentation and source)](https://github.com/jlowin/fastmcp) *(FastMCP-style ergonomics are widely used; verify relationship/versioning with the official `mcp` SDK you adopt)*

### Client/product integration references (verify current status per client)
- [Anthropic/Claude MCP documentation entry points](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
- [OpenAI developer/platform documentation](https://platform.openai.com/docs) *(MCP/connector support is product-specific and evolving; verify current ChatGPT/client capabilities)*
- [Google AI / Gemini developer documentation](https://ai.google.dev/gemini-api/docs) *(MCP/tooling support varies by Gemini surface/product; verify current capabilities)*

*Verification reminder: protocol revisions, SDK APIs, and host/client MCP support evolve. Re-validate spec version, transport/auth requirements, and per-client configuration before implementation and release.*
