"""Core domain models for the Medium MCP server."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

ContentFormat = Literal["markdown", "html"]
PublishStatusIntent = Literal["draft", "public", "unlisted"]
SourceType = Literal["user", "publication", "tag", "url"]


class CapabilityMode(str, Enum):
    EXPORT = "export"
    FEED_READ = "feed_read"
    OFFICIAL_API = "official_api"
    UNOFFICIAL_AUTOMATION = "unofficial_automation"


@dataclass(slots=True)
class AuthStatus:
    configured: bool = False
    provider: str | None = None
    valid: bool | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "provider": self.provider,
            "valid": self.valid,
            "detail": self.detail,
        }


@dataclass(slots=True)
class CapabilityReport:
    modes: list[str] = field(default_factory=list)
    active_capabilities: list[str] = field(default_factory=list)
    auth: AuthStatus = field(default_factory=AuthStatus)
    supported_tools: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "modes": self.modes,
            "active_capabilities": self.active_capabilities,
            "auth": self.auth.to_dict(),
            "supported_tools": self.supported_tools,
            "limitations": self.limitations,
            "warnings": self.warnings,
            "version": self.version,
        }


@dataclass(slots=True)
class PreparedPost:
    title: str
    content: str
    content_format: ContentFormat
    tags: list[str] = field(default_factory=list)
    canonical_url: str | None = None
    license: str | None = None
    publish_status_intent: PublishStatusIntent = "draft"
    publication_id: str | None = None
    idempotency_key: str | None = None
    normalization_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "content_format": self.content_format,
            "tags": list(self.tags),
            "canonical_url": self.canonical_url,
            "license": self.license,
            "publish_status_intent": self.publish_status_intent,
            "publication_id": self.publication_id,
            "idempotency_key": self.idempotency_key,
            "normalization_notes": list(self.normalization_notes),
        }


@dataclass(slots=True)
class Publication:
    id: str
    name: str
    url: str
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "description": self.description,
        }


@dataclass(slots=True)
class Profile:
    id: str
    username: str | None = None
    name: str | None = None
    url: str | None = None
    image_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "url": self.url,
            "image_url": self.image_url,
        }


@dataclass(slots=True)
class FeedItem:
    id: str | None
    title: str | None
    link: str | None
    published_at: str | None = None
    author: str | None = None
    summary: str | None = None
    content: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "published_at": self.published_at,
            "author": self.author,
            "summary": self.summary,
            "content": self.content,
            "tags": list(self.tags),
        }


@dataclass(slots=True)
class OperationResult:
    ok: bool
    mode: str
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "data": self.data,
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
            "error": self.error,
        }
