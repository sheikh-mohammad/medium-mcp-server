from __future__ import annotations

from medium_mcp_server.config import (
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PATH,
    DEFAULT_HTTP_PORT,
    load_settings,
)


def test_load_settings_defaults() -> None:
    settings, args = load_settings([])
    assert settings.transport == "stdio"
    assert settings.http_host == DEFAULT_HTTP_HOST
    assert settings.http_port == DEFAULT_HTTP_PORT
    assert settings.http_path == DEFAULT_HTTP_PATH
    assert settings.log_level == "INFO"
    assert settings.medium_token is None
    assert settings.medium_enable_unofficial is False
    assert args.command is None or args.command in {None, "serve", "doctor"}


def test_cli_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.setenv("MCP_HTTP_PORT", "9000")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    monkeypatch.setenv("MEDIUM_TOKEN", "secret-token")
    settings, _ = load_settings(
        [
            "serve",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--path",
            "api/mcp",
            "--log-level",
            "debug",
        ]
    )
    assert settings.transport == "streamable-http"
    assert settings.http_host == "127.0.0.1"
    assert settings.http_port == 8765
    assert settings.http_path == "/api/mcp"
    assert settings.log_level == "DEBUG"
    assert settings.medium_token == "secret-token"
    redacted = settings.redacted_dict()
    assert redacted["medium_token"] == "***redacted***"


def test_doctor_command_parsing(monkeypatch) -> None:
    monkeypatch.delenv("MEDIUM_TOKEN", raising=False)
    settings, args = load_settings(["doctor", "--transport", "streamable-http"])
    assert args.command == "doctor"
    assert settings.transport == "streamable-http"
