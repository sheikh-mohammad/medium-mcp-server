"""Runtime configuration for the Medium MCP server."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

TransportName = Literal["stdio", "streamable-http"]

DEFAULT_TRANSPORT: TransportName = "stdio"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8000
DEFAULT_HTTP_PATH = "/mcp"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_MEDIUM_API_BASE_URL = "https://api.medium.com/v1"

REDACTED = "***redacted***"


@dataclass(slots=True)
class Settings:
    transport: TransportName = DEFAULT_TRANSPORT
    http_host: str = DEFAULT_HTTP_HOST
    http_port: int = DEFAULT_HTTP_PORT
    http_path: str = DEFAULT_HTTP_PATH
    log_level: str = DEFAULT_LOG_LEVEL
    log_file: str | None = None
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    medium_token: str | None = None
    medium_api_base_url: str = DEFAULT_MEDIUM_API_BASE_URL
    medium_enable_unofficial: bool = False

    @property
    def medium_token_configured(self) -> bool:
        return bool(self.medium_token)

    def redacted_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["medium_token"] = REDACTED if self.medium_token else None
        return data


def _normalize_transport(value: str | None) -> TransportName:
    if value is None:
        return DEFAULT_TRANSPORT
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"stdio", "std"}:
        return "stdio"
    if normalized in {"streamable-http", "http", "streamable"}:
        return "streamable-http"
    raise ValueError(
        f"Unsupported transport '{value}'. Expected 'stdio' or 'streamable-http'."
    )


def _normalize_path(path: str) -> str:
    path = path.strip() or DEFAULT_HTTP_PATH
    if not path.startswith("/"):
        path = "/" + path
    return path


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_settings() -> Settings:
    """Load settings from environment variables only."""
    transport = _normalize_transport(os.getenv("MCP_TRANSPORT", DEFAULT_TRANSPORT))
    host = os.getenv("MCP_HTTP_HOST", DEFAULT_HTTP_HOST).strip() or DEFAULT_HTTP_HOST
    port_raw = os.getenv("MCP_HTTP_PORT")
    port = int(port_raw) if port_raw and port_raw.strip() else DEFAULT_HTTP_PORT
    path = _normalize_path(os.getenv("MCP_HTTP_PATH", DEFAULT_HTTP_PATH))
    log_level = (os.getenv("LOG_LEVEL") or DEFAULT_LOG_LEVEL).strip().upper() or DEFAULT_LOG_LEVEL
    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS")
    timeout = (
        float(timeout_raw)
        if timeout_raw and timeout_raw.strip()
        else DEFAULT_REQUEST_TIMEOUT_SECONDS
    )
    token = os.getenv("MEDIUM_TOKEN")
    token = token.strip() if token else None
    base_url = (
        os.getenv("MEDIUM_API_BASE_URL", DEFAULT_MEDIUM_API_BASE_URL).strip()
        or DEFAULT_MEDIUM_API_BASE_URL
    ).rstrip("/")
    unofficial = _parse_bool(os.getenv("MEDIUM_ENABLE_UNOFFICIAL"), default=False)
    log_file = os.getenv("MEDIUM_MCP_LOG_FILE")
    log_file = log_file.strip() if log_file else None
    return Settings(
        transport=transport,
        http_host=host,
        http_port=port,
        http_path=path,
        log_level=log_level,
        log_file=log_file,
        request_timeout_seconds=timeout,
        medium_token=token or None,
        medium_api_base_url=base_url,
        medium_enable_unofficial=unofficial,
    )


def build_arg_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog or "medium-mcp-server",
        description="Medium MCP server (capability-gated, draft-first).",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    def add_common_run_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--transport",
            choices=["stdio", "streamable-http"],
            help="MCP transport to run (default: env MCP_TRANSPORT or stdio).",
        )
        p.add_argument("--host", help="HTTP bind host (streamable-http only).")
        p.add_argument("--port", type=int, help="HTTP bind port (streamable-http only).")
        p.add_argument("--path", help="HTTP endpoint path (streamable-http only).")
        p.add_argument(
            "--log-level",
            help="Log level (DEBUG, INFO, WARNING, ERROR).",
        )
        p.add_argument("--log-file", help="Optional log file path (in addition to stderr).")
        p.add_argument(
            "--request-timeout-seconds",
            type=float,
            help="Upstream/feed request timeout in seconds.",
        )
        p.add_argument(
            "--medium-api-base-url",
            help="Override Medium API base URL (for testing/compat).",
        )

    serve = subparsers.add_parser("serve", help="Run the MCP server (default).")
    add_common_run_args(serve)

    doctor = subparsers.add_parser(
        "doctor", help="Print redacted effective configuration and diagnostics."
    )
    add_common_run_args(doctor)

    # Allow top-level run flags without explicit 'serve' for convenience.
    add_common_run_args(parser)
    return parser


def merge_cli_settings(base: Settings, args: argparse.Namespace) -> Settings:
    transport = base.transport
    if getattr(args, "transport", None):
        transport = _normalize_transport(args.transport)
    host = (getattr(args, "host", None) or base.http_host).strip() or DEFAULT_HTTP_HOST
    port = getattr(args, "port", None) or base.http_port
    path = _normalize_path(getattr(args, "path", None) or base.http_path)
    log_level = (
        (getattr(args, "log_level", None) or base.log_level).strip().upper() or DEFAULT_LOG_LEVEL
    )
    log_file = getattr(args, "log_file", None)
    if log_file is not None:
        log_file = log_file.strip() or None
    else:
        log_file = base.log_file
    timeout = getattr(args, "request_timeout_seconds", None) or base.request_timeout_seconds
    base_url = (
        (getattr(args, "medium_api_base_url", None) or base.medium_api_base_url).strip()
        or DEFAULT_MEDIUM_API_BASE_URL
    ).rstrip("/")
    return Settings(
        transport=transport,
        http_host=host,
        http_port=int(port),
        http_path=path,
        log_level=log_level,
        log_file=log_file,
        request_timeout_seconds=float(timeout),
        medium_token=base.medium_token,
        medium_api_base_url=base_url,
        medium_enable_unofficial=base.medium_enable_unofficial,
    )


def load_settings(argv: Sequence[str] | None = None) -> tuple[Settings, argparse.Namespace]:
    """Load settings with precedence: CLI args > env vars > defaults."""
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    settings = merge_cli_settings(env_settings(), args)
    return settings, args
