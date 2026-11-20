"""Capability detection and reporting."""

from __future__ import annotations

import time
from collections.abc import Iterable

from . import __version__
from .config import Settings
from .domain.models import AuthStatus, CapabilityMode, CapabilityReport

# Phase 1: export/prepare tools are implemented (always-on). Feed read and official
# API operation tools are registered in later phases; capability reporting must remain truthful.
IMPLEMENTED_TOOLS = [
    "get_capabilities",
    "prepare_post",
    "render_medium_content",
    "export_post_bundle",
]

PLANNED_FEED_TOOLS = ["read_public_feed"]
PLANNED_OFFICIAL_API_TOOLS = [
    "get_profile",
    "list_publications",
    "create_draft",
    "upload_image",
    "publish_post",
]

BASE_LIMITATIONS = [
    "No Medium post list/read/edit/delete parity is provided; use export bundles and manual steps when needed.",
    "Public feed read operations are not implemented yet (planned for a later phase).",
    "Official Medium API operation tools are not implemented yet (planned for a later phase).",
]
OFFICIAL_API_LIMITATIONS = [
    "Official Medium API is legacy/limited; no post list/read/edit/delete support is assumed.",
    "Create operations have no native idempotency guarantee; dedupe safeguards are best-effort.",
]


class CapabilityManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached_report: CapabilityReport | None = None
        self._cached_at: float = 0.0
        self._cache_ttl_seconds: float = 30.0
        self._official_api_valid: bool | None = None
        self._official_api_detail: str | None = None

    def invalidate(self) -> None:
        self._cached_report = None
        self._cached_at = 0.0
        self._official_api_valid = None
        self._official_api_detail = None

    def mark_official_api_auth_failure(self, detail: str) -> None:
        self._official_api_valid = False
        self._official_api_detail = detail
        self._cached_report = None
        self._cached_at = 0.0

    def mark_official_api_auth_success(self, detail: str = "Token probe succeeded.") -> None:
        self._official_api_valid = True
        self._official_api_detail = detail
        self._cached_report = None
        self._cached_at = 0.0

    def get_report(self, *, force_refresh: bool = False) -> CapabilityReport:
        now = time.monotonic()
        if (
            not force_refresh
            and self._cached_report is not None
            and (now - self._cached_at) < self._cache_ttl_seconds
        ):
            return self._cached_report
        report = self._compute_report()
        self._cached_report = report
        self._cached_at = now
        return report

    def _compute_report(self) -> CapabilityReport:
        modes: list[str] = [CapabilityMode.EXPORT.value, CapabilityMode.FEED_READ.value]
        active_capabilities: list[str] = [CapabilityMode.EXPORT.value]
        limitations = list(BASE_LIMITATIONS)
        warnings: list[str] = []
        supported_tools = list(IMPLEMENTED_TOOLS)

        token_configured = self.settings.medium_token_configured
        auth_detail = self._official_api_detail
        auth_valid = self._official_api_valid

        if self.settings.medium_enable_unofficial:
            warnings.append(
                "MEDIUM_ENABLE_UNOFFICIAL is set, but unofficial automation is not implemented in this MVP."
            )

        if token_configured:
            modes.append(CapabilityMode.OFFICIAL_API.value)
            if auth_valid is False:
                limitations.append(
                    "MEDIUM_TOKEN is configured but the official API capability is not currently available."
                )
                warnings.append(auth_detail or "Official API authentication/capability check failed.")
            else:
                # Config-gated; not treated as operation-ready until adapter/probe is implemented and succeeds.
                limitations.extend(OFFICIAL_API_LIMITATIONS)
                if auth_valid is None:
                    warnings.append(
                        "MEDIUM_TOKEN is configured; official API operation tools are not implemented yet and will require probe/adapter support in a later phase."
                    )
                elif auth_detail:
                    warnings.append(auth_detail)
        else:
            auth_detail = auth_detail or "No MEDIUM_TOKEN configured; official_api mode is disabled."

        auth = AuthStatus(
            configured=token_configured,
            provider="medium_legacy_token" if token_configured else None,
            valid=auth_valid,
            detail=auth_detail,
        )

        def dedupe(items: Iterable[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for item in items:
                if item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

        return CapabilityReport(
            modes=dedupe(modes),
            active_capabilities=dedupe(active_capabilities),
            auth=auth,
            supported_tools=dedupe(supported_tools),
            limitations=dedupe(limitations),
            warnings=dedupe(warnings),
            version=__version__,
        )

    def snapshot(self) -> dict[str, object]:
        return self.get_report().to_dict()


def build_capability_manager(settings: Settings) -> CapabilityManager:
    return CapabilityManager(settings)

