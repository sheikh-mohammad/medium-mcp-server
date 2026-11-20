"""Content rendering and normalization transforms."""

from __future__ import annotations

from typing import Any

from .models import ContentFormat, PreparedPost
from .validation import detect_fidelity_warnings, validate_and_normalize_post


def render_prepared_post(
    prepared: PreparedPost,
    *,
    target_format: ContentFormat | None = None,
) -> dict[str, Any]:
    """Render a prepared post to a Medium-compatible payload representation.

    MVP rendering is conservative: it preserves content and emits warnings for
    potentially lossy/unsupported constructs. It does not claim perfect Medium parity.
    """
    warnings: list[str] = []
    notes = list(prepared.normalization_notes)

    target = target_format or prepared.content_format
    content = prepared.content
    content_format: ContentFormat = prepared.content_format

    if target not in {"markdown", "html"}:
        warnings.append(f"Unsupported target_format '{target}'; using source format instead.")
        target = prepared.content_format

    if target != prepared.content_format:
        # Deterministic, conservative conversion with explicit warning.
        if prepared.content_format == "markdown" and target == "html":
            content_format = "html"
            content = _markdown_to_simple_html(prepared.content)
            warnings.append(
                "Converted markdown to basic HTML conservatively; review formatting before publishing."
            )
            notes.append("Applied conservative markdown-to-HTML rendering.")
        elif prepared.content_format == "html" and target == "markdown":
            content_format = "markdown"
            content = _html_to_simple_markdown(prepared.content)
            warnings.append(
                "Converted HTML to basic markdown conservatively; formatting may be lossy."
            )
            notes.append("Applied conservative HTML-to-markdown rendering.")
        else:
            content_format = prepared.content_format
            warnings.append("Requested format conversion is not supported; kept source format.")
    else:
        content_format = target

    warnings.extend(detect_fidelity_warnings(content, content_format))

    metadata = {
        "canonical_url": prepared.canonical_url,
        "license": prepared.license,
        "publish_status_intent": prepared.publish_status_intent,
        "publication_id": prepared.publication_id,
        "idempotency_key": prepared.idempotency_key,
        "normalization_notes": notes,
    }
    return {
        "content_format": content_format,
        "content": content,
        "title": prepared.title,
        "tags": list(prepared.tags),
        "metadata": metadata,
        "warnings": _dedupe_strings(warnings),
    }


def prepare_and_render(
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
    target_format: ContentFormat | None = None,
) -> tuple[PreparedPost | None, dict[str, Any] | None, dict[str, Any]]:
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
    rendered = render_prepared_post(prepared, target_format=target_format) if prepared else None
    return prepared, rendered, validation.to_dict()


def _markdown_to_simple_html(markdown: str) -> str:
    """Very conservative markdown-to-HTML wrapper for deterministic export/rendering."""
    # Avoid heavy dependencies and lossy transforms; preserve content.
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    paragraphs = [p.strip() for p in escaped.split("\n\n")]
    parts = [f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p]
    return "\n".join(parts) if parts else "<p></p>"


def _html_to_simple_markdown(html: str) -> str:
    """Very conservative HTML-to-markdown pass-through for deterministic behavior."""
    # Preserve text as-is with minimal tag stripping cues; callers are warned about lossy conversion.
    text = html
    replacements = [
        ("<br>", "\n"),
        ("<br/>", "\n"),
        ("<br />", "\n"),
        ("</p>", "\n\n"),
        ("<p>", ""),
    ]
    for old, new in replacements:
        text = text.replace(old, new).replace(old.upper(), new)
    return text.strip()


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
