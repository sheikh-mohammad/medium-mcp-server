# Medium MCP Server — Product & Technical Specification

> **Status:** Draft v0.1 (spec-first). This document defines what to build and how to validate it, grounded in the research in [`docs/`](./README.md). Implementation details may be refined during development, but changes that affect the MCP surface, safety model, or capability claims must update this spec.
>
> **Research inputs:**
> - [Medium platform integration research (2026)](./research-medium-platform.md)
> - [MCP, Python implementation, and client compatibility](./research-mcp-python-and-compatibility.md)
> - [Existing servers/integrations and recommended architecture](./research-existing-servers-and-architecture.md)
> - [Connector-Native Apps (reference)](./af-v1-chap.md)
> - Project intent: [README](../README.md), [CHANGELOG](../CHANGELOG.md)

## 1. Purpose

Build a **Python Model Context Protocol (MCP) server** that helps AI assistants and coding agents work with Medium content safely and reliably across local and remote MCP hosts.

Because Medium's official API surface is legacy/limited and operationally uncertain, this server must remain useful **without** guaranteed write-capable Medium credentials. The core product value is: prepare, validate, and export Medium-ready content; discover capabilities honestly; optionally read public content; and, when explicitly configured and supported, perform safe draft/publish operations through capability-gated adapters.

## 2. Background & research synthesis

### 2.1 Platform reality (Medium)

- Official API base historically: `https://api.medium.com/v1` (legacy/uncertain availability for new tokens/apps in 2026; treat as optional).
- Documented capabilities (when available): authenticated profile (`/me`), user/publications lookup, create post/draft for user or publication, image upload.
- Not documented/unsupported by official API: list/read-back posts, edit/update, delete/unpublish, full draft lifecycle management, publication admin, analytics/comments, webhooks.
- Practical implications: **no full Medium parity**, **draft-first**, **no blind retries on create/publish**, provide export/manual fallback and clear capability reporting.
- Public RSS/Atom feeds are viable for **public, read-only** discovery/ingestion (best-effort, format/availability may vary). Unofficial browser/internal automation is high-risk (ToS, breakage, account/security) and must not be the default.

### 2.2 MCP & client reality

- Implement standard MCP primitives over JSON-RPC with capability negotiation: **tools**, **resources**, and **prompts** (optional advanced capabilities only if negotiated and useful).
- **Transports:** `stdio` is the primary local compatibility baseline (CLI/IDE/desktop agents). **Streamable HTTP** is required for remote/shared and many web/connector scenarios. Legacy HTTP+SSE is not a primary target.
- **Python stack:** official `mcp` Python SDK (pin version; verify minimum Python at implementation time, target Python 3.10+ unless SDK requires newer), high-level FastMCP-style ergonomics where available, transport-agnostic domain/adapters, `pyproject.toml` packaging and console entrypoint.
- **Compatibility posture:** "works wherever local MCP stdio is supported; works remotely where Streamable HTTP MCP clients/connectors are supported." Per-client ChatGPT/Claude/Gemini web behavior is product-specific and evolving; ship portable schemas/configs and maintain a verified compatibility matrix.

### 2.3 Design lessons from adjacent integrations & reference

- Expose **explicit capability discovery** and separate read/prepare/export from mutating actions.
- Keep domain logic independent of transport/auth/bootstrap.
- Prefer small, typed, deterministic tool schemas and structured results (IDs, URLs, mode, warnings, next actions).
- Enforce **human/explicit confirmation** for high-impact publish actions and fail with actionable, sanitized errors when prerequisites/capabilities are missing.
- "Connector-native" lesson applied here: the server must not rely on the model to supply trusted identity or to improvise when capabilities are unavailable; it must report state/capabilities truthfully and fail closed for unsupported operations.

## 3. Goals and non-goals

### 3.1 Goals

1. **Always-useful core:** content preparation, validation, rendering, and export work with no Medium credentials.
2. **Honest capability model:** runtime discovery of enabled modes/backends and supported operations; no implied parity.
3. **Safe writes (when available):** official API adapter is optional/capability-gated, draft-first, confirmation-gated for public publish, with dedupe guidance.
4. **Broad connectivity:** first-class `stdio` and `Streamable HTTP` support with shared behavior.
5. **Portable MCP surface:** clear tools/resources/prompts, typed schemas, bounded outputs, sanitized errors.
6. **Production-minded baseline:** secret handling, logging discipline (no stdout pollution in stdio), tests, and packaging suitable for local and remote use.

### 3.2 Non-goals (MVP / v1)

- Guaranteed full Medium feature parity (list/read/edit/delete all posts, publication admin, analytics, comments, paywalled/private content access).
- Officially supported Medium OAuth app onboarding flow (may be impossible/unavailable; treat as future/conditional).
- Unofficial browser automation, internal/GraphQL endpoint usage, or cookie/session scraping **by default**.
- Multi-tenant SaaS, billing, user accounts, or hosted control plane.
- Background sync/webhooks/event ingestion (Medium has no documented webhook model).
- Rich media asset management beyond what official image upload/feed/export paths safely support.

## 4. Users, hosts, and compatibility targets

| Audience / host type | Primary transport | Priority | Notes |
|---|---|---|---|
| Coding agents & IDE hosts (Claude Code, Cursor, VS Code, Windsurf, Codex CLI, Gemini CLI, etc.) | stdio (local) | P0 | Command+args+env config; workspace-agnostic operation |
| Desktop MCP apps (Claude Desktop and others) | stdio | P0 | Standard local server config |
| Terminal/custom MCP clients, scripts, Inspector | stdio, Streamable HTTP | P0 | Debuggability and contract stability |
| Remote/web connectors and hosted clients (ChatGPT/Claude/Gemini surfaces where supported) | Streamable HTTP | P1 | Product-specific; verify per client and document limits |
| Shared/team HTTP deployment | Streamable HTTP | P1/P2 | Requires real auth/TLS/ops hardening |

**Compatibility contract:** local stdio interoperability is a release gate for MVP; Streamable HTTP protocol compliance is a release gate for remote mode. Specific web-product connector support is documented as *verified/unverified* per tested client/version, not assumed.

## 5. Architecture principles

1. **Capability-gated:** every operation checks runtime capability/mode; unsupported operations return structured "unsupported in current mode" errors with alternatives (e.g. export).
2. **Draft-first, confirmation-gated:** create as draft by default; public/unlisted publish requires explicit confirmation and capability.
3. **Transport-agnostic core:** domain logic, validation, and adapters are shared; stdio and HTTP are thin runtime shells.
4. **Adapter isolation:** official API, feed reader, and export/prep are separate adapters behind interfaces; risky/unofficial adapters (future) are opt-in and isolated.
5. **Fail closed / no improvisation:** missing auth, unavailable backend, or ambiguous state must not be reported as success; tool results include warnings/next actions.
6. **Least privilege & secret safety:** no secret/cookie/token logging or echoing; mutating tools separated from read/prepare tools.
7. **Deterministic, bounded outputs:** typed results, pagination/limits, truncation notices where applicable.
8. **Content treated as untrusted input:** guard against prompt-injection-driven unsafe actions; require explicit intent/confirmation for side effects.

## 6. Capability modes

| Mode | Default | Auth required | Capabilities | Notes |
|---|---|---|---|---|
| **`export` / `prepare`** | **Always on** | No | Normalize/validate content, render Medium-compatible payloads, generate export bundle/manifests, templates/checklists | Baseline value with zero Medium access |
| **`feed_read`** | Auto/on when used (public) | No (public feeds) | Best-effort read of public RSS/Atom feeds for profiles/publications/tags; parse/normalize metadata and available content | Public-only; may be partial; respect fetch limits/timeouts |
| **`official_api`** | **Opt-in by config** | Yes (valid legacy token, e.g. `MEDIUM_TOKEN`) | `whoami`/profile, list contributor publications, upload image (if supported), create draft/post | Feature-gated by successful auth/capability probe; draft-first; no edit/delete/list-post claims |
| **`unofficial_automation`** | **Off by default (future, experimental)** | User-provided session/automation context | Potential UI-parity operations | Not in MVP; if ever added: explicit opt-in flag, prominent warnings, isolation, no default enablement |

**Capability resolution:** at startup and/or on-demand, compute effective capabilities from config + auth probe + adapter health. Expose via `get_capabilities` tool and `medium://capabilities` resource (redacting secrets). Cache probes briefly with safe refresh; never cache success after auth revocation without revalidation on failure.

## 7. MCP surface (tools, resources, prompts)

Naming: snake_case, verb-oriented, stable. All tools return structured, JSON-serializable content (plus text summary where useful) with `mode`, `warnings`, and `next_actions` fields when relevant. Mutating tools are clearly marked and require explicit intent.

### 7.1 Tools

#### 7.1.1 Discovery & diagnostics

| Tool | Mode | Description | Inputs | Output (key fields) | Side effects |
|---|---|---|---|---|---|
| `get_capabilities` | all | Report enabled modes, auth state (redacted), supported operations, and important limitations/warnings | none | `modes`, `active_capabilities`, `tools_available`, `limitations`, `version` | none |

#### 7.1.2 Content preparation & export (always-on)

| Tool | Mode | Description | Inputs (illustrative) | Output | Side effects |
|---|---|---|---|---|---|
| `prepare_post` | export | Validate and normalize a post draft into a canonical prepared representation | `title` (str), `content` (str), `content_format` (`markdown`\|`html`), `tags?` (str[]), `canonical_url?`, `license?`, `publish_status_intent?` (`draft`\|`public`\|`unlisted`), `publication_id?`, `idempotency_key?` | `prepared_post` (normalized), `validation` (errors/warnings), `medium_ready` (bool), `suggested_next_actions` | none |
| `render_medium_content` | export | Render prepared content to Medium-compatible payload/content and highlight fidelity warnings | `prepared_post` or raw fields, `target_format?` | `content_format`, `content`, `title`, `tags`, `metadata`, `warnings` | none |
| `export_post_bundle` | export | Produce an export bundle for manual publish/import/cross-posting | `prepared_post`, `output?` (`inline`\|`path`), `path?` (workspace-safe), `include_manifest?` | `bundle` (inline artifacts) or `written_paths`, `manifest` | optional local file writes **only within allowed workspace/path policy** |

**Validation rules (prepare/render):** non-empty title/content; `tags` max 5 (warn/truncate per policy, configurable default: warn and keep first 5 valid unique tags); canonical URL must be valid URL if provided; supported license enum; warn on potentially unsupported embeds/custom HTML and on lossy conversion.

#### 7.1.3 Public feed read

| Tool | Mode | Description | Inputs | Output | Side effects |
|---|---|---|---|---|---|
| `read_public_feed` | feed_read | Fetch and parse a public Medium RSS/Atom feed | `source` (handle/url/publication/tag identifier; normalized), `source_type?` (`user`\|`publication`\|`tag`\|`url`), `limit?` (bounded, default e.g. 10), `include_content?` (bool) | `items[]` (id/guid?, title, link, published_at, author?, summary/content snippet, tags?), `source`, `fetched_at`, `warnings` | outbound HTTP read (public) |

Constraints: best-effort parsing, timeouts, max bytes/items, robots/ToS-aware conservative behavior, no auth/cookies, no paywalled/private access claims.

#### 7.1.4 Official Medium API (capability-gated)

| Tool | Mode | Requires | Description | Inputs | Output | Side effects |
|---|---|---|---|---|---|---|
| `get_profile` | official_api | valid token | Fetch authenticated Medium user/profile | none | `user` (`id`, `username?`, `name?`, `url?`, `image_url?`), `mode` | API read |
| `list_publications` | official_api | valid token | List publications the user can contribute to | none | `publications[]` (`id`, `name`, `url`, `description?`, roles?) | API read |
| `upload_image` | official_api | valid token + support | Upload an image for use in content | `image_path` (workspace-safe) or `image_bytes_base64` + `media_type`, `filename?` | `url`, `md5?`, `warnings` | API write/upload (remote) |
| `create_draft` | official_api | valid token | Create a draft (user or publication) | `title`, `content_format`, `content`, `tags?`, `canonical_url?`, `license?`, `publication_id?`, `notify_followers?` (default false), `idempotency_key?` | `post` (`id?`, `url?`, `publish_status`, `publication_id?`), `dedupe` status, `warnings` | **remote create (draft)** |
| `publish_post` | official_api | valid token + `confirm=true` | Create/publish as `public` or `unlisted` (or submit to publication as supported) | same as draft + `publish_status` (`public`\|`unlisted`), **`confirm` (bool, must be true)**, `idempotency_key?` | `post`, `dedupe` status, `warnings` | **remote create/publish (high impact)** |

**Safety/behavior:**
- If `official_api` is unavailable, return `unsupported_capability` with export/prepare alternatives.
- `publish_post` without `confirm=true` must fail with a clear confirmation-required error (no side effect).
- Prefer calling/using `prepare_post`/`render_medium_content` first; tools may accept prepared input or perform equivalent validation.
- Dedupe: if `idempotency_key` (or computed content hash) was recently used successfully in-process/session cache, return prior result metadata/warning instead of creating a duplicate when possible; always warn that Medium API has no native idempotency guarantee.

### 7.2 Resources

| URI | Name | Mode | Description | MIME/type (logical) |
|---|---|---|---|---|
| `medium://capabilities` | capabilities | all | Current modes, supported ops, limitations, auth status (redacted) | application/json |
| `medium://profile` | profile | official_api | Authenticated profile snapshot when available | application/json |
| `medium://publications` | publications | official_api | Contributor publications when available | application/json |
| `medium://templates/post` | post-template | export | Canonical post template/examples and checklist metadata | text/markdown or application/json |
| `medium://exports/latest` | latest-export | export | Latest prepared/export metadata in current runtime context (if tracked) | application/json |

Resources are read-only, scoped, and bounded. Unsupported/unavailable resources return clear not-available errors (not empty success).

### 7.3 Prompts

| Prompt | Purpose | Arguments (illustrative) | Output intent |
|---|---|---|---|
| `draft_medium_post` | Turn notes/repo context into a Medium-ready draft | `source_notes`, `audience?`, `tone?`, `target_format?` | Prepared title/content/tags/canonical checklist using `prepare_post` conventions |
| `crosspost_checklist` | Preflight for syndication/cross-posting | `source_url?`, `draft_title?` | Canonical URL, license, tags, formatting/image rights, capability checks |
| `preflight_publish` | Safe publish review before any mutating call | `prepared_post_ref?`, `publish_status` | Verify capability/auth, show preview/warnings, require explicit confirmation step; never auto-publish |

Prompts guide workflow; they must not perform hidden side effects.

## 8. Data models & content handling

### 8.1 Core entities (conceptual)

- **CapabilityReport:** `modes`, `active_capabilities`, `auth` (boolean/provider/redacted details), `supported_tools`, `limitations[]`, `warnings[]`.
- **PreparedPost:** `title`, `content`, `content_format`, `tags[]`, `canonical_url?`, `license?`, `publish_status_intent`, `publication_id?`, `idempotency_key?`, `normalization_notes[]`.
- **Publication:** `id`, `name`, `url`, `description?`.
- **Profile:** `id`, `username?`, `name?`, `url?`, `image_url?`.
- **FeedItem:** `id/guid?`, `title`, `link`, `published_at?`, `author?`, `summary?`, `content?`.
- **OperationResult:** `ok`, `mode`, `data?`, `warnings[]`, `next_actions[]`, `error?` (structured on failure).

### 8.2 Content rules

- Supported authoring inputs: Markdown and HTML (as provided). Canonical internal handling should preserve source intent and produce Medium-compatible output with explicit warnings for unsupported constructs.
- Normalize line endings/whitespace conservatively; do not silently drop meaningful content.
- Validate/enforce: tags count/shape, URL validity, license enum, non-empty required fields, payload/size bounds.
- Image handling: MVP supports references/URLs in content and, when `official_api` + upload supported, validated image upload. Do not fetch arbitrary remote images without explicit user intent and safety checks.

## 9. Authentication, configuration, and secrets

### 9.1 Configuration sources

Precedence (recommended): explicit CLI args/runtime config > environment variables > config file (if supported) > defaults. Never persist secrets in logs or generated artifacts.

| Setting | Example | Purpose | Default |
|---|---|---|---|
| `MEDIUM_TOKEN` | (secret) | Official API integration token (legacy) | unset (export/feed modes only) |
| `MEDIUM_API_BASE_URL` | `https://api.medium.com/v1` | Override for testing/compat | official base |
| `MCP_TRANSPORT` | `stdio` \| `streamable-http` | Runtime transport selection | `stdio` |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` / `MCP_HTTP_PATH` | `127.0.0.1`, `8000`, `/mcp` | HTTP bind/path config | localhost-safe defaults |
| `MCP_HTTP_AUTH_TOKEN` | (secret) | Shared bearer/token for remote HTTP (if simple auth mode enabled) | unset (local-only/no shared-secret auth) |
| `MEDIUM_ENABLE_UNOFFICIAL` | `false` | Future experimental gate | `false` (and feature absent in MVP) |
| `LOG_LEVEL` | `INFO` | Logging verbosity | `INFO` |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Upstream/fetch timeout | bounded default |

### 9.2 Auth model

- **Local stdio (MVP primary):** token from host-provided env/secret store. Probe lazily or on first official-api call; report redacted status in capabilities.
- **Remote Streamable HTTP:** server endpoint must be protectable (TLS via deployment/proxy, authn/authz middleware/config as supported). Do not design MVP as open multi-tenant; document secure deployment patterns.
- **OAuth:** not assumed available; only a future/conditional adapter if Medium app registration and flows are viable.

### 9.3 Secret handling

- Read secrets from env/secret stores; redact in logs/errors/results (`***redacted***`).
- Do not accept secrets via untrusted prompt content as a persistence mechanism.
- Support "export/feed-only" operation with no secrets configured.

## 10. Transports, runtime, and CLI

### 10.1 stdio (P0)

- Protocol messages on stdout only; **all logs to stderr** (or file when configured).
- Launchable via console script/module (`python -m medium_mcp_server`, `medium-mcp-server`, and/or `uvx`-friendly invocation once packaged).
- Graceful shutdown on EOF/termination; cleanup caches/handles.

### 10.2 Streamable HTTP (P1, required capability for remote compatibility)

- SDK-supported Streamable HTTP endpoint (ASGI integration as appropriate).
- Local-dev bind defaults to localhost; production behind TLS/reverse proxy.
- Implement/enable deployment controls as applicable: authentication, origin/DNS-rebinding protections, rate limiting hooks, health endpoint (non-MCP or operational), request size/time limits.
- Stateless request handling where practical; session/state handling must follow SDK/spec behavior.

### 10.3 CLI surface (proposed)

- `serve` / default: run server (`--transport stdio|streamable-http`, host/port/path options).
- `--help`, `--version`.
- Optional quality-of-life: `capabilities` or `doctor` (prints effective modes and config diagnostics, redacted) — useful for host setup/debugging.

## 11. Error handling, logging, and observability

### 11.1 Error taxonomy

| Category | Examples | Behavior |
|---|---|---|
| `validation_error` | missing/invalid fields, bad URL/tag/license/format | no side effect; actionable fix hints |
| `unsupported_capability` | publish without official API, edit/delete request | no side effect; include alternatives (export/prepare/feed) |
| `confirmation_required` | `publish_post` without `confirm=true` | no side effect; require explicit confirmation |
| `auth_error` | missing/invalid/revoked token | no side effect; redacted details; capability downgrade guidance |
| `not_found` / `unavailable` | unknown publication/resource/feed/source | no side effect; clear message |
| `upstream_error` | Medium API/feed non-2xx, parse failure | bounded retries only for safe reads; sanitized details |
| `rate_limited` / `timeout` | 429, network timeout | backoff guidance; no blind create retry |
| `internal_error` | unexpected exception | sanitized message + correlation id; detailed logs server-side |

### 11.2 Logging & diagnostics

- Structured logs (key/value or JSON-capable) with correlation/request/tool identifiers and timing.
- Redaction filter for tokens, auth headers, cookies, and sensitive payloads.
- Audit-style records for mutating operations: action, mode, target (redacted/minimal), idempotency key/hash, outcome, timestamp.
- Bounded payload/result sizes to protect hosts/clients.

## 12. Security, privacy, and compliance

- **Draft-first default** and explicit confirmation for public/unlisted publish.
- **Prompt-injection resilience:** treat post/feed content and external text as data; never execute instructions embedded in content; require validated tool intent for side effects.
- **Remote hardening:** TLS in production, authentication/authorization, origin checks/DNS-rebinding protections per spec guidance, rate limiting, and minimal exposed surface.
- **Filesystem safety:** `export_post_bundle` path writes (if enabled) must be constrained to allowed workspace/configured output roots; reject path traversal.
- **Supply chain:** pin SDK/dependencies, minimal dependency set, audit before release.
- **ToS posture:** default modes limited to official API (when available), public feeds, and local export/prep. No unofficial automation in MVP; any future experimental adapter requires explicit opt-in and documented risks.

## 13. Reliability and idempotency

- **Timeouts:** bounded for all upstream/feed operations.
- **Retries:** only safe/idempotent reads (e.g. feed/profile/publications) with backoff/jitter; **never blind-retry create/upload/publish**.
- **Dedupe support:** accept `idempotency_key`; compute normalized content hash fallback when appropriate; keep a short-lived in-memory (and optional pluggable) dedupe cache of recent successful create operations to reduce duplicates on ambiguous failures/retries.
- **Graceful degradation:** if one adapter/mode fails, others (especially export/prepare) remain available; capabilities reflect current state.

## 14. Proposed project structure & tech stack

```text
medium-mcp-server/
  pyproject.toml
  README.md
  src/
    medium_mcp_server/
      __init__.py
      __main__.py              # CLI entrypoint (stdio / streamable-http)
      server.py                # MCP server assembly (tools/resources/prompts registration)
      config.py                # settings/env parsing (redacted diagnostics)
      capabilities.py          # mode detection and capability reporting
      errors.py                # domain -> MCP/tool error mapping
      logging.py               # structured logging/redaction setup
      domain/
        models.py              # Profile/Publication/Post/FeedItem/PreparedPost/etc.
        validation.py          # schema + business-rule validation
        transforms.py          # markdown/html normalization & rendering helpers
      adapters/
        export.py              # prepare/render/export bundle (always-on)
        feeds.py               # RSS/Atom public feed reader
        medium_official.py     # official API client/adapter (capability-gated)
        # unofficial_*.py       # future experimental, opt-in only (not MVP)
  tests/
    unit/
    integration/
    contract/
  docs/
    spec.md                    # this document
    ...
```

**Stack:** Python (target 3.10+, confirm SDK minimum), official `mcp` SDK, type hints + validation models (Pydantic or dataclasses as chosen), HTTP client for feeds/API with explicit timeouts, minimal parsing deps for feeds/HTML/Markdown as needed. Distribution via `pyproject.toml` console script and PyPI-ready package; optional container for HTTP deployment.

## 15. Testing and validation strategy

| Layer | Scope | Examples / gates |
|---|---|---|
| **Unit** | Pure logic | content normalization/validation, tag/license/URL rules, capability gating, error/redaction mapping, dedupe/cache behavior |
| **Integration** | Adapters with mocks/fixtures | official API success/failure/auth/429/timeout, feed parsing variants and limits, export bundle generation, filesystem safety |
| **Contract** | MCP surface stability | `tools/list` and schema snapshots, resource URI availability/shape, prompt definitions, deterministic prepare/export outputs |
| **Transport/E2E** | Real MCP sessions | stdio session via Inspector/SDK harness; Streamable HTTP request/stream behavior; config/CLI smoke tests |
| **Security/negative** | Abuse and leakage prevention | secret redaction, publish-confirm enforcement, path traversal rejection, origin/auth checks (HTTP), oversized input/output bounds |

**Tooling:** MCP Inspector for interactive validation of both transports; automated CI for unit/integration/contract tests. Maintain golden fixtures for prepare/export and representative feed payloads.

## 16. Documentation & compatibility deliverables

- `README.md`: install, quickstart, stdio config, capability model, safety notes.
- `docs/spec.md`: canonical product/technical spec (this file).
- Client setup guides (incremental): Claude Desktop/Code, Cursor/VS Code/Windsurf, terminal/Inspector, remote Streamable HTTP, and per-client notes for ChatGPT/Gemini/other web connectors as verified.
- **Compatibility matrix:** tested host/client, version/date, transport, auth mode, verified tools/resources/prompts, known limitations.
- `CHANGELOG.md`: spec and implementation changes by release.

## 17. Implementation phases (roadmap)

| Phase | Scope | Exit criteria |
|---|---|---|
| **Phase 0 — Scaffold** | Package skeleton, config/logging, CLI, stdio + Streamable HTTP server shells, `get_capabilities`, MCP Inspector smoke tests | Server runs in both transports; capability resource/tool responds; no stdout logging in stdio |
| **Phase 1 — Always-useful core** | `prepare_post`, `render_medium_content`, `export_post_bundle`, `medium://templates/post`, validation/transforms, unit+contract tests | Deterministic prep/export without credentials; golden tests pass |
| **Phase 2 — Public read** | `read_public_feed` adapter, normalization/limits/warnings, tests/fixtures | Bounded, best-effort public feed reads with clear warnings |
| **Phase 3 — Official API (gated)** | Token config/probe, `get_profile`, `list_publications`, `create_draft`, optional `upload_image`, `publish_post` with confirmation, dedupe safeguards | Safe draft workflow when valid token available; publish hard-gated on confirm; failures degrade to export guidance |
| **Phase 4 — Hardening & release** | HTTP auth/deployment guidance, security tests, docs/config matrix, packaging (PyPI/container), versioned compatibility notes | Release-ready MVP with documented verified clients and security checklist |

**Future (explicitly out of MVP):** verified OAuth flow (if feasible), richer feed/source helpers, optional experimental unofficial adapter behind strong opt-in/warnings, hosted multi-tenant controls.

## 18. Risks, assumptions, and open questions

| Item | Type | Notes / mitigation |
|---|---|---|
| Medium token issuance/official API availability for new users | Risk/uncertainty | Core value must not depend on it; export/feed modes always available; capability probe and clear messaging |
| No official post list/read/edit/delete | Platform constraint | Do not promise; provide feed/export workflows and "manual step required" guidance |
| Web-client MCP connector variability (ChatGPT/Claude/Gemini) | Evolving | Streamable HTTP + portable surface; maintain verified compatibility matrix; avoid overclaiming |
| Duplicate creates on retries/timeouts | Risk | Dedupe keys/cache, no blind create retries, draft-first |
| Feed format/availability changes | Risk | Best-effort parsing, fixtures, warnings, strict limits |
| Legal/ToS concerns for unofficial methods | Risk | Exclude from MVP; opt-in+isolated if ever considered |
| SDK/API churn (MCP spec, Python SDK, host configs) | Risk | Pin versions, contract tests, re-verify before release |

**Open questions to resolve during implementation:**
1. Final Python minimum version and `mcp` SDK version pin (confirm at scaffold time).
2. Export write behavior default (`inline` only vs workspace path writes) and exact path safety policy.
3. Whether to include a `doctor` CLI command in MVP for host troubleshooting.
4. Level of Markdown/HTML fidelity guarantees and supported conversion library choices.
5. Exact Streamable HTTP auth mechanism(s) supported out-of-the-box for self-hosted deployments.

## 19. Acceptance criteria for "spec complete" (this milestone)

- [x] Spec reflects all provided docs: platform constraints, MCP/Python/transport guidance, adjacent-server lessons, and capability-gated architecture.
- [x] Defines capability modes, MVP/prioritized tool-resource-prompt surface, safety model, transports, config/auth, errors, testing, and phased roadmap.
- [x] Explicitly documents non-goals and known uncertainties (Medium API availability, client-specific web support, unofficial automation risks).

---
*This specification is the source of truth for initial implementation planning. Keep it updated as capabilities are verified or changed.*
