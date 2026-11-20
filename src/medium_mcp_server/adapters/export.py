"""Export/prepare adapter (always-on, no Medium credentials required)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from ..domain.models import ContentFormat, PreparedPost
from ..domain.transforms import render_prepared_post
from ..domain.validation import ValidationResult, validate_and_normalize_post
from ..errors import ToolError, success_result, unsupported_capability, validation_error

MODE = "export"

_LATEST_EXPORT: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_latest_export(payload: dict[str, Any]) -> None:
    global _LATEST_EXPORT
    _LATEST_EXPORT = payload


def get_latest_export_metadata() -> dict[str, Any] | None:
    return _LATEST_EXPORT


def _suggested_next_actions(prepared: PreparedPost, validation: ValidationResult) -> list[str]:
    actions: list[str] = []
    if validation.warnings:
        actions.append("Review validation warnings and adjust content/metadata for better fidelity.")
    actions.append("Use render_medium_content to inspect the Medium-compatible rendered payload.")
    actions.append("Use export_post_bundle to generate an inline export bundle/manifest.")
    if prepared.publish_status_intent in {"public", "unlisted"}:
        actions.append(
            "If using official_api in a later phase, run preflight checks and require explicit confirm=true before publish."
        )
    else:
        actions.append("Draft-first is recommended when official publishing capabilities are available.")
    actions.append(
        "Without official API capabilities, copy/export the prepared content into Medium manually."
    )
    return actions


def prepare_post(
    *,
    title: str | None = None,
    content: str | None = None,
    content_format: str | None = None,
    tags: list[str] | None = None,
    canonical_url: str | None = None,
    license: str | None = None,  # noqa: A002
    publish_status_intent: str | None = None,
    publication_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    prepared, validation = validate_and_normalize_post(
        title=title,
        content=content,
        content_format=content_format,
        tags=tags,
        canonical_url=canonical_url,
        license=license,
        publish_status_intent=publish_status_intent,
        publication_id=publication_id,
        idempotency_key=idempotency_key,
    )
    warnings = [w.message for w in validation.warnings]
    if not validation.ok:
        err = validation_error(
            "Post preparation failed validation.",
            validation=validation.to_dict(),
        )
        return {
            "ok": False,
            "mode": MODE,
            "data": {
                "prepared_post": None,
                "validation": validation.to_dict(),
                "medium_ready": False,
                "suggested_next_actions": [
                    "Fix validation errors and call prepare_post again.",
                    "Use medium://templates/post for a canonical template/checklist.",
                ],
            },
            "warnings": warnings,
            "next_actions": err.next_actions
            or ["Fix validation errors and call prepare_post again."],
            "error": err.to_dict(),
        }

    assert prepared is not None
    data = {
        "prepared_post": prepared.to_dict(),
        "validation": validation.to_dict(),
        "medium_ready": True,
        "suggested_next_actions": _suggested_next_actions(prepared, validation),
    }
    _set_latest_export(
        {
            "type": "prepared_post",
            "prepared_at": _now_iso(),
            "title": prepared.title,
            "content_format": prepared.content_format,
            "publish_status_intent": prepared.publish_status_intent,
            "idempotency_key": prepared.idempotency_key,
        }
    )
    return success_result(
        MODE,
        data,
        warnings=warnings,
        next_actions=["Use render_medium_content or export_post_bundle for next steps."],
    )


def _coerce_prepared_post(prepared_post: Any) -> PreparedPost | ToolError:
    if not isinstance(prepared_post, dict):
        return validation_error(
            "prepared_post must be an object/dict when provided.",
            field="prepared_post",
        )
    # Re-validate/normalize to ensure deterministic, safe rendering.
    prepared, validation = validate_and_normalize_post(
        title=prepared_post.get("title"),
        content=prepared_post.get("content"),
        content_format=prepared_post.get("content_format"),
        tags=prepared_post.get("tags"),
        canonical_url=prepared_post.get("canonical_url"),
        license=prepared_post.get("license"),
        publish_status_intent=prepared_post.get("publish_status_intent"),
        publication_id=prepared_post.get("publication_id"),
        idempotency_key=prepared_post.get("idempotency_key"),
    )
    if not validation.ok or prepared is None:
        return validation_error(
            "prepared_post is invalid; run prepare_post to generate a valid prepared post.",
            validation=validation.to_dict(),
        )
    return prepared


def render_medium_content(
    *,
    prepared_post: dict[str, Any] | None = None,
    target_format: ContentFormat | None = None,
    title: str | None = None,
    content: str | None = None,
    content_format: str | None = None,
    tags: list[str] | None = None,
    canonical_url: str | None = None,
    license: str | None = None,  # noqa: A002
    publish_status_intent: str | None = None,
    publication_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    validation_payload: dict[str, Any] | None = None
    prepared: PreparedPost | None = None

    if prepared_post is not None:
        coerced = _coerce_prepared_post(prepared_post)
        if isinstance(coerced, ToolError):
            return {
                "ok": False,
                "mode": MODE,
                "data": None,
                "warnings": [],
                "next_actions": ["Call prepare_post to produce a valid prepared_post."],
                "error": coerced.to_dict(),
            }
        prepared = coerced
        validation_payload = {"ok": True, "errors": [], "warnings": []}
    else:
        prepared, validation = validate_and_normalize_post(
            title=title,
            content=content,
            content_format=content_format,
            tags=tags,
            canonical_url=canonical_url,
            license=license,
            publish_status_intent=publish_status_intent,
            publication_id=publication_id,
            idempotency_key=idempotency_key,
        )
        validation_payload = validation.to_dict()
        if not validation.ok or prepared is None:
            err = validation_error(
                "Cannot render content because input validation failed.",
                validation=validation_payload,
            )
            return {
                "ok": False,
                "mode": MODE,
                "data": {"validation": validation_payload},
                "warnings": [w.message for w in validation.warnings],
                "next_actions": ["Fix validation errors and call prepare_post/render_medium_content again."],
                "error": err.to_dict(),
            }

    if target_format is not None and target_format not in {"markdown", "html"}:
        err = validation_error(
            "target_format must be 'markdown' or 'html' when provided.",
            field="target_format",
        )
        return {
            "ok": False,
            "mode": MODE,
            "data": {"validation": validation_payload},
            "warnings": [],
            "next_actions": ["Use target_format 'markdown' or 'html'."],
            "error": err.to_dict(),
        }

    rendered = render_prepared_post(prepared, target_format=target_format)
    data = {
        **rendered,
        "validation": validation_payload,
    }
    _set_latest_export(
        {
            "type": "rendered_content",
            "rendered_at": _now_iso(),
            "title": rendered.get("title"),
            "content_format": rendered.get("content_format"),
        }
    )
    return success_result(
        MODE,
        data,
        warnings=list(rendered.get("warnings") or []),
        next_actions=["Use export_post_bundle to generate an inline export bundle/manifest."],
    )


def _bundle_hash(prepared: PreparedPost, rendered: dict[str, Any]) -> str:
    basis = json.dumps(
        {
            "title": prepared.title,
            "content_format": rendered.get("content_format"),
            "content": rendered.get("content"),
            "tags": prepared.tags,
            "canonical_url": prepared.canonical_url,
            "license": prepared.license,
            "publish_status_intent": prepared.publish_status_intent,
            "publication_id": prepared.publication_id,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def export_post_bundle(
    *,
    prepared_post: dict[str, Any] | None = None,
    output: str | None = "inline",
    path: str | None = None,
    include_manifest: bool | None = True,
) -> dict[str, Any]:
    # MVP: inline-only, no filesystem writes.
    if output not in {None, "inline", "path"}:
        err = validation_error(
            "output must be 'inline' or 'path' when provided.",
            field="output",
        )
        return {
            "ok": False,
            "mode": MODE,
            "data": None,
            "warnings": [],
            "next_actions": ["Use output='inline' (MVP default)."],
            "error": err.to_dict(),
        }

    if path is not None and str(path).strip():
        err = unsupported_capability(
            "export_post_bundle path writes are not supported in this MVP; use inline output instead.",
            alternatives=[
                "Call export_post_bundle with output='inline' (or omit output/path).",
                "Save the returned inline bundle/manifest in your client/workspace if needed.",
            ],
            field="path",
        )
        return {
            "ok": False,
            "mode": MODE,
            "data": None,
            "warnings": [],
            "next_actions": err.next_actions,
            "error": err.to_dict(),
        }

    if output == "path":
        err = unsupported_capability(
            "output='path' is not supported in this MVP; export_post_bundle is inline-only.",
            alternatives=[
                "Call export_post_bundle with output='inline' (or omit output).",
                "Use the returned inline bundle/manifest without filesystem writes.",
            ],
            field="output",
        )
        return {
            "ok": False,
            "mode": MODE,
            "data": None,
            "warnings": [],
            "next_actions": err.next_actions,
            "error": err.to_dict(),
        }

    if prepared_post is None:
        err = validation_error("prepared_post is required.", field="prepared_post")
        return {
            "ok": False,
            "mode": MODE,
            "data": None,
            "warnings": [],
            "next_actions": ["Call prepare_post first, then pass its prepared_post to export_post_bundle."],
            "error": err.to_dict(),
        }

    coerced = _coerce_prepared_post(prepared_post)
    if isinstance(coerced, ToolError):
        return {
            "ok": False,
            "mode": MODE,
            "data": None,
            "warnings": [],
            "next_actions": ["Call prepare_post to produce a valid prepared_post."],
            "error": coerced.to_dict(),
        }
    prepared = coerced
    rendered = render_prepared_post(prepared)

    content_hash = _bundle_hash(prepared, rendered)
    content_ext = "md" if rendered.get("content_format") == "markdown" else "html"
    artifacts: dict[str, str] = {
        "title.txt": prepared.title,
        f"content.{content_ext}": str(rendered.get("content", "")),
        "metadata.json": json.dumps(rendered.get("metadata", {}), ensure_ascii=False, indent=2),
    }
    bundle = {
        "format": "medium-export-bundle/v1",
        "generated_at": _now_iso(),
        "prepared_post": prepared.to_dict(),
        "rendered": rendered,
        "artifacts": artifacts,
    }
    manifest = {
        "bundle_format": "medium-export-bundle/v1",
        "generated_at": bundle["generated_at"],
        "title": prepared.title,
        "content_format": rendered.get("content_format"),
        "tags": list(prepared.tags),
        "canonical_url": prepared.canonical_url,
        "license": prepared.license,
        "publish_status_intent": prepared.publish_status_intent,
        "publication_id": prepared.publication_id,
        "idempotency_key": prepared.idempotency_key,
        "content_sha256": content_hash,
        "warnings": list(rendered.get("warnings") or []),
        "files": list(artifacts.keys()),
    }

    data: dict[str, Any] = {"bundle": bundle}
    if include_manifest is not False:
        data["manifest"] = manifest
    else:
        data["manifest"] = None

    _set_latest_export(
        {
            "type": "export_bundle",
            "generated_at": bundle["generated_at"],
            "title": prepared.title,
            "content_sha256": content_hash,
            "publish_status_intent": prepared.publish_status_intent,
        }
    )
    return success_result(
        MODE,
        data,
        warnings=list(rendered.get("warnings") or []),
        next_actions=[
            "Copy the inline exported content into Medium manually if official API publishing is unavailable.",
            "Review warnings and run preflight_publish before any future publish action.",
        ],
    )


def get_post_template_resource() -> str:
    template = {
        "name": "medium-post-template",
        "version": 1,
        "description": "Canonical Medium-ready post template and checklist metadata.",
        "template": {
            "title": "Your post title",
            "content_format": "markdown",
            "content": "# Your post title\n\nWrite your Medium-ready content here.\n",
            "tags": ["tag-one", "tag-two"],
            "canonical_url": "https://example.com/original-post",
            "license": "all-rights-reserved",
            "publish_status_intent": "draft",
            "publication_id": None,
            "idempotency_key": "optional-stable-key-for-dedupe",
        },
        "checklist": [
            "Confirm title and content are non-empty and finalized.",
            "Keep tags to 5 or fewer relevant values.",
            "Set a canonical URL when cross-posting to avoid duplicate-content issues.",
            "Choose an appropriate license.",
            "Prefer draft status first; require explicit confirmation before any public/unlisted publish.",
            "Review formatting/fidelity warnings for embeds, custom HTML, and images.",
            "Verify capabilities via get_capabilities or medium://capabilities before mutating operations.",
        ],
        "notes": [
            "Export/prepare tools work without Medium credentials.",
            "export_post_bundle is inline-only in this MVP (no filesystem path writes).",
            "Official Medium API operations, when available, are capability-gated and draft-first.",
        ],
    }
    return json.dumps(template, ensure_ascii=False, indent=2)
