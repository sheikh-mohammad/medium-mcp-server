"""Validation and normalization helpers for post preparation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from .models import SUPPORTED_LICENSES, ContentFormat, PreparedPost, PublishStatusIntent

MAX_TAGS = 5
MAX_TITLE_LENGTH = 300
MAX_CONTENT_LENGTH = 500_000
MAX_TAG_LENGTH = 100
MAX_IDEMPOTENCY_KEY_LENGTH = 256

_UNSUPPORTED_HTML_RE = re.compile(
    r"<\s*(script|style|iframe|object|embed|form)\b|on\w+\s*=|javascript:",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ValidationIssue:
    field: str
    message: str
    severity: str = "error"  # error | warning

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "message": self.message, "severity": self.severity}


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


def _is_valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_tags(tags: list[str] | None) -> tuple[list[str], list[str], list[str]]:
    """Return (normalized_tags, notes, warnings). Keeps first 5 valid unique tags."""
    if tags is None:
        return [], [], []
    notes: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    normalized: list[str] = []
    invalid_count = 0
    duplicate_count = 0
    for raw in tags:
        if raw is None:
            continue
        tag = str(raw).strip()
        if not tag:
            invalid_count += 1
            continue
        if len(tag) > MAX_TAG_LENGTH:
            warnings.append(f"Tag exceeds {MAX_TAG_LENGTH} characters and was skipped.")
            invalid_count += 1
            continue
        key = tag.lower()
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        normalized.append(tag)

    if invalid_count:
        notes.append(f"Skipped {invalid_count} invalid/empty tag(s).")
    if duplicate_count:
        notes.append(f"Removed {duplicate_count} duplicate tag(s).")
    if len(normalized) > MAX_TAGS:
        dropped = len(normalized) - MAX_TAGS
        warnings.append(
            f"Medium supports up to {MAX_TAGS} tags; kept first {MAX_TAGS} and dropped {dropped}."
        )
        notes.append(f"Truncated tags to first {MAX_TAGS}.")
        normalized = normalized[:MAX_TAGS]
    return normalized, notes, warnings


def detect_fidelity_warnings(content: str, content_format: ContentFormat) -> list[str]:
    warnings: list[str] = []
    if _UNSUPPORTED_HTML_RE.search(content):
        warnings.append(
            "Content may include unsupported or unsafe HTML constructs (e.g. script/iframe/style/forms/event handlers); Medium may strip or alter them."
        )
    if content_format == "html" and re.search(r"<\s*img\b", content, re.IGNORECASE):
        warnings.append(
            "HTML image embeds may require upload/hosting adjustments for Medium compatibility."
        )
    if content_format == "markdown" and re.search(r"```", content):
        warnings.append(
            "Code fences are included; verify formatting/fidelity in Medium's editor if needed."
        )
    return warnings


def validate_and_normalize_post(
    *,
    title: str | None,
    content: str | None,
    content_format: str | None,
    tags: list[str] | None = None,
    canonical_url: str | None = None,
    license: str | None = None,  # noqa: A002 - matches API field name
    publish_status_intent: str | None = None,
    publication_id: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[PreparedPost | None, ValidationResult]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    notes: list[str] = []

    # content_format
    fmt_raw = (content_format or "").strip().lower()
    if fmt_raw not in {"markdown", "html"}:
        errors.append(
            ValidationIssue(
                "content_format",
                "content_format must be 'markdown' or 'html'.",
            )
        )
        fmt: ContentFormat = "markdown"
    else:
        fmt = fmt_raw  # type: ignore[assignment]

    # title/content
    title_str = (title or "").strip()
    if not title_str:
        errors.append(ValidationIssue("title", "title is required and must be non-empty."))
    elif len(title_str) > MAX_TITLE_LENGTH:
        errors.append(
            ValidationIssue("title", f"title must be <= {MAX_TITLE_LENGTH} characters.")
        )

    content_str = content if content is not None else ""
    if not isinstance(content_str, str):
        content_str = str(content_str)
    # Conservative normalization: normalize line endings only.
    normalized_content = content_str.replace("\r\n", "\n").replace("\r", "\n")
    if normalized_content != content_str:
        notes.append("Normalized line endings to LF.")
    if not normalized_content.strip():
        errors.append(ValidationIssue("content", "content is required and must be non-empty."))
    elif len(normalized_content) > MAX_CONTENT_LENGTH:
        errors.append(
            ValidationIssue(
                "content",
                f"content exceeds maximum supported length ({MAX_CONTENT_LENGTH} characters).",
            )
        )

    # tags
    norm_tags, tag_notes, tag_warnings = normalize_tags(tags)
    notes.extend(tag_notes)
    for w in tag_warnings:
        warnings.append(ValidationIssue("tags", w))

    # canonical_url
    canonical: str | None = None
    if canonical_url is not None and str(canonical_url).strip():
        canonical = str(canonical_url).strip()
        if not _is_valid_url(canonical):
            errors.append(
                ValidationIssue(
                    "canonical_url",
                    "canonical_url must be a valid http(s) URL.",
                )
            )
    else:
        canonical = None

    # license
    lic: str | None = None
    if license is not None and str(license).strip():
        lic = str(license).strip()
        if lic not in SUPPORTED_LICENSES:
            errors.append(
                ValidationIssue(
                    "license",
                    f"license must be one of: {', '.join(SUPPORTED_LICENSES)}.",
                )
            )
    else:
        lic = None

    # publish_status_intent
    intent_raw = (publish_status_intent or "draft").strip().lower()
    if intent_raw not in {"draft", "public", "unlisted"}:
        errors.append(
            ValidationIssue(
                "publish_status_intent",
                "publish_status_intent must be 'draft', 'public', or 'unlisted'.",
            )
        )
        intent: PublishStatusIntent = "draft"
    else:
        intent = intent_raw  # type: ignore[assignment]

    # publication_id
    pub_id: str | None = None
    if publication_id is not None and str(publication_id).strip():
        pub_id = str(publication_id).strip()
    else:
        pub_id = None

    # idempotency_key
    idem: str | None = None
    if idempotency_key is not None and str(idempotency_key).strip():
        idem = str(idempotency_key).strip()
        if len(idem) > MAX_IDEMPOTENCY_KEY_LENGTH:
            errors.append(
                ValidationIssue(
                    "idempotency_key",
                    f"idempotency_key must be <= {MAX_IDEMPOTENCY_KEY_LENGTH} characters.",
                )
            )
    else:
        idem = None

    # Fidelity warnings (non-fatal)
    for w in detect_fidelity_warnings(normalized_content, fmt):
        warnings.append(ValidationIssue("content", w))

    ok = len(errors) == 0
    result = ValidationResult(ok=ok, errors=errors, warnings=warnings)

    prepared: PreparedPost | None = None
    if ok:
        prepared = PreparedPost(
            title=title_str,
            content=normalized_content,
            content_format=fmt,
            tags=norm_tags,
            canonical_url=canonical,
            license=lic,
            publish_status_intent=intent,
            publication_id=pub_id,
            idempotency_key=idem,
            normalization_notes=notes,
        )
    else:
        # Still provide a best-effort normalized representation in callers if desired;
        # PreparedPost requires non-empty title/content by contract, so omit when invalid.
        prepared = None

    return prepared, result
