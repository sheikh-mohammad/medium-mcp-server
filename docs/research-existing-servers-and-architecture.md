# Existing MCP Servers/Integrations and Recommended Architecture (Medium, 2026)

*Research date: 2026-11-19. Scope: survey of Medium-related and adjacent blogging/CMS MCP servers, plus recommended architecture for a **Python** Medium MCP server connectable to coding agents, terminals, desktop apps, and web-based AIs (ChatGPT, Claude, Gemini, etc.).*

## Executive summary

- **Dedicated Medium MCP servers:** no clearly maintained, widely adopted, official or community Medium MCP server was identified from available research in this session. This is primarily due to Medium’s constrained/legacy official API surface and the fragility/ToS risk of unofficial automation approaches.
- **Adjacent ecosystem provides strong patterns:** WordPress, Ghost, Dev.to/Forem, Hashnode, Blogger, and headless CMS integrations demonstrate reusable MCP design patterns: explicit capability discovery, draft-first workflows, idempotent/safe mutations, clear auth scoping, and dual-transport support (stdio for local hosts, Streamable HTTP for remote/web clients).
- **Recommended product/technical strategy:** build a **capability-gated, draft-first, export-safe** Python MCP server. Treat official Medium API access as optional/legacy-limited, use RSS/feeds for public read-only ingestion where useful, and always provide local content preparation/export so the server remains valuable even without write-capable Medium credentials.
- **MVP:** prioritize `capabilities`, profile/publication discovery (when available), content preparation/render/export, and safe draft creation (feature-gated). Defer edit/delete/list-posts/publication-management parity claims because they are not reliably supported by official Medium interfaces.

> **Evidence note:** Live external retrieval in this run was limited. This document combines (a) canonical MCP/platform sources, (b) findings from a prior research survey in this session, and (c) established integration patterns. Maintenance signals for third-party repos/packages (stars, issues, last commit/release) should be verified at implementation time.

## 1) Survey: existing servers and integrations

### 1.1 Medium-related MCP servers/integrations

| Item | Evidence/status | Stack / transport / auth (expected if present) | Capabilities (typical/possible) | Strengths | Gaps / risks | Lessons |
|---|---|---|---|---|---|---|
| **Official Medium MCP server** | **None identified** | N/A | N/A | N/A | Medium has no official MCP product surface identified | Do not depend on vendor-provided Medium MCP support |
| **Clearly maintained dedicated community Medium MCP server** | **None clearly identified / likely sparse or niche** | Often Node/Python if found; commonly stdio-only; token/session-based | Usually limited to draft/publish experiments; rarely full CRUD | May prove feasibility for narrow flows | Unofficial endpoints/browser automation breakage, auth/session fragility, ToS/account risk, poor maintenance continuity | Treat as references only; prefer first-party/stable interfaces and explicit fallback modes |
| **Non-MCP Medium automation scripts/libraries** | **Exist in ecosystem (varied quality)** | Python/JS scripts, API wrappers, Playwright/Selenium automation | Draft/publish/import helpers, feed readers, content transforms | Useful building blocks (parsers, converters) | Not MCP-compatible, uneven maintenance, compliance/security concerns | Reuse content-transform ideas, but isolate risky adapters behind opt-in flags |

### 1.2 Adjacent blogging/CMS MCP/reference integrations (patterns to reuse)

| Platform / example | Reference(s) | Typical stack | Transport patterns | Auth patterns | Common MCP capabilities | Strengths | Gaps / limitations | Design lessons for this project |
|---|---|---|---|---|---|---|---|---|
| **WordPress** (e.g. Automattic ecosystem / WordPress MCP integrations) | [Automattic/wordpress-mcp](https://github.com/Automattic/wordpress-mcp), [WordPress REST API](https://developer.wordpress.org/rest-api/) | TypeScript/Node common (adapters/connectors vary) | stdio for local; remote/HTTP-hosted connectors in some environments | OAuth/app passwords/site tokens depending on deployment | List/read/create/update posts/pages, drafts, taxonomies/metadata, some media/site operations (varies) | Mature content model; clear draft/publish semantics; local+hosted patterns | Capability differences by hosting mode/permissions; media flows can be complex | Separate transport/auth from domain operations; expose explicit state transitions; report environment-specific capabilities |
| **Ghost** (community MCP servers over Admin/Content APIs) | [Ghost Developer Docs](https://ghost.org/docs/) | Commonly Node.js/TypeScript; Python possible | Mostly stdio; some HTTP wrappers/proxies | Content API key (read), Admin API key/JWT (write/admin) | List/get/create/update posts/pages/tags/authors, drafts/publish/schedule, image upload (implementation-dependent) | Clean API boundaries and Markdown-friendly workflows | Fragmented community implementations; uneven feature coverage and maintenance | Split read-only vs privileged modes; support idempotent upserts by slug/id; normalize content formats |
| **Dev.to / Forem** (community wrappers) | [Forem API docs](https://developers.forem.com/api) | Node.js/TS or Python | Typically stdio | API key header | List/get/create draft/publish/update articles, tags/series/profile/org (API-dependent) | Simple auth and useful MVP surface for developer blogging | Limited CMS/media richness; rate limits and permission variance | Good template for minimal, high-value tool set (`capabilities`, `list/get`, `create_draft`, `publish`, `update`) |
| **Hashnode** (community GraphQL-based integrations) | [Hashnode API docs](https://apidocs.hashnode.com/) | Often Node.js/TS; Python feasible | Typically stdio | Personal/API token | Query posts/publications, create draft/publish/update, tags/cover metadata (varies) | Precise GraphQL field selection; publication-aware workflows | GraphQL/schema and pagination complexity; maintenance variance | Use typed operation wrappers, cursor pagination tools, and normalized errors |
| **Blogger** (community servers over Google Blogger API) | [Blogger API](https://developers.google.com/blogger) | Node.js/Python possible | Typically stdio | Google OAuth 2.0 (user consent), token refresh/storage required | List blogs/posts, get/insert/update/delete posts/labels (media often indirect) | Demonstrates robust OAuth consent flows | OAuth setup complexity; token lifecycle/security burden | Abstract auth/token storage; keep auth bootstrap separate from runtime tool execution |
| **Headless CMS** (Contentful/Sanity/Strapi, etc.) | [Contentful docs](https://www.contentful.com/developers/docs/), [Sanity docs](https://www.sanity.io/docs), [Strapi docs](https://docs.strapi.io/) | Mixed (TS/Node common) | stdio common; hosted/remote connectors exist in some ecosystems | Scoped API tokens/PATs/OAuth, environment/project scoping | Schema/content discovery, query/search, draft/publish, assets/media, localization (varies) | Strong resource-discovery and environment-scoping patterns | More abstract than single-blog workflows | Expose schema/capabilities as resources; return structured metadata for agent planning |

### 1.3 Cross-platform takeaways

- **Most reliable baseline:** local **stdio** MCP servers with a small, well-typed tool surface and draft-first behavior.
- **Remote reach:** **Streamable HTTP** is important for shared/web-hosted clients, but requires real auth/security/ops work.
- **Capability honesty matters:** servers should expose what is actually supported in the current auth/backend/environment instead of implying full CMS parity.
- **Content portability is high value:** preparation, validation, and export workflows remain useful even when publish APIs are unavailable.

## 2) Medium platform constraints (design-driving facts)

| Area | Implication for architecture |
|---|---|
| Official API is legacy/limited and availability for new tokens/apps is uncertain | Treat official write access as **optional, capability-gated**; never make it a hard dependency for core value |
| Official write surface is mostly "create post/draft" (+ image/upload/profile/publications in documented API) | Design around **draft creation**, not full post lifecycle management |
| No documented official endpoints for list/read-back/edit/delete posts or full publication management | Do not promise these in default mode; provide feed-read and export/manual fallback |
| Unofficial/browser/internal automation can increase apparent capability | Keep such approaches **out of MVP**, opt-in only, isolated behind adapters with strong warnings |
| Content fidelity/duplicate-create/idempotency concerns | Add validation, preview/export, confirmation for publish, and client-provided idempotency/dedupe keys where possible |

(See [Medium platform research](./research-medium-platform.md) for detailed evidence and confidence labels.)

## 3) Recommended architecture for this project

### 3.1 Goals and non-goals

**Goals**
- Python MCP server usable from local coding agents/terminals/desktop hosts and remotely where Streamable HTTP clients/connectors are supported.
- Reliable, safe assistance for Medium workflows despite platform API limitations.
- Clear capability discovery and predictable, typed tool behavior.

**Non-goals (MVP)**
- Guaranteed full Medium parity (list/read/edit/delete all posts, publication admin, analytics/comments).
- Unofficial scraping/browser automation by default.
- Multi-tenant SaaS-grade auth/hosting in the first iteration (can be a later phase).

### 3.2 Capability modes (core architectural decision)

| Mode | Availability | Auth required | Primary capabilities | Notes |
|---|---|---|---|---|
| **Export / prepare (always-on)** | Default | No | Normalize input, generate Medium-ready Markdown/HTML, canonical/tag/license checks, export bundle/manifests | Ensures value even with zero Medium access |
| **Feed read (public)** | Optional/auto-detect | No (public feeds) | Discover/read public posts via RSS/Atom (and cautiously any JSON feed variants if explicitly supported) | Public-only, format/availability may vary; label partial/uncertain |
| **Official API (legacy-limited)** | Optional, capability-gated | Yes (`MEDIUM_TOKEN` or equivalent, if valid) | `whoami`/profile, list contributor publications, create draft/post, upload image (as supported) | Draft-first default; no edit/delete/list-post guarantees |
| **Unofficial automation (future/experimental)** | Off by default | User-provided session/automation context | Potential UI-parity operations | High ToS/security/maintenance risk; require explicit opt-in and strong warnings |

Expose active mode(s) and supported operations via a `capabilities` tool/resource so clients and models can plan correctly.

### 3.3 Proposed MCP surface (MVP-oriented)

#### Tools (suggested)
| Tool | Category | Purpose | Key inputs (illustrative) | Notes |
|---|---|---|---|---|
| `get_capabilities` | discovery | Report enabled backends/modes and supported operations | none | Always available; first-call friendly |
| `get_profile` | official-api | Fetch authenticated user/profile | none/token context | Requires valid official credentials |
| `list_publications` | official-api | List publications user can contribute to | none/user context | Official API scope only |
| `prepare_post` | export | Normalize/validate content and metadata | title, markdown/html, tags, canonicalUrl, license, publish intent | Pure/local, deterministic |
| `render_medium_content` | export | Produce Medium-compatible payload/HTML and warnings | prepared post/content format | No side effects |
| `export_post_bundle` | export | Write/return export artifacts (content + metadata + asset refs) | prepared post, output options | Fallback/manual publish path |
| `create_draft` | official-api | Create a draft (user or publication) | title, contentFormat/content, tags, canonicalUrl, license, publicationId?, idempotencyKey? | Default safe write; dedupe guidance needed |
| `publish_post` | official-api | Create/publish publicly or unlisted | same as draft + explicit `confirm=true` | Require explicit confirmation; high-impact action |
| `upload_image` | official-api | Upload supported image and return URL/metadata | file/path/bytes + mime | Validate size/type; optional for MVP |
| `read_public_feed` | feed-read | Read public posts from user/publication/tag feed | feed URL/handle, limit | Public-only, best-effort parsing |

#### Resources (suggested)
| URI | Purpose |
|---|---|
| `medium://capabilities` | Current modes, auth status (redacted), supported ops/warnings |
| `medium://profile` | Authenticated profile snapshot (when available) |
| `medium://publications` | Contributor publications (when available) |
| `medium://templates/post` | Example/front-matter templates for agents |
| `medium://exports/latest` (or local index) | Recently prepared/exported artifacts (if persisted) |

#### Prompts (optional, high UX value)
- "Draft a Medium post from repository notes/README/changelog"
- "Cross-post checklist" (canonical URL, tags, license, image rights, formatting)
- "Preflight before publish" (capability/auth checks, preview, confirmation)

### 3.4 Python stack and project structure

| Choice | Recommendation | Rationale |
|---|---|---|
| Language/runtime | Python 3.10+ (verify SDK minimum) | Modern typing, ecosystem fit, easy packaging for CLI/server use |
| MCP SDK | Official `mcp` Python SDK | Spec alignment, transports/types, maintained baseline |
| Server style | High-level FastMCP-style API (if available in chosen SDK version) over modular domain/adapters | Fast tool/resource/prompt authoring with clean separation |
| Validation/models | Type hints + Pydantic/dataclasses (as appropriate) | Explicit schemas, safer inputs/outputs, easier testing |
| HTTP serving (remote mode) | SDK-supported Streamable HTTP integration (ASGI stack as applicable) | Standard remote deployment path |
| Packaging | `pyproject.toml`, console entrypoint, PyPI-ready; optional container for HTTP | Works with `pip`/`pipx`/`uvx` and hosted deployments |
| Config | Env vars + optional config file; no secrets in logs | Simple local stdio and host-managed secret injection |

**Suggested module boundaries:** `server.py` (MCP registration), `domain/` (models/transforms/validation), `adapters/` (official API, feeds, export), `auth/` (token/capability resolution), `errors.py` (sanitized mapping), `__main__.py` (stdio/http CLI).

### 3.5 Transport and connectivity strategy

- **Stdio (must-have):** primary integration path for terminal CLIs, coding agents, IDEs, and local desktop hosts; easiest distribution and secret handling.
- **Streamable HTTP (must-have for "all types" aspiration):** enable remote/shared hosting and compatibility with clients/connectors that consume remote MCP endpoints.
- **Configuration presets:** publish examples for local stdio (`command`, `args`, `env`) and remote HTTP (`url`, auth headers/tokens as required by deployment/client).
- **Client reality:** stdio local compatibility is broadly achievable; arbitrary web-client connectivity (ChatGPT/Claude/Gemini web surfaces) depends on each product's current MCP/connector support. Maintain a verified compatibility matrix over time.

### 3.6 Auth, secrets, and security/ToS considerations

- **Secrets:** load from env/host secret stores; never echo tokens/cookies in tool outputs or logs.
- **Least privilege:** separate read/prepare/export tools from mutating/publish tools.
- **Human confirmation:** require explicit `confirm=true` (or equivalent) for public publish actions; default to drafts.
- **Prompt-injection awareness:** treat post content/feeds as untrusted input; do not let embedded instructions trigger unsafe actions without validation/confirmation.
- **Remote HTTP controls:** TLS, authentication/authorization, Origin/DNS-rebinding protections per spec/deployment, rate limiting, audit logging (redacted).
- **ToS/compliance:** official API/feed/export modes by default; no browser automation/internal endpoint usage unless explicitly enabled by user with documented risk.

### 3.7 Reliability, idempotency, and content handling

- **Idempotency/deduplication:** accept client-provided idempotency keys/source hashes for create operations and cache recent create fingerprints (where feasible) to reduce duplicate drafts on retries/timeouts.
- **Timeouts/retries:** bounded timeouts; retry only safe/idempotent reads with backoff; avoid blind retries on create/publish.
- **Content conversion:** canonicalize Markdown/HTML, validate tags/counts/URLs/licenses, warn on unsupported embeds/format loss.
- **Response design:** return structured results (IDs, URLs, mode, warnings, next actions) and keep payloads bounded.

### 3.8 MVP sequencing (recommended)

| Phase | Scope | Outcome |
|---|---|---|
| **MVP-0: Scaffold & core** | Python package, config/logging, stdio + Streamable HTTP server skeleton, MCP Inspector smoke tests | Runnable server with transport parity and observability basics |
| **MVP-1: Always-useful local modes** | `get_capabilities`, `prepare_post`, `render_medium_content`, `export_post_bundle`, templates/resources | Value without Medium credentials; deterministic tests |
| **MVP-2: Public read mode** | `read_public_feed` adapter + parsing/normalization + limits | Public content discovery/ingestion for research and republishing workflows |
| **MVP-3: Official API write mode (feature-gated)** | token auth, `get_profile`, `list_publications`, `create_draft`, optional `upload_image`, explicit `publish_post` with confirmation | Safe draft/publish assistance when legacy token access is available |
| **MVP-4: Hardening & distribution** | contract/integration/security tests, docs/config examples per client, packaging (PyPI/container), compatibility matrix | Release-ready, maintainable baseline |
| **Future (opt-in/experimental)** | browser-assisted or unofficial adapters | Only with explicit user opt-in, isolation, and strong risk labeling |

## 4) Testing and validation plan (architecture-level)

- **MCP Inspector:** validate discovery/invocation UX for stdio and Streamable HTTP.
- **Unit tests:** transforms, validators, capability gating, error/redaction mapping.
- **Integration tests:** mocked official API and feed adapters, auth failures, timeouts, retries.
- **Contract tests:** stable `tools/list` schemas and resource URIs; golden outputs for prepare/export flows.
- **Security tests:** secret redaction, confirmation enforcement on publish, input/path/URL validation, Origin/auth checks for HTTP mode.

## Sources

### MCP protocol, SDKs, and tooling
- [Model Context Protocol — Official site](https://modelcontextprotocol.io/)
- [MCP Specification (latest)](https://modelcontextprotocol.io/specification/latest)
- [MCP Specification 2025-11-25](https://spec.modelcontextprotocol.io/specification/2025-11-25/)
- [MCP Transports (2025-11-25)](https://spec.modelcontextprotocol.io/specification/2025-11-25/basic/transports/)
- [MCP Build a server guide](https://modelcontextprotocol.io/docs/develop/build-server)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [MCP servers/examples repository](https://github.com/modelcontextprotocol/servers)

### Medium platform references
- [Medium API documentation (official repo, archived)](https://github.com/Medium/medium-api-docs)
- [Medium Help Center: Using RSS feeds](https://help.medium.com/hc/en-us/articles/214874118-Using-RSS-feeds-of-profiles-publications-and-topics)
- [Medium Help Center: Import a story](https://help.medium.com/hc/en-us/articles/214550207-Import-a-story-to-Medium)
- [Medium Terms of Service](https://policy.medium.com/medium-terms-of-service-9db0094a1e0f)

### Adjacent platform/ecosystem references
- [Automattic/wordpress-mcp](https://github.com/Automattic/wordpress-mcp)
- [WordPress REST API Handbook](https://developer.wordpress.org/rest-api/)
- [Ghost Developer Documentation](https://ghost.org/docs/)
- [Forem API Documentation (Dev.to)](https://developers.forem.com/api)
- [Hashnode API Documentation](https://apidocs.hashnode.com/)
- [Blogger API (Google Developers)](https://developers.google.com/blogger)
- [Contentful Developer Documentation](https://www.contentful.com/developers/docs/)
- [Sanity Documentation](https://www.sanity.io/docs)
- [Strapi Documentation](https://docs.strapi.io/)
- [Awesome MCP Servers (community index)](https://github.com/punkpeye/awesome-mcp-servers)

*Maintenance/status note: for third-party servers/packages listed as patterns, verify current repository/package activity, releases, and issue health before adopting implementation ideas or dependencies.*
