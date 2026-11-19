# Medium Platform Integration Research (2026)

*Research date: 2026-11-19. Scope: feasibility and design inputs for a Python MCP server that can connect to coding agents, terminals, desktop apps, and web-based AI clients.*

## Executive summary

- **Official Medium API status (Confirmed):** Medium published an official REST API at `https://api.medium.com/v1` with OAuth 2.0 and integration-token authentication and endpoints for `GET /me`, `GET /users/:id/publications`, `GET /users/:id`, `POST /users/:id/posts`, `POST /publications/:id/posts`, and `POST /images`. Official documentation and the primary GitHub SDK repos are now archived/read-only, and self-serve integration-token generation has been reported by developers as unavailable in normal account settings. Treat the official API as **legacy/limited and operationally uncertain in 2026**, not a dependable foundation for a new full-featured integration.
- **What the official API can/cannot do (Confirmed from official docs/specs, uncertain in practice):** It supports creating posts/drafts, uploading images, fetching the authenticated user, listing contributor publications, and publishing to a publication. It does **not** provide documented endpoints for listing posts, reading post content, editing/updating posts, deleting posts, managing publication membership/settings, analytics, comments, or full draft lifecycle management.
- **Realistic alternatives (Unofficial/community):** RSS/Atom feeds (and Medium's `?format=json` feed variant) are viable for **read-only/public content discovery**. Unofficial libraries and internal/GraphQL or browser-automation approaches exist but carry ToS, breakage, account, and security risks.
- **Recommended approach for this project:** Build an **MCP server with capability modes**: (1) *Official API mode* (if a user already has a valid token) for safe draft creation/image upload/profile/publication discovery; (2) *Read-only feed mode* (RSS/JSON) for public post discovery/content ingestion; (3) *Export/assist mode* (generate Medium-ready Markdown/HTML, canonical/import guidance) as the default safe fallback. Do **not** promise edit/delete/list-all/manage-publications parity with Medium's web UI unless unofficial automation is explicitly opted into and risk-accepted.

> **Evidence note:** This environment exposed `web_search`/`web_fetch` tool schemas but live external retrieval could not be executed successfully during this run. Findings below are therefore evidence-based from widely known official Medium API materials and ecosystem behavior as of recent years, with confidence labels and explicit uncertainty where 2026 runtime verification was not possible. Verify linked sources during implementation.

## 1) Official Medium API (status, auth, capabilities)

### 1.1 Status and availability

| Claim | Confidence | Notes |
|---|---|---|
| Official REST API base URL is `https://api.medium.com/v1` | **Confirmed (official/historical docs)** | Longstanding official endpoint documented by Medium. |
| Official API documentation existed at `https://github.com/Medium/medium-api-docs` | **Confirmed** | Repo is the canonical spec; it has been archived/read-only (no active development). |
| Official OAuth app registration page existed (`https://medium.com/me/applications`) and integration tokens could be generated from settings | **Confirmed (historical) / Uncertain (2026 availability)** | Many developers report the UI/token issuance path is no longer generally available; verify in a live Medium account. |
| API is actively maintained with new endpoints/features | **Uncertain, likely no** | No evidence of recent official expansion; archived docs and community reports indicate stagnation. |
| Existing issued tokens may still work for supported endpoints | **Uncertain** | Depends on Medium's current enforcement; must be validated per account/token. |

### 1.2 Authentication

| Method | Confidence | Details |
|---|---|---|
| **Integration token (Bearer)** | **Confirmed** | Send `Authorization: Bearer <integration_token>` over HTTPS. Simplest for personal/server use; token acts as the user. |
| **OAuth 2.0** | **Confirmed (documented)** | Authorization Code flow with scopes; exchange code for access/refresh tokens. Useful for multi-user apps but requires a registered Medium application/client credentials (availability uncertain in 2026). |
| **Browser session/cookies** | **Unofficial** | Used by scrapers/automation; fragile and higher ToS/security risk. Not recommended for an MCP server default. |

**Auth UX implications:** Prefer user-supplied integration token via env/secret store (`MEDIUM_TOKEN`) for local stdio use. For hosted/remote multi-user scenarios, only offer OAuth if a client can actually be registered and maintained; otherwise document "bring your own legacy token" and provide read-only/export modes that require no Medium auth.

### 1.3 Capabilities and endpoints

#### Confirmed (officially documented) endpoints

| Endpoint | Method | Purpose | Key params / fields | Notes |
|---|---|---|---|---|
| `/me` | GET | Get authenticated user | Returns `id`, `username`, `name`, `url`, `imageUrl` | Entry point to obtain author/user id. |
| `/users/:authorId` | GET | Get user by id | Path: `authorId` | Limited profile info. |
| `/users/:authorId/publications` | GET | List publications user can contribute to | Path: `authorId` | Returns publication ids/names/URLs/roles (as documented). Not full publication management. |
| `/users/:authorId/posts` | POST | Create a post under user | `title`, `contentFormat`, `content`, `tags[]`, `canonicalUrl`, `publishStatus`, `license`, `notifyFollowers` | Core write capability. |
| `/publications/:publicationId/posts` | POST | Create a post in a publication | Same body fields as above + path `publicationId` | Submits/creates per publication rules; may result in draft/pending depending on publication. |
| `/images` | POST | Upload an image | Multipart form-data (`image` file: jpeg/png/gif/tiff; documented size/type limits apply) | Returns image URL/MD5 (as documented) for embedding in post content. |

#### Post creation parameters (Confirmed, documented)

| Parameter | Type | Values / behavior |
|---|---|---|
| `title` | string | Post title (required in practice; used for HTML posts as heading context). |
| `contentFormat` | string | `html` or `markdown` (officially supported). |
| `content` | string | Body in the specified format. |
| `tags` | string[] | Up to 5 tags (documented). Only first few may be applied; validate. |
| `canonicalUrl` | string (URL) | Sets canonical/original source URL. Important for cross-posting. |
| `publishStatus` | string | `public`, `draft`, or `unlisted` (documented). |
| `license` | string | e.g. `all-rights-reserved`, `cc-40-by`, `cc-40-by-sa`, `cc-40-by-nd`, `cc-40-by-nc`, `cc-40-by-nc-nd`, `cc-40-by-nc-sa`, `cc-40-zero`, `public-domain` (as documented). |
| `notifyFollowers` | boolean | Whether followers are notified (relevant for public publishing). |
| `publicationId` | path param | Target publication for publication-post endpoint. |

#### Not available / not documented in official API

| Capability | Confidence | Implication |
|---|---|---|
| List posts/stories (own or publication) | **Confirmed not documented** | Cannot build "list my posts" from official API alone. |
| Read/fetch full post content by id | **Confirmed not documented** | No official read-back of story bodies. |
| Edit/update an existing post | **Confirmed not documented** | No `PUT/PATCH` post endpoints; "create" is effectively append/new-post. |
| Delete/unpublish a post | **Confirmed not documented** | Must be done manually in Medium UI (or unofficial automation, risky). |
| Draft listing/management beyond create-as-draft | **Confirmed not documented** | Cannot enumerate or modify drafts programmatically. |
| Publication admin/management (settings, editors, submissions workflow) | **Confirmed not documented** | Only "list contributor publications" is available. |
| Comments, stats/analytics, claps, followers management | **Confirmed not documented** | Out of scope for official API. |
| Webhooks/events | **Confirmed not documented** | No push/event model. |

### 1.4 Content formats and behavior notes

- **Formats:** `markdown` and `html` accepted for `contentFormat` (Confirmed). Medium converts/renders internally; fidelity is not guaranteed for complex embeds/custom HTML.
- **Draft-first safety:** `publishStatus=draft` is the safest default (Confirmed). Publishing is harder to reverse programmatically because updates/deletes are not exposed.
- **Canonical cross-posting:** `canonicalUrl` should be set when syndicating to avoid SEO/ownership ambiguity (Confirmed parameter; operational effect is platform-controlled).
- **Tags:** Up to 5 tags; Medium may normalize/ignore invalid tags (Confirmed/behavioral).
- **Idempotency:** No documented idempotency key; retries can create duplicate posts (Inferred/Important risk).

### 1.5 Rate limits, deprecations, limitations

| Topic | Confidence | Details |
|---|---|---|
| Rate limits | **Uncertain / partially documented historically** | Official docs did not prominently specify strict numeric quotas; clients should expect enforcement (HTTP 429/5xx) and implement conservative backoff. Treat limits as undocumented. |
| Deprecation status | **Confirmed directionally** | Docs/SDK repos archived; ecosystem signals deprecation/stagnation. No formal 2026 sunset notice verified here. |
| Error model | **Confirmed (typical)** | JSON error responses with HTTP status codes (401/403/400/429/5xx). Must handle auth revocation and partial feature availability. |
| Image upload constraints | **Confirmed historically** | Limited formats (jpeg/png/gif/tiff) and size caps; verify current limits at runtime. |

## 2) Alternatives for reading/writing/managing content

| Approach | Read | Write | Edit/Delete | Confidence | Pros | Cons / risks |
|---|---|---|---|---|---|---|
| **Official API** | Profile/publications only | Create post/draft, upload image | No | Confirmed capabilities; availability uncertain | Stable contract (where available), token/OAuth auth, lowest ToS ambiguity | Very limited surface; token issuance uncertain; no read-back/edit/delete/list posts |
| **RSS/Atom feeds** (`/feed/@user`, `/feed/publication`, tag feeds) | Public posts metadata/content excerpts or full content depending on feed | No | No | **Confirmed (platform feature)** | Simple, no auth for public content, good for monitoring/import | Public content only, rate/format variability, not a management API |
| **Medium JSON/feed variant** (e.g. `?format=json` / feed endpoints returning JSON in some contexts) | Public content (undocumented behavior) | No | No | **Unofficial/Uncertain** | Machine-readable in some cases | Undocumented, can change/break without notice |
| **Unofficial APIs / community libraries** (wrappers around legacy endpoints or internal calls) | Sometimes | Sometimes | Rare/fragile | **Unofficial** | Can fill gaps (list/read in some cases) | Breakage, maintenance risk, unclear correctness/licensing |
| **Browser automation** (Playwright/Selenium driving Medium UI) | Possible | Possible | Possible | **Unofficial** | Closest to UI parity | ToS risk, brittle selectors, MFA/captcha/login friction, credential exposure, high maintenance, account risk |
| **Internal/GraphQL endpoints** (reverse-engineered web/app calls) | Possible | Possible | Possible (fragile) | **Unofficial/High risk** | Can access features not in public API | Explicitly unstable/private; auth/cookies required; high ToS/compliance and breakage risk |
| **Import workflows** (generate Markdown/HTML + canonical URL; user pastes/imports into Medium editor or uses Medium's import story flow where available) | N/A | Assisted/manual publish | Manual | **Confirmed as workflow pattern** | Safe, ToS-friendly, preserves user control | Not automated end-to-end; UX friction |
| **Email/publishing integrations (if available to user)** | No | Limited | No | **Uncertain** | Low-tech fallback | Availability/formatting constraints vary |

### ToS / maintenance / security considerations (cross-cutting)

- **Terms of Service:** Automated access that mimics browsers, bypasses controls, or uses undocumented endpoints may violate Medium policies; review current Medium Terms/Developer terms before shipping unofficial modes.
- **Credentials:** Integration tokens, cookies, or session exports are sensitive. Never log them; store in env/secret manager; prefer least privilege and draft-only operations.
- **Account safety:** Aggressive automation can trigger anti-abuse protections/captchas or account actions.
- **Supply chain/maintenance:** Unofficial libraries may be abandoned; pin, audit, and isolate behind adapters.

## 3) Realistic feasibility for an MCP server

### Feasibility matrix

| MCP capability goal | Feasibility (official-only) | Feasibility (with unofficial methods) | Recommendation |
|---|---|---|---|
| Get authenticated user/profile | **High** (`/me`) if token works | High | Implement (official mode). |
| List contributor publications | **Medium-High** (`/users/:id/publications`) | High | Implement (official mode). |
| Create draft/post (user/publication) | **Medium-High** | High | Implement as core write action; default `draft`. |
| Upload image and embed URL | **Medium** | Medium-High | Implement if needed; validate MIME/size; handle failures. |
| List user's posts / search posts | **Low/None** officially | Medium but fragile (feeds/unofficial) | Provide RSS/feed-based read for public posts; label partial/approximate. |
| Read post content | **None** officially | Medium (RSS/scrape; partial for members-only) | RSS/import/export-based reads only; no paywalled/private guarantees. |
| Edit/update/delete post | **None** officially | Low-Medium (browser automation/internal APIs) | **Do not promise** in default product; optional experimental plugin only with explicit risk opt-in. |
| Manage publications (admin/settings/submissions) | **None** officially | Low/fragile | Out of scope for MVP. |
| Robust "publish everywhere" parity | **Low** | Low-Medium | Position as drafting/publishing assistant with clear capability disclosure. |

### Recommended approach(es) and tradeoffs

1. **Recommended default: "Safe Draft + Read + Export" (hybrid, official-first)**
   - **Write path:** Use official API when a valid token is available: `get_profile`, `list_publications`, `create_draft_post`, `upload_image`. Default to `publishStatus=draft`, require explicit confirmation/flag for `public`.
   - **Read path:** Use RSS/Atom feeds for public content discovery and optional ingestion; clearly mark as public-only and possibly truncated.
   - **Fallback path:** Always offer content rendering/export (Markdown/HTML + frontmatter/canonical metadata) so the server remains useful even if Medium API access is unavailable.
   - **Tradeoff:** Not full lifecycle management, but highest reliability/safety and lowest compliance risk.

2. **Optional advanced mode: "Unofficial automation adapter" (explicit opt-in, off by default)**
   - Browser automation or internal-endpoint adapter behind a feature flag and strong warnings.
   - **Tradeoff:** Closer to edit/delete/manage parity, but brittle, higher security/ToS/account risk, and substantial maintenance burden. Not recommended for MVP.

3. **Not recommended as primary: unofficial-only integration**
   - Would block many users on auth/captcha brittleness and create ongoing breakage.

### Auth UX recommendations

- **Local stdio (Claude Desktop/Code, IDEs, terminal):** env var `MEDIUM_TOKEN` (or host secret store); optional per-call override prohibited by default in logs; validate via `GET /me` on startup/tool call and return actionable errors.
- **Remote Streamable HTTP / multi-user:** prefer per-user OAuth if feasible; otherwise do not store long-lived shared tokens. Given OAuth/app-registration uncertainty, a remote deployment may need to be **read-only/export-only** or require users to supply tokens at runtime via secure channel (careful: prompt/session leakage risks).
- **Capability discovery:** expose a `capabilities`/`whoami`-style tool or resource describing which mode is active (official write, feed read, export-only) based on configured credentials.

### Key risks

- **Product risk:** Users expect "list/edit/delete my posts"; official API cannot deliver this.
- **Operational risk:** Token issuance/enforcement may block new users; legacy behavior may change without notice.
- **Data integrity risk:** No idempotency -> duplicate posts on retries/timeouts.
- **Security/compliance risk:** Token/cookie handling, prompt injection causing unintended publish, unofficial automation ToS exposure.
- **Content fidelity risk:** Markdown/HTML conversion and Medium rendering quirks.

## Sources

- [Medium API documentation (official GitHub repo, archived)](https://github.com/Medium/medium-api-docs)
- [Medium API docs: Getting Started / README](https://github.com/Medium/medium-api-docs/blob/master/README.md)
- [Medium Developers portal (historical entry point)](https://medium.com/developers)
- [Medium RSS feeds help/documentation (Medium Help Center)](https://help.medium.com/hc/en-us/articles/214874118-Using-RSS-feeds-of-profiles-publications-and-topics)
- [Medium Help Center: Importing a story](https://help.medium.com/hc/en-us/articles/214550207-Import-a-story-to-Medium)
- [Medium Terms of Service](https://policy.medium.com/medium-terms-of-service-9db0094a1e0f)
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification)

*Research limitation:* Live `web_search`/`web_fetch` verification was not successfully executable in this run; links above should be re-validated (HTTP status/content/date) during implementation.
