from __future__ import annotations

from medium_mcp_server.capabilities import CapabilityManager
from medium_mcp_server.config import Settings

PHASE3_TOOLS = [
    "get_capabilities",
    "prepare_post",
    "render_medium_content",
    "export_post_bundle",
    "read_public_feed",
    "get_profile",
    "list_publications",
    "create_draft",
    "upload_image",
    "publish_post",
]


def test_capabilities_without_token() -> None:
    manager = CapabilityManager(Settings())
    report = manager.get_report()
    assert "export" in report.modes
    assert "feed_read" in report.modes
    assert "official_api" not in report.modes
    assert report.active_capabilities == ["export", "feed_read"]
    assert report.supported_tools == PHASE3_TOOLS
    assert report.auth.configured is False
    assert report.auth.provider is None
    assert report.auth.detail is not None
    assert report.version == "1.0.0"
    assert any("public feed reads are best-effort" in lim.lower() for lim in report.limitations)
    assert any("official medium api capabilities are unavailable" in lim.lower() for lim in report.limitations)


def test_capabilities_with_token_configured_unknown_probe() -> None:
    manager = CapabilityManager(Settings(medium_token="secret-token"))
    report = manager.get_report()
    assert "official_api" in report.modes
    assert report.active_capabilities == ["export", "feed_read"]
    assert report.auth.configured is True
    assert report.auth.provider == "medium_legacy_token"
    assert report.auth.valid is None
    assert report.supported_tools == PHASE3_TOOLS
    assert any("verified on first use/probe" in w for w in report.warnings)


def test_capabilities_with_token_probe_success() -> None:
    manager = CapabilityManager(Settings(medium_token="secret-token"))
    manager.mark_official_api_auth_success("Token probe succeeded.")
    report = manager.get_report(force_refresh=True)
    assert "official_api" in report.active_capabilities
    assert report.auth.valid is True
    assert report.supported_tools == PHASE3_TOOLS


def test_official_api_auth_failure_marks_unavailable() -> None:
    manager = CapabilityManager(Settings(medium_token="secret-token"))
    manager.mark_official_api_auth_failure("Invalid token")
    report = manager.get_report(force_refresh=True)
    assert report.auth.valid is False
    assert any("Invalid token" in (w or "") for w in report.warnings)
    assert any("not currently available" in lim for lim in report.limitations)
    assert "official_api" not in report.active_capabilities
