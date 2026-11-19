# Medium MCP Server — MVP Design & Implementation Plan (Phases 0–4)

**Source of truth:** [`docs/spec.md`](D:\main\projects\medium-mcp-server\docs\spec.md) (Draft v0.1). Any change affecting MCP surface, safety model, or capability claims must update the spec.

**Repo baseline (2026-11-19):** spec/docs-only repository (`docs/`, README, CHANGELOG, LICENSE, community/meta files, `.github` issue/PR templates). **No** `pyproject.toml`, `src/`, Python files, tests, CI workflows, Dockerfile, or entrypoints exist yet — implementation starts from scaffold.

## 1. Scope & confirmed decisions

### In scope (MVP)
- **Phases 0–4** per spec §17: scaffold + transports + capabilities, always-useful export/prepare core, public feed read, gated official Medium API (draft-first), hardening/release readiness.
- **Transports:** `stdio` (P0, release gate) and `Streamable HTTP` (P1, protocol-compliance gate for remote mode) with shared domain logic (§4, §10).
- **Capability-gated modes:** `export`/`prepare` (always on), `feed_read` (public/best-effort), `official_api` (opt-in by valid token/probe). `unofficial_automation` **absent in MVP** (§6).

### Confirmed product decisions (this plan)
| Decision | Choice | Implication |
|---|---|---|
| Plan scope | MVP phases 0–4 | No unofficial adapter, no OAuth onboarding flow, no multi-tenant SaaS/control plane, no webhooks/sync (§3.2, §17 future) |
| `export_post_bundle` writes | **Inline-only by default (MVP)** | Return `bundle`/`manifest` inline only; **no local path writes** in MVP. Do not implement `output=path` / `written_paths`; if `path`/`output=path` is supplied, return `validation_error`/`unsupported_capability` with guidance to use inline output. Filesystem-write/path-traversal policy deferred to post-MVP hardening (§12, §18.4 Q2). |
| Streamable HTTP auth | **Localhost + deploy hooks** | Bind localhost-safe defaults; document TLS/reverse-proxy/auth/origin/DNS-rebinding/rate-limiting deployment patterns. **No built-in auth middleware/shared bearer enforcement in MVP** (`MCP_HTTP_AUTH_TOKEN` not implemented as server auth in MVP). Do not design as open multi-tenant (§9.2, §10.2, §12). |
| CLI diagnostics | **Include `doctor` in MVP** | Add `doctor` CLI command (and keep `get_capabilities` tool/resource) to print redacted effective config, modes, transport readiness, and actionable setup issues for host troubleshooting (§10.3, §18.4 Q3). |

### Opinionated resolutions for remaining open questions (§18.4)
1. **Python / SDK pin (Phase 0):** target `requires-python = ">=3.10"`; pin official `mcp` SDK to a specific verified version/range at scaffold (record exact pin after API/transport verification), prefer FastMCP-style ergonomics where available in chosen version, fall back to low-level primitives only if required. Re-verify on release (§2.2, §14).
2. **Markdown/HTML fidelity:** deterministic, conservative normalization/transforms with explicit warnings for unsupported embeds/custom HTML/lossy conversion; do not silently drop meaningful content (§8.2). Use minimal deps; define supported subset and golden fixtures in Phase 1 (candidate libs decided at implementation: e.g. Pydantic v2 for validation/models, `httpx` for HTTP, `feedparser` for RSS/Atom — keep conversion logic small and test-locked).
3. **HTTP auth mechanism:** out-of-box = localhost bind + deployment hooks/docs only (per decision above).

## 2. Architecture & design principles (apply throughout)

- **Capability-gated, fail closed:** compute/report capabilities from config + auth probe + adapter health (`get_capabilities`, `medium://capabilities`, redacted). Unsupported ops return structured `unsupported_capability` with alternatives (export/prepare/feed) — never imply parity (§5.1, §6, §7.1.1).
- **Draft-first, explicit confirmation:** create draft by default; `publish_post` requires `confirm=true` and `official_api` capability or fails `confirmation_required` with no side effect (§5.2, §7.1.4, §12).
- **No blind create retries / dedupe:** retries only for safe/idempotent reads with backoff+jitter and bounded timeouts. Accept `idempotency_key` and/or normalized content hash; short-lived in-memory dedupe cache for recent successful creates/uploads where feasible; always warn Medium has no native idempotency (§7.1.4, §13).
- **Transport-agnostic core:** shared domain/validation/adapters; stdio and Streamable HTTP are thin runtime shells with identical tool/resource/prompt behavior (§5.3, §10).
- **Adapter isolation:** `export` (always-on), `feeds`, `medium_official` behind interfaces; `unofficial_*` not created/enabled in MVP (§5.4, §14).
- **Secret & logging safety:** no tokens/cookies/auth headers/secrets in logs/errors/results (`***redacted***`); audit-style records for mutating ops (action, mode, minimal target, idempotency key/hash, outcome, timestamp). **stdio: stdout protocol-only, all logs to stderr/file** (§9.3, §10.1, §11.2).
- **Prompt-injection resilience & input trust:** treat post/feed/external content as data; never execute embedded instructions; require validated intent/confirmation for side effects (§5.8, §12).
- **Deterministic, bounded outputs:** typed JSON-serializable results, `mode`/`warnings`/`next_actions` where relevant, limits/truncation/timeouts/size bounds (§5.7, §7, §11.2).

## 3. Target project structure & critical files

Create (incrementally by phase) the spec-aligned layout (§14):

```text
pyproject.toml                         # packaging, deps, console scripts, tool config
README.md                              # update: install/quickstart/config/safety (Phase 4)
CHANGELOG.md                           # update per release/milestones
docs/
  spec.md                              # keep canonical; update if surface/safety/capabilities change
  compatibility-matrix.md              # new in Phase 4 (verified/unverified hosts)
src/medium_mcp_server/
  __init__.py                          # version/export
  __main__.py                          # CLI: serve/default, doctor, --help/--version
  server.py                            # MCP server assembly: register tools/resources/prompts
  config.py                            # settings/env/CLI parsing, precedence, redacted diagnostics
  capabilities.py                      # mode detection, auth/capability probes, capability report/cache
  errors.py                            # domain -> MCP/tool error taxonomy mapping (sanitized)
  logging.py                           # structured logging + redaction; stderr/file routing for stdio
  domain/
    __init__.py
    models.py                          # CapabilityReport, PreparedPost, Profile, Publication, FeedItem, OperationResult, etc.
    validation.py                      # schema/business-rule validation (tags/urls/license/required/size)
    transforms.py                      # markdown/html normalization & Medium-compatible rendering helpers
  adapters/
    __init__.py
    export.py                          # prepare/render/export bundle (always-on, inline-only MVP)
    feeds.py                           # public RSS/Atom reader (best-effort, bounded)
    medium_official.py                 # official API client/adapter (capability-gated; draft-first)
tests/
  unit/                                # validation, transforms, capabilities, errors/redaction, dedupe
  integration/                         # adapter mocks/fixtures, feed parsing, export, API error paths
  contract/                            # tools/list & schema snapshots, resource/prompt definitions, golden outputs
  e2e/ or transport/                    # stdio & Streamable HTTP session smoke/harness (as practical)
.github/
  workflows/ci.yml                     # add in Phase 0/4: lint/type/unit/integration/contract gates
Dockerfile                             # optional, Phase 4 (HTTP deployment)
```

**Existing files to update over time:** `README.md`, `CHANGELOG.md`, `docs/README.md`, `docs/spec.md` (only if contract changes), and add `docs/compatibility-matrix.md` + per-host setup notes as verified.

## 4. Phased implementation plan

### Phase 0 — Scaffold (foundation, both transports, diagnostics)
**Goal:** runnable MCP server skeleton with honest capability reporting and no protocol/logging violations.

**Tasks**
- Initialize packaging: `pyproject.toml` (src layout, `project.scripts` console entrypoint e.g. `medium-mcp-server`, module run `python -m medium_mcp_server`, metadata, dependencies, optional extras). Set Python/SDK pins (verify at scaffold).
- Implement `config.py`: load/merge CLI args > env > defaults; parse transport/HTTP bind-path/timeouts/log level/Medium token/base URL (redacted diagnostics). No config-file requirement in MVP unless trivial.
- Implement `logging.py`: structured logs, redaction filter (tokens/headers/cookies/sensitive payloads), correlation ids; **stdio mode routes logs to stderr only**; optional file logging config.
- Implement `errors.py` + base `domain/models.py` for `OperationResult`/error payloads covering taxonomy (§11.1).
- Implement `capabilities.py`: resolve modes from config + placeholder/probe hooks; produce `CapabilityReport` (redacted auth state), cache with safe refresh semantics.
- Implement `server.py`: register `get_capabilities` tool and `medium://capabilities` resource; wire prompts registration scaffold (empty or Phase 1) and server assembly reusable by both transports.
- Implement transports/CLI in `__main__.py`: `serve`/default with `--transport stdio|streamable-http` and `--host/--port/--path` (localhost-safe defaults), `--help`, `--version`, and **`doctor`** (prints redacted effective config, detected modes/capabilities, transport settings, common misconfig warnings e.g. token set but probe not run/unavailable). Graceful shutdown/cleanup.
- Add test/quality tooling baseline (pytest, ruff, mypy/pyright as chosen), initial `tests/` layout, and MCP Inspector smoke instructions/scripts.

**Deliverables / critical files:** `pyproject.toml`, `src/medium_mcp_server/{__init__,__main__,server,config,capabilities,errors,logging}.py`, `src/medium_mcp_server/domain/{__init__,models}.py`, minimal `tests/`.

**Exit criteria (§17):** server runs in stdio and Streamable HTTP; capability tool/resource responds accurately for no-auth state; **no stdout logging in stdio**; Inspector smoke test passes for both transports.

### Phase 1 — Always-useful core (no credentials required)
**Goal:** deterministic, validated prepare/render/export workflow — primary product value without Medium access.

**Tasks**
- Flesh out `domain/models.py` with `PreparedPost`, template/checklist-related models as needed; `domain/validation.py` (non-empty title/content, tags max 5 default warn+keep first 5 valid unique, canonical URL validity, license enum, required fields, payload/size bounds).
- Implement `domain/transforms.py`: conservative markdown/html normalization (preserve intent, no silent drops), render Medium-compatible content/payload and emit fidelity/unsupported-construct/lossy-conversion warnings.
- Implement `adapters/export.py`:
  - `prepare_post`: validate + normalize -> `PreparedPost`, `validation`, `medium_ready`, `suggested_next_actions` (recommend draft-first/publish checks where relevant).
  - `render_medium_content`: accept prepared or raw fields, return content/format/title/tags/metadata/warnings.
  - `export_post_bundle`: **inline-only MVP** — return inline `bundle` artifacts + `manifest` (and include_manifest handling); reject path-write requests per decision with actionable error; no filesystem writes.
- Register tools in `server.py`: `prepare_post`, `render_medium_content`, `export_post_bundle`.
- Register resource `medium://templates/post` (canonical template/examples/checklist metadata) and optional in-memory `medium://exports/latest` metadata if low-cost.
- Register prompts (§7.3): `draft_medium_post`, `crosspost_checklist`, `preflight_publish` — workflow guidance only, no hidden side effects, instruct use of prepare/capability/confirm steps.
- Tests: unit (validation/transforms/tag/license/url/normalization), contract snapshots for tools/resources/prompts schemas and deterministic golden prepare/export outputs, integration for export bundle generation.

**Deliverables / critical files:** `domain/{models,validation,transforms}.py`, `adapters/export.py`, `server.py` registrations, `tests/unit|contract` fixtures/goldens.

**Exit criteria (§17):** deterministic prep/export works without credentials; golden tests pass; inline-only export behavior enforced.

### Phase 2 — Public feed read (best-effort, bounded)
**Goal:** safe public-only ingestion/discovery via RSS/Atom without auth.

**Tasks**
- Implement `adapters/feeds.py`: normalize `source`/`source_type` (user/publication/tag/url), fetch with `httpx` (or chosen client) using explicit `REQUEST_TIMEOUT_SECONDS`, max bytes/items, and conservative behavior; parse RSS/Atom (`feedparser` or equivalent) into `FeedItem` list with `fetched_at`, warnings for partial/unsupported/truncated content.
- Register `read_public_feed` tool with bounded `limit` (default e.g. 10) and `include_content` handling; ensure no auth/cookies and no paywalled/private claims.
- Error handling: upstream/parse/timeouts/rate-limit mapped to taxonomy with sanitized details; retries only if safe/idempotent and bounded (reads only).
- Tests: unit normalization/limits; integration with recorded feed fixtures/variants and failure modes (timeout, malformed/partial, oversized).

**Deliverables / critical files:** `adapters/feeds.py`, `server.py`, feed fixtures under `tests/integration` (and/or `tests/fixtures`).

**Exit criteria (§17):** bounded, best-effort public feed reads with clear warnings and limits enforced.

### Phase 3 — Official Medium API (capability-gated, safe writes)
**Goal:** optional draft workflow against legacy official API when a valid token is configured, without overclaiming unsupported operations.

**Tasks**
- Extend `config.py`/`capabilities.py`: `MEDIUM_TOKEN`, `MEDIUM_API_BASE_URL`, auth probe/capability detection (lazy or on first official call), redacted status, cache with safe refresh and invalidation on auth failure.
- Implement `adapters/medium_official.py`: HTTP client wrapper (timeouts, redacted logging), endpoints for profile, contributor publications, create post/draft (user/publication), and optional image upload if supported; validate/sanitize inputs; map 4xx/5xx/429/timeouts to taxonomy.
- Register tools: `get_profile`, `list_publications`, `create_draft`, optional `upload_image` (workspace-safe `image_path` or base64+media type, size/type validation), `publish_post`.
- Enforce safety rules: `official_api` unavailable -> `unsupported_capability` with export/prepare alternatives; `publish_post` requires `confirm=true` else `confirmation_required` (no side effect); default draft intent; prefer/accept prepared/validated input or run equivalent validation; `notify_followers` default false.
- Implement dedupe support: accept `idempotency_key`, compute normalized content hash fallback as appropriate, short-lived in-memory cache of recent successful create/upload results; return prior metadata/warning on cache hit when possible; never blind-retry create/upload/publish.
- Register resources `medium://profile`, `medium://publications` (available only when capability present; clear not-available otherwise).
- Tests: integration with mocked API (success/failure/auth/401/403/404/429/5xx/timeout), unit tests for gating/confirm/dedupe/cache/error-redaction; verify failures degrade with export guidance.

**Deliverables / critical files:** `adapters/medium_official.py`, updates to `config.py`, `capabilities.py`, `server.py`, `domain/models.py`, `tests/unit|integration`.

**Exit criteria (§17):** safe draft workflow with valid token; publish hard-gated on confirm; dedupe safeguards present; unsupported/unavailable states degrade to export/prepare guidance.

### Phase 4 — Hardening & release readiness
**Goal:** production-minded MVP with documented compatibility, security checks, and packaging.

**Tasks**
- **HTTP/deployment guidance:** document localhost defaults, TLS termination/reverse proxy, origin/DNS-rebinding protections, request/size/time limits, rate-limiting hooks/expectations, and secure host configuration patterns (no open multi-tenant). Ensure Streamable HTTP implementation follows SDK/spec behavior and is protocol-compliant.
- **Security/negative tests:** secret redaction (logs/errors/results), publish-confirm enforcement, unsupported-capability behavior, path traversal rejection for any future-facing parsing of disallowed path inputs (and explicit rejection of path writes now), origin/auth-related checks as applicable to chosen HTTP stack, oversized input/output bounds, prompt-injection-resilience expectations (data-only handling).
- **Observability & audit:** verify structured/redacted logging, correlation ids, bounded payloads, and audit records for mutating operations (`create_draft`, `publish_post`, `upload_image`).
- **Packaging & CI:** finalize `pyproject.toml`, console script/`python -m`/`uvx` friendliness, pinned deps/lock guidance, optional `Dockerfile` for HTTP deployment; add `.github/workflows/ci.yml` for unit/integration/contract (and lint/type) gates.
- **Docs & compatibility:** update `README.md` (install, quickstart, stdio/HTTP config, capability model, safety notes), `docs/README.md` index, add `docs/compatibility-matrix.md` and per-host setup notes (Claude Desktop/Code, Cursor/VS Code/Windsurf, Inspector, Streamable HTTP clients) with verified/unverified status per tested client/version; update `CHANGELOG.md`.
- **`doctor` polish:** ensure diagnostics cover common host/setup failures (transport mismatch, missing token/capability downgrade, localhost bind, redacted config summary) without leaking secrets.

**Deliverables / critical files:** `tests/*` security/negative coverage, `.github/workflows/ci.yml`, `Dockerfile` (optional), `README.md`, `docs/compatibility-matrix.md`, `CHANGELOG.md`, finalized CLI/server behavior.

**Exit criteria (§17):** release-ready MVP with security checklist satisfied, documented verified clients/config matrix, Streamable HTTP protocol compliance for remote mode, and stdio interoperability preserved.

## 5. Cross-cutting implementation details (must hold in all phases)

### MCP surface summary (stable, spec §7)
- **Tools:** `get_capabilities` (0), `prepare_post`/`render_medium_content`/`export_post_bundle` (1), `read_public_feed` (2), `get_profile`/`list_publications`/`create_draft`/`upload_image?`/`publish_post` (3). Mutating: `create_draft`, `upload_image`, `publish_post`.
- **Resources:** `medium://capabilities` (0), `medium://templates/post` (1), `medium://exports/latest` (1+ if tracked), `medium://profile`/`medium://publications` (3).
- **Prompts:** `draft_medium_post`, `crosspost_checklist`, `preflight_publish` (register Phase 1; no side effects).

### Config/env (spec §9.1, precedence CLI > env > defaults)
`MEDIUM_TOKEN`, `MEDIUM_API_BASE_URL`, `MCP_TRANSPORT`, `MCP_HTTP_HOST/PORT/PATH`, `LOG_LEVEL`, `REQUEST_TIMEOUT_SECONDS`; `MEDIUM_ENABLE_UNOFFICIAL` remains default `false`/absent in MVP; `MCP_HTTP_AUTH_TOKEN` not enforced in MVP (localhost+deploy-hooks decision).

### Error taxonomy (§11.1)
`validation_error`, `unsupported_capability`, `confirmation_required`, `auth_error`, `not_found`/`unavailable`, `upstream_error`, `rate_limited`/`timeout`, `internal_error` — sanitized, actionable, no side effects on failed/blocked mutations.

### Data/content rules (§8)
Core entities: `CapabilityReport`, `PreparedPost`, `Publication`, `Profile`, `FeedItem`, `OperationResult`. Markdown/HTML inputs; conservative normalization; tags max 5 policy; canonical URL/license validation; bounded payloads; fidelity warnings; no arbitrary remote image fetch without explicit intent.

## 6. Verification plan (execution checklist for implementation)

**Phase 0**
- `pip install -e .` / `uv` equivalent succeeds; `python -m medium_mcp_server --help` and `--version` work; `medium-mcp-server doctor` prints redacted diagnostics/modes.
- Run stdio server and validate with MCP Inspector/SDK harness: `tools/list` includes `get_capabilities`, `resources/list|read` for `medium://capabilities`; confirm **no stdout contamination**.
- Run Streamable HTTP locally (`127.0.0.1`) and validate MCP session/tool/resource access via Inspector/client harness.

**Phase 1**
- `pytest tests/unit tests/contract` pass with golden deterministic outputs for `prepare_post`/`render_medium_content`/`export_post_bundle` (inline-only); invalid inputs -> `validation_error`; path-write attempt rejected per policy.

**Phase 2**
- Integration tests with feed fixtures: bounded results, warnings on partial/parse issues, timeout/upstream handling, public-only behavior.

**Phase 3**
- Mocked official API integration tests: profile/publications/draft/upload (if implemented)/publish flows; `publish_post` without `confirm=true` -> `confirmation_required` no side effect; missing/invalid token -> `auth_error`/capability downgrade + export alternatives; dedupe key/hash prevents duplicate on cached success; no blind create retries.

**Phase 4 / release gates**
- CI green (unit/integration/contract + lint/type); security-negative suite (redaction, confirmation, bounds, traversal-rejection cases, HTTP hardening checks applicable).
- Manual/recorded verification matrix updated for stdio hosts and Streamable HTTP clients (mark unverified where not tested). Package build/install smoke (`pip`, console script, optional container).

## 7. Risks & guardrails (from spec §18)
- **Medium API uncertainty / no list-edit-delete:** never depend on official writes for core value; always provide export/manual fallback and honest capability/limitation messaging.
- **Duplicate creates:** dedupe + draft-first + no blind retries; surface warnings.
- **Feed variability:** best-effort parsing, strict limits/timeouts, fixtures, warnings.
- **Client variability:** portable MCP surface; verified/unverified matrix, no overclaims.
- **ToS/legal (unofficial):** excluded from MVP.
- **SDK churn:** pin/contract-test/re-verify.

## 8. Suggested implementation sequencing notes
- Build **export/prepare/domain/validation** as the pure, testable core first (Phase 1) so all mutating/read adapters can reuse validation and prepared representations.
- Keep **capability reporting** authoritative at every phase (update as adapters/probes are added) so clients never guess.
- Prefer **small, reviewable commits per phase** aligned with exit criteria and update `CHANGELOG.md`/docs incrementally.
- When implementation begins, re-check `docs/spec.md` open questions and record concrete pins/library choices in code/docs (and amend spec if contract-level decisions change).
