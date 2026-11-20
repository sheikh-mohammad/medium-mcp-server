"""Official Medium API adapter (capability-gated, draft-first)."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from ..domain.models import Profile, Publication
from ..domain.validation import validate_and_normalize_post
from ..errors import (
    ToolError,
    auth_error,
    not_found,
    rate_limited,
    success_result,
    timeout_error,
    unavailable,
    unsupported_capability,
    upstream_error,
    validation_error,
)

MODE = "official_api"
DEDUPE_TTL_SECONDS = 600
DEDUPE_MAX_ENTRIES = 200


@dataclass(slots=True)
class DedupeEntry:
    key: str
    created_at: float
    payload: dict[str, Any]


class DedupeCache:
    def __init__(self, ttl_seconds: int = DEDUPE_TTL_SECONDS, max_entries: int = DEDUPE_MAX_ENTRIES):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, DedupeEntry] = {}
        self._lock = threading.Lock()

    def _prune_locked(self, now: float) -> None:
        expired = [k for k, v in self._entries.items() if (now - v.created_at) > self.ttl_seconds]
        for k in expired:
            self._entries.pop(k, None)
        if len(self._entries) > self.max_entries:
            # drop oldest
            for k, _ in sorted(self._entries.items(), key=lambda kv: kv[1].created_at)[
                : len(self._entries) - self.max_entries
            ]:
                self._entries.pop(k, None)

    def get(self, key: str) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            entry = self._entries.get(key)
            if not entry:
                return None
            return dict(entry.payload)

    def set(self, key: str, payload: dict[str, Any]) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            self._entries[key] = DedupeEntry(key=key, created_at=now, payload=dict(payload))


def _redact_for_error(text: str | None) -> str | None:
    if not text:
        return text
    # Avoid leaking tokens/secrets in upstream error bodies.
    lowered = text.lower()
    if "bearer" in lowered or "token" in lowered or "authorization" in lowered:
        return "***redacted***"
    # Keep short/safe snippets only.
    return text[:300]


def _json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        try:
            return response.text
        except Exception:
            return None


def _extract_error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                msg = first.get("message") or first.get("detail")
                if msg:
                    return str(msg)
        for key in ("message", "error", "detail"):
            if payload.get(key):
                return str(payload[key])
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    return None


class MediumOfficialApiClient:
    def __init__(
        self,
        base_url: str,
        token: str | None,
        timeout_seconds: float,
        *,
        on_auth_failure: Callable[[str], None] | None = None,
        on_auth_success: Callable[[str], None] | None = None,
    ) -> None:
        self.base_url = (base_url or "https://api.medium.com/v1").rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self._on_auth_failure = on_auth_failure
        self._on_auth_success = on_auth_success
        self._profile: Profile | None = None
        self._dedupe = DedupeCache()

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "medium-mcp-server/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        expected_status: tuple[int, ...] = (200, 201),
    ) -> Any | ToolError:
        if not self.configured:
            return unsupported_capability(
                "Official Medium API is unavailable because MEDIUM_TOKEN is not configured.",
                alternatives=[
                    "Use prepare_post/render_medium_content/export_post_bundle for manual publishing.",
                    "Use read_public_feed for public content discovery.",
                ],
            )

        url = path if path.startswith("http://") or path.startswith("https://") else f"{self.base_url}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                resp = client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body if files is None else None,
                    files=files,
                    data=None if files is None else json_body,
                )
        except httpx.TimeoutException:
            return timeout_error("Medium API request timed out.")
        except httpx.RequestError:
            return upstream_error("Network error while calling Medium API.")

        payload = _json_or_text(resp)
        message = _extract_error_message(payload)

        if resp.status_code in expected_status:
            if self._on_auth_success:
                try:
                    self._on_auth_success("Medium API request succeeded.")
                except Exception:
                    pass
            return payload

        if resp.status_code in (401, 403):
            detail = "Medium API authentication failed or token is invalid/revoked."
            self._profile = None
            if self._on_auth_failure:
                try:
                    self._on_auth_failure(detail)
                except Exception:
                    pass
            return auth_error(detail, status_code=resp.status_code, upstream_message=_redact_for_error(message))

        if resp.status_code == 404:
            return not_found("Requested Medium API resource was not found.", status_code=404, upstream_message=_redact_for_error(message))
        if resp.status_code == 429:
            return rate_limited("Medium API rate limit reached.", status_code=429, upstream_message=_redact_for_error(message))
        if resp.status_code == 400:
            return validation_error("Medium API rejected the request.", status_code=400, upstream_message=_redact_for_error(message))
        if 500 <= resp.status_code <= 599:
            return upstream_error("Medium API returned a server error.", status_code=resp.status_code, upstream_message=_redact_for_error(message))
        return upstream_error("Medium API request failed.", status_code=resp.status_code, upstream_message=_redact_for_error(message))

    def probe(self, force: bool = False) -> dict[str, Any] | ToolError:
        if not self.configured:
            return unsupported_capability(
                "Official Medium API is unavailable because MEDIUM_TOKEN is not configured.",
                alternatives=["Use export/prepare tools or read_public_feed instead."],
            )
        if self._profile is not None and not force:
            return {"user": self._profile.to_dict(), "mode": MODE}
        payload = self._request("GET", "/me")
        if isinstance(payload, ToolError):
            return payload
        user = self._parse_user_payload(payload)
        if isinstance(user, ToolError):
            return user
        self._profile = user
        return {"user": user.to_dict(), "mode": MODE}

    def _parse_user_payload(self, payload: Any) -> Profile | ToolError:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return upstream_error("Medium API /me response was missing expected user data.")
        user_id = data.get("id")
        if not user_id:
            return upstream_error("Medium API /me response did not include a user id.")
        return Profile(
            id=str(user_id),
            username=(str(data.get("username")) if data.get("username") is not None else None),
            name=(str(data.get("name")) if data.get("name") is not None else None),
            url=(str(data.get("url")) if data.get("url") is not None else None),
            image_url=(str(data.get("imageUrl")) if data.get("imageUrl") is not None else None),
        )

    def get_profile(self) -> dict[str, Any] | ToolError:
        probed = self.probe()
        if isinstance(probed, ToolError):
            return probed
        return probed

    def list_publications(self) -> dict[str, Any] | ToolError:
        probed = self.probe()
        if isinstance(probed, ToolError):
            return probed
        assert self._profile is not None
        payload = self._request("GET", f"/users/{self._profile.id}/publications")
        if isinstance(payload, ToolError):
            return payload
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return upstream_error("Medium API publications response was missing expected data.")
        pubs: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            pub_id = item.get("id")
            name = item.get("name")
            url = item.get("url")
            if not pub_id or not name or not url:
                continue
            pubs.append(
                Publication(
                    id=str(pub_id),
                    name=str(name),
                    url=str(url),
                    description=(str(item.get("description")) if item.get("description") is not None else None),
                ).to_dict()
            )
        return {"publications": pubs, "mode": MODE}

    def _content_hash_key(self, operation: str, payload: dict[str, Any]) -> str:
        basis = json.dumps({"operation": operation, **payload}, sort_keys=True, ensure_ascii=False, default=str)
        return f"{operation}:hash:{hashlib.sha256(basis.encode('utf-8')).hexdigest()}"

    def _dedupe_key(self, operation: str, idempotency_key: str | None, payload: dict[str, Any]) -> str:
        if idempotency_key and str(idempotency_key).strip():
            return f"{operation}:key:{str(idempotency_key).strip()}"
        return self._content_hash_key(operation, payload)

    def _resolve_post_input(
        self,
        *,
        prepared_post: dict[str, Any] | None,
        title: str | None,
        content: str | None,
        content_format: str | None,
        tags: list[str] | None,
        canonical_url: str | None,
        license: str | None,  # noqa: A002
        publish_status_intent: str | None,
        publication_id: str | None,
        idempotency_key: str | None,
        default_publish_status_intent: str,
    ) -> tuple[dict[str, Any], Any, list[str]] | ToolError:
        source = prepared_post if isinstance(prepared_post, dict) else {}
        prepared, validation = validate_and_normalize_post(
            title=title if title is not None else source.get("title"),
            content=content if content is not None else source.get("content"),
            content_format=content_format if content_format is not None else source.get("content_format"),
            tags=tags if tags is not None else source.get("tags"),
            canonical_url=canonical_url if canonical_url is not None else source.get("canonical_url"),
            license=license if license is not None else source.get("license"),
            publish_status_intent=(
                publish_status_intent
                if publish_status_intent is not None
                else source.get("publish_status_intent") or default_publish_status_intent
            ),
            publication_id=publication_id if publication_id is not None else source.get("publication_id"),
            idempotency_key=idempotency_key if idempotency_key is not None else source.get("idempotency_key"),
        )
        if not validation.ok or prepared is None:
            return validation_error("Post content is invalid.", validation=validation.to_dict())
        warnings = [w.message for w in validation.warnings]
        return (prepared.to_dict(), prepared, warnings)

    def create_post(
        self,
        *,
        action: str,  # create_draft | publish_post
        publish_status: str = "draft",
        prepared_post: dict[str, Any] | None = None,
        title: str | None = None,
        content: str | None = None,
        content_format: str | None = None,
        tags: list[str] | None = None,
        canonical_url: str | None = None,
        license: str | None = None,  # noqa: A002
        publication_id: str | None = None,
        notify_followers: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any] | ToolError:
        if publish_status not in {"draft", "public", "unlisted"}:
            return validation_error("publish_status must be 'draft', 'public', or 'unlisted'.", field="publish_status")
        if action == "publish_post" and publish_status not in {"public", "unlisted"}:
            return validation_error(
                "publish_post supports publish_status 'public' or 'unlisted'.",
                field="publish_status",
            )

        resolved = self._resolve_post_input(
            prepared_post=prepared_post,
            title=title,
            content=content,
            content_format=content_format,
            tags=tags,
            canonical_url=canonical_url,
            license=license,
            publish_status_intent=publish_status,
            publication_id=publication_id,
            idempotency_key=idempotency_key,
            default_publish_status_intent=publish_status,
        )
        if isinstance(resolved, ToolError):
            return resolved
        prepared_dict, prepared_model, warnings = resolved

        # Ensure profile for user-targeted posts.
        probed = self.probe()
        if isinstance(probed, ToolError):
            if probed.code.value in {"unsupported_capability", "auth_error"}:
                return probed
            return probed
        assert self._profile is not None

        target_publication_id = prepared_model.publication_id
        request_payload = {
            "title": prepared_model.title,
            "contentFormat": prepared_model.content_format,
            "content": prepared_model.content,
            "tags": prepared_model.tags,
            "canonicalUrl": prepared_model.canonical_url,
            "publishStatus": publish_status,
            "license": prepared_model.license,
            "notifyFollowers": bool(notify_followers),
        }
        # Remove nulls for cleaner API payloads.
        request_payload = {k: v for k, v in request_payload.items() if v is not None}

        dedupe_basis = {
            "target": target_publication_id or self._profile.id,
            "publish_status": publish_status,
            "payload": request_payload,
        }
        dedupe_key = self._dedupe_key(action, prepared_model.idempotency_key, dedupe_basis)
        cached = self._dedupe.get(dedupe_key)
        if cached is not None:
            cached_out = dict(cached)
            data = dict(cached_out.get("data") or {})
            dedupe_info = dict(data.get("dedupe") or {})
            dedupe_info.update(
                {
                    "status": "hit",
                    "key": dedupe_key,
                    "warning": "Returned cached result for a recently successful create operation; Medium API has no native idempotency guarantee.",
                }
            )
            data["dedupe"] = dedupe_info
            cached_out["data"] = data
            cached_out["warnings"] = list(cached_out.get("warnings") or []) + [
                "Duplicate create prevented using local dedupe cache; verify on Medium if needed."
            ]
            return cached_out

        if target_publication_id:
            path = f"/publications/{target_publication_id}/posts"
        else:
            path = f"/users/{self._profile.id}/posts"

        resp = self._request("POST", path, json_body=request_payload, expected_status=(200, 201))
        if isinstance(resp, ToolError):
            # Do not blindly retry creates; return actionable error.
            return resp

        resp_data: Any = resp.get("data") if isinstance(resp, dict) else None
        if not isinstance(resp_data, dict):
            return upstream_error("Medium API create response was missing expected post data.")

        post_out = {
            "id": (str(resp_data.get("id")) if resp_data.get("id") is not None else None),
            "url": (str(resp_data.get("url")) if resp_data.get("url") is not None else None),
            "publish_status": (str(resp_data.get("publishStatus") or publish_status)),
            "publication_id": (
                str(resp_data.get("publicationId"))
                if resp_data.get("publicationId") is not None
                else target_publication_id
            ),
            "canonical_url": (
                str(resp_data.get("canonicalUrl"))
                if resp_data.get("canonicalUrl") is not None
                else prepared_model.canonical_url
            ),
            "tags": resp_data.get("tags") if isinstance(resp_data.get("tags"), list) else prepared_model.tags,
        }
        result = {
            "ok": True,
            "mode": MODE,
            "data": {
                "post": post_out,
                "dedupe": {
                    "status": "stored",
                    "key": dedupe_key,
                    "warning": "Medium API has no native idempotency guarantee; local dedupe cache was updated.",
                },
            },
            "warnings": warnings + ["Medium API has no native idempotency guarantee; avoid blind retries on create/publish."],
            "next_actions": [
                "Verify the draft/post URL in Medium if needed.",
                "Use export_post_bundle as a fallback/manual record when appropriate.",
            ],
            "error": None,
        }
        self._dedupe.set(dedupe_key, result)
        return result

    def upload_image(
        self,
        *,
        image_path: str | None = None,
        image_bytes_base64: str | None = None,
        media_type: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any] | ToolError:
        probed = self.probe()
        if isinstance(probed, ToolError):
            return probed

        if (not image_path or not str(image_path).strip()) and not image_bytes_base64:
            return validation_error(
                "Provide either image_path or image_bytes_base64 (with media_type).",
                field="image_path",
            )
        if image_bytes_base64 and not media_type:
            return validation_error("media_type is required when image_bytes_base64 is provided.", field="media_type")

        content: bytes
        name: str
        mtype: str

        if image_bytes_base64:
            try:
                content = base64.b64decode(str(image_bytes_base64), validate=True)
            except Exception:
                return validation_error("image_bytes_base64 must be valid base64.", field="image_bytes_base64")
            name = filename or "upload"
            mtype = str(media_type)
        else:
            p = str(image_path).strip()
            if not os.path.exists(p) or not os.path.isfile(p):
                return validation_error("image_path must point to an existing file.", field="image_path")
            try:
                with open(p, "rb") as f:
                    content = f.read()
            except Exception:
                return validation_error("Unable to read image_path.", field="image_path")
            name = filename or os.path.basename(p) or "upload"
            guessed = mimetypes.guess_type(name)[0]
            mtype = str(media_type or guessed or "application/octet-stream")

        max_bytes = 10 * 1024 * 1024
        if len(content) == 0:
            return validation_error("Image content must not be empty.", field="image")
        if len(content) > max_bytes:
            return validation_error(f"Image exceeds maximum supported size ({max_bytes} bytes).", field="image")

        dedupe_key = f"upload_image:hash:{hashlib.sha256(content).hexdigest()}:{mtype}"
        cached = self._dedupe.get(dedupe_key)
        if cached is not None:
            cached_out = dict(cached)
            out_data = dict(cached_out.get("data") or {})
            dedupe_info = dict(out_data.get("dedupe") or {})
            dedupe_info.update({"status": "hit", "key": dedupe_key})
            out_data["dedupe"] = dedupe_info
            cached_out["data"] = out_data
            cached_out["warnings"] = list(cached_out.get("warnings") or []) + [
                "Duplicate image upload prevented using local dedupe cache."
            ]
            return cached_out

        files = {"image": (name, content, mtype)}
        resp = self._request("POST", "/images", files=files, expected_status=(200, 201))
        if isinstance(resp, ToolError):
            if resp.code.value == "unsupported_capability":
                return resp
            if resp.code.value == "auth_error":
                return resp
            # Some Medium deployments may not support upload; report clearly.
            return unavailable(
                "Image upload is unavailable or failed via the official Medium API.",
                upstream=resp.to_dict(),
            ) if resp.code.value in {"not_found", "upstream_error"} else resp

        resp_data: Any = resp.get("data") if isinstance(resp, dict) else None
        if not isinstance(resp_data, dict) or not resp_data.get("url"):
            return upstream_error("Medium API image upload response was missing an image URL.")

        result = success_result(
            MODE,
            {
                "url": str(resp_data.get("url")),
                "md5": (str(resp_data.get("md5")) if resp_data.get("md5") is not None else None),
            },
            warnings=["Medium image upload support/capabilities may vary by account/API availability."],
            next_actions=["Use the returned URL in your Medium-compatible content as needed."],
        )
        result["data"]["dedupe"] = {"status": "stored", "key": dedupe_key}
        self._dedupe.set(dedupe_key, result)
        return result
