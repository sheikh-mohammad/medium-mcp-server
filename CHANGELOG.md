# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once releases begin.

## [Unreleased]

### Added

- Phase 0 scaffold: Python package (`pyproject.toml`, src layout), CLI entrypoint (`serve`, `doctor`, `--help`, `--version`), config/env loading, structured redacted logging, capability manager/reporting, MCP server assembly, and stdio/Streamable HTTP runtime wiring.
- Phase 1 always-useful core: `prepare_post`, `render_medium_content`, and `export_post_bundle` (inline-only MVP), validation/transforms/domain models, `medium://templates/post` and `medium://exports/latest` resources, and workflow prompts (`draft_medium_post`, `crosspost_checklist`, `preflight_publish`).
- Phase 2 public read: `read_public_feed` adapter/tool for best-effort public RSS/Atom sources with normalization, bounds, warnings, and error handling.
- Phase 3 official Medium API (capability-gated): token/config-based capability gating, profile/publications resources/tools, `create_draft`, optional `upload_image`, and confirmation-gated `publish_post` with fail-closed behavior and short-lived local dedupe safeguards.
- Phase 4 hardening/release readiness: audit logging for mutating operations, additional security/negative and redaction tests, CI workflow, optional Dockerfile for Streamable HTTP, compatibility matrix, and expanded README/docs for install/config/safety/deployment guidance.
- Product/technical specification, research docs, MVP implementation plan, and repository community/meta files.

### Changed

- Replaced placeholder README/roadmap content with implemented MVP capabilities, configuration, transport guidance, and verified-vs-unverified compatibility notes.
- Updated documentation index to include compatibility matrix and implementation-plan references.

### Notes

- Official Medium API token issuance and endpoint availability remain legacy/uncertain; official operations are optional and fail closed with export/manual alternatives.
- `export_post_bundle` remains inline-only in MVP (no filesystem path writes).
- Streamable HTTP MVP posture is localhost/deployment hooks only (no built-in multi-tenant auth). Remote deployments must add TLS/reverse-proxy auth/origin protections and rate/request limits.
