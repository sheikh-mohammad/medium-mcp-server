"""Public RSS/Atom feed adapter (best-effort, bounded, no auth)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser  # type: ignore[import-untyped]
import httpx

from ..domain.models import FeedItem, SourceType
from ..errors import (
    ToolError,
    rate_limited,
    success_result,
    timeout_error,
    unavailable,
    upstream_error,
    validation_error,
)

MODE = "feed_read"
DEFAULT_LIMIT = 10
MAX_LIMIT = 25
MAX_FEED_BYTES = 2_000_000
MAX_TEXT_CHARS = 20_000
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(slots=True)
class NormalizedFeedSource:
    input_source: str
    source_type: SourceType
    feed_url: str
    warnings: list[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_handle(value: str) -> str:
    v = value.strip()
    if v.startswith("@"):
        v = v[1:]
    # Allow full medium profile URLs in user/publication-ish inputs best-effort.
    if _is_http_url(v):
        parsed = urlparse(v)
        path = (parsed.path or "").strip("/")
        if path.startswith("@"):
            return path[1:].split("/", 1)[0]
        if path.startswith("feed/@"):
            return path[len("feed/@") :].split("/", 1)[0]
        if path:
            return path.split("/", 1)[0]
    return v.strip("/")


def _normalize_tag(value: str) -> str:
    v = value.strip().strip("/")
    if _is_http_url(v):
        parsed = urlparse(v)
        path = (parsed.path or "").strip("/")
        if path.startswith("feed/tag/"):
            return path[len("feed/tag/") :].split("/", 1)[0]
        if path.startswith("tag/"):
            return path[len("tag/") :].split("/", 1)[0]
    if v.startswith("tag/"):
        v = v[4:]
    return v


def normalize_feed_source(source: str, source_type: str | None = None) -> NormalizedFeedSource | ToolError:
    if source is None or not str(source).strip():
        return validation_error("source is required.", field="source")

    raw = str(source).strip()
    st_raw = (source_type or "").strip().lower() if source_type is not None else ""

    if st_raw and st_raw not in {"user", "publication", "tag", "url"}:
        return validation_error(
            "source_type must be one of: user, publication, tag, url.",
            field="source_type",
        )

    inferred: SourceType
    if st_raw:
        inferred = st_raw  # type: ignore[assignment]
    elif _is_http_url(raw):
        inferred = "url"
    elif raw.startswith("@"):
        inferred = "user"
    elif "/tag/" in raw or raw.startswith("tag/"):
        inferred = "tag"
    else:
        # Best-effort default: treat bare handle/slug as user feed.
        inferred = "user"

    warnings: list[str] = []

    if inferred == "url":
        if not _is_http_url(raw):
            return validation_error("source must be a valid http(s) URL when source_type is 'url'.", field="source")
        feed_url = raw
        if "/feed" not in urlparse(raw).path:
            warnings.append("Provided URL does not look like a Medium feed URL; attempting to parse as-is.")
    elif inferred == "user":
        handle = _normalize_handle(raw)
        if not handle:
            return validation_error("Unable to normalize user handle from source.", field="source")
        feed_url = f"https://medium.com/feed/@{handle}"
    elif inferred == "publication":
        slug = _normalize_handle(raw)
        if not slug:
            return validation_error("Unable to normalize publication identifier from source.", field="source")
        feed_url = f"https://medium.com/feed/{slug}"
    else:  # tag
        tag = _normalize_tag(raw)
        if not tag:
            return validation_error("Unable to normalize tag identifier from source.", field="source")
        feed_url = f"https://medium.com/feed/tag/{tag}"

    return NormalizedFeedSource(
        input_source=raw,
        source_type=inferred,
        feed_url=feed_url,
        warnings=warnings,
    )


def _bounded_limit(limit: Any) -> tuple[int, list[str]] | ToolError:
    if limit is None:
        return DEFAULT_LIMIT, []
    try:
        value = int(limit)
    except Exception:
        return validation_error("limit must be an integer.", field="limit")
    if value < 1:
        return validation_error("limit must be >= 1.", field="limit")
    if value > MAX_LIMIT:
        return MAX_LIMIT, [f"limit capped at {MAX_LIMIT} items."]
    return value, []


def _truncate_text(value: str | None, max_chars: int = MAX_TEXT_CHARS) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    text = str(value)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n...[truncated]", True


def _entry_text(entry: Any) -> tuple[str | None, str | None]:
    summary = getattr(entry, "summary", None) or entry.get("summary") if isinstance(entry, dict) else None
    content_val = None
    contents = getattr(entry, "content", None) or (entry.get("content") if isinstance(entry, dict) else None)
    if isinstance(contents, list) and contents:
        first = contents[0]
        if isinstance(first, dict):
            content_val = first.get("value") or first.get("content")
        else:
            content_val = getattr(first, "value", None)
    if content_val is None and isinstance(entry, dict):
        content_val = entry.get("content")
    return (str(summary) if summary is not None else None, str(content_val) if content_val is not None else None)


def _entry_tags(entry: Any) -> list[str]:
    tags_raw = getattr(entry, "tags", None) or (entry.get("tags") if isinstance(entry, dict) else None) or []
    tags: list[str] = []
    seen: set[str] = set()
    for t in tags_raw:
        term = None
        if isinstance(t, dict):
            term = t.get("term") or t.get("label")
        else:
            term = getattr(t, "term", None) or getattr(t, "label", None)
        if term is None:
            continue
        s = str(term).strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        tags.append(s)
    return tags


def _parse_feed_items(
    feed_text: str,
    *,
    limit: int,
    include_content: bool,
    warnings: list[str],
) -> list[dict[str, Any]]:
    parsed = feedparser.parse(feed_text)
    if getattr(parsed, "bozo", False):
        bozo_exc = getattr(parsed, "bozo_exception", None)
        warnings.append(
            "Feed parser reported malformed/partial content; results may be incomplete"
            + (f" ({bozo_exc})." if bozo_exc else ".")
        )

    entries = list(getattr(parsed, "entries", []) or [])
    if len(entries) > limit:
        warnings.append(f"Feed contained {len(entries)} entries; returning first {limit}.")

    items: list[FeedItem] = []
    for entry in entries[:limit]:
        guid = getattr(entry, "id", None) or (entry.get("id") if isinstance(entry, dict) else None)
        if guid is None:
            guid = getattr(entry, "guid", None) or (entry.get("guid") if isinstance(entry, dict) else None)
        title = getattr(entry, "title", None) or (entry.get("title") if isinstance(entry, dict) else None)
        link = getattr(entry, "link", None) or (entry.get("link") if isinstance(entry, dict) else None)
        published = (
            getattr(entry, "published", None)
            or getattr(entry, "updated", None)
            or (entry.get("published") if isinstance(entry, dict) else None)
            or (entry.get("updated") if isinstance(entry, dict) else None)
        )
        author = getattr(entry, "author", None) or (entry.get("author") if isinstance(entry, dict) else None)
        summary, content_val = _entry_text(entry)

        summary_out, trunc_sum = _truncate_text(summary)
        content_out, trunc_content = _truncate_text(content_val) if include_content else (None, False)
        if trunc_sum or trunc_content:
            warnings.append("One or more feed item fields were truncated to size limits.")

        if not include_content:
            content_out = None
        elif content_out is None and summary_out is not None:
            # Best-effort: some feeds only provide summary/description.
            content_out = summary_out

        tags = _entry_tags(entry)
        items.append(
            FeedItem(
                id=str(guid) if guid is not None else None,
                title=str(title) if title is not None else None,
                link=str(link) if link is not None else None,
                published_at=str(published) if published is not None else None,
                author=str(author) if author is not None else None,
                summary=summary_out,
                content=content_out,
                tags=tags,
            )
        )

    return [i.to_dict() for i in items]


def _fetch_feed_text(feed_url: str, timeout_seconds: float) -> str | ToolError:
    headers = {
        "User-Agent": "medium-mcp-server/0.1 (+https://modelcontextprotocol.io; public feed reader)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }
    attempts = 2
    last_err: Exception | None = None
    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=timeout_seconds, follow_redirects=True, headers=headers) as client:
                with client.stream("GET", feed_url) as resp:
                    status = resp.status_code
                    if status == 429:
                        return rate_limited(
                            "Public feed request was rate limited.",
                            status_code=status,
                            source_url=feed_url,
                        )
                    if status == 404:
                        return unavailable(
                            "Public feed source was not found.",
                            status_code=status,
                            source_url=feed_url,
                        )
                    if status >= 400:
                        if status in RETRYABLE_STATUS_CODES and attempt + 1 < attempts:
                            time.sleep(0.2 * (attempt + 1))
                            continue
                        return upstream_error(
                            "Failed to fetch public feed.",
                            status_code=status,
                            source_url=feed_url,
                        )

                    chunks: list[bytes] = []
                    total = 0
                    truncated = False
                    for chunk in resp.iter_bytes():
                        if not chunk:
                            continue
                        remaining = MAX_FEED_BYTES - total
                        if remaining <= 0:
                            truncated = True
                            break
                        if len(chunk) > remaining:
                            chunks.append(chunk[:remaining])
                            total += remaining
                            truncated = True
                            break
                        chunks.append(chunk)
                        total += len(chunk)
                    body = b"".join(chunks)
                    try:
                        text = body.decode(resp.encoding or "utf-8", errors="replace")
                    except Exception:
                        text = body.decode("utf-8", errors="replace")
                    if truncated:
                        text += "\n<!-- feed content truncated by size limit -->"
                    return text
        except httpx.TimeoutException as exc:
            last_err = exc
            if attempt + 1 < attempts:
                time.sleep(0.2 * (attempt + 1))
                continue
            return timeout_error("Timed out while fetching public feed.", source_url=feed_url)
        except httpx.RequestError as exc:
            last_err = exc
            if attempt + 1 < attempts:
                time.sleep(0.2 * (attempt + 1))
                continue
            return upstream_error(
                "Network error while fetching public feed.",
                source_url=feed_url,
            )
    return upstream_error("Failed to fetch public feed.", source_url=feed_url, detail=str(last_err) if last_err else None)


def read_public_feed(
    *,
    source: str,
    source_type: str | None = None,
    limit: Any = None,
    include_content: bool = False,
    request_timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    normalized = normalize_feed_source(source, source_type)
    if isinstance(normalized, ToolError):
        return {
            "ok": False,
            "mode": MODE,
            "data": None,
            "warnings": [],
            "next_actions": [],
            "error": normalized.to_dict(),
        }

    bounded = _bounded_limit(limit)
    if isinstance(bounded, ToolError):
        return {
            "ok": False,
            "mode": MODE,
            "data": {"source": normalized.feed_url, "source_type": normalized.source_type},
            "warnings": list(normalized.warnings),
            "next_actions": [],
            "error": bounded.to_dict(),
        }
    lim, limit_warnings = bounded

    warnings = list(normalized.warnings) + list(limit_warnings)
    fetched = _fetch_feed_text(normalized.feed_url, timeout_seconds=request_timeout_seconds)
    if isinstance(fetched, ToolError):
        return {
            "ok": False,
            "mode": MODE,
            "data": {
                "source": {
                    "input": normalized.input_source,
                    "type": normalized.source_type,
                    "feed_url": normalized.feed_url,
                },
            },
            "warnings": warnings,
            "next_actions": fetched.next_actions,
            "error": fetched.to_dict(),
        }

    items = _parse_feed_items(fetched, limit=lim, include_content=bool(include_content), warnings=warnings)
    if not items and "Feed parser reported malformed/partial content" not in " ".join(warnings):
        warnings.append("No feed items were found; the source may have no public posts or may use an unsupported feed format.")

    data = {
        "items": items,
        "source": {
            "input": normalized.input_source,
            "type": normalized.source_type,
            "feed_url": normalized.feed_url,
        },
        "fetched_at": _now_iso(),
        "warnings": list(warnings),
    }
    return success_result(
        MODE,
        data,
        warnings=warnings,
        next_actions=[
            "Public feed data is best-effort and public-only; verify details on Medium if needed.",
            "Use prepare_post/render_medium_content/export_post_bundle to repurpose public content.",
        ],
    )
