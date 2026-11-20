"""CLI entrypoint for the Medium MCP server."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence

from . import __version__
from .config import DEFAULT_TRANSPORT, Settings, build_arg_parser, load_settings
from .logging import configure_logging, get_logger
from .server import create_server


def _run_stdio(mcp: object, settings: Settings) -> int:
    logger = get_logger(__name__)
    logger.info("Starting Medium MCP server", extra={"mode": "serve", "transport": "stdio"})
    run = getattr(mcp, "run", None)
    if callable(run):
        # Try common signatures.
        try:
            run(transport="stdio")
            return 0
        except TypeError:
            pass
        try:
            run("stdio")
            return 0
        except TypeError:
            pass
        try:
            run()
            return 0
        except TypeError as exc:
            raise RuntimeError(
                "Unable to start stdio transport with installed MCP SDK API"
            ) from exc
    raise RuntimeError("Installed MCP server object does not expose a runnable stdio API")


def _run_streamable_http(mcp: object, settings: Settings) -> int:
    logger = get_logger(__name__)
    logger.info(
        "Starting Medium MCP server",
        extra={
            "mode": "serve",
            "transport": "streamable-http",
            "host": settings.http_host,
            "path": settings.http_path,
            "port": settings.http_port,
        },
    )

    host = settings.http_host
    port = settings.http_port
    path = settings.http_path

    # Preferred: built-in synchronous runner (mcp 2.x MCPServer.run / compatible APIs).
    run = getattr(mcp, "run", None)
    if callable(run):
        for kwargs in (
            {
                "transport": "streamable-http",
                "host": host,
                "port": port,
                "streamable_http_path": path,
            },
            {"transport": "streamable-http", "host": host, "port": port, "path": path},
            {"transport": "streamable-http", "host": host, "port": port},
            {
                "transport": "http",
                "host": host,
                "port": port,
                "streamable_http_path": path,
            },
            {"transport": "http", "host": host, "port": port, "path": path},
            {"transport": "http", "host": host, "port": port},
        ):
            try:
                run(**kwargs)
                return 0
            except TypeError:
                continue
            except Exception:
                # If the method exists but fails at runtime, let it propagate.
                raise

    # Async runner fallback (mcp 2.x).
    run_async = getattr(mcp, "run_streamable_http_async", None)
    if callable(run_async):
        import anyio

        async def _run_http(**kwargs: object) -> None:
            result = run_async(**kwargs)
            if result is not None:
                await result

        for kwargs in (
            {"host": host, "port": port, "streamable_http_path": path},
            {"host": host, "port": port},
        ):
            try:

                async def _go(_kwargs: dict[str, object] = kwargs) -> None:
                    await _run_http(**_kwargs)

                anyio.run(_go)
                return 0
            except TypeError:
                continue

    # Fallback: obtain ASGI app and run via uvicorn.
    app = None
    for app_attr in ("streamable_http_app", "http_app", "sse_app"):
        factory = getattr(mcp, app_attr, None)
        if callable(factory):
            try:
                app = factory()
                break
            except TypeError:
                try:
                    app = factory(path)
                    break
                except Exception:
                    continue
            except Exception:
                continue
    if app is None and hasattr(mcp, "_app"):
        app = mcp._app

    if app is not None:
        try:
            import uvicorn
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Streamable HTTP fallback requires 'uvicorn' and a compatible ASGI app."
            ) from exc
        uvicorn.run(app, host=host, port=port, log_level=settings.log_level.lower())
        return 0

    raise RuntimeError("Unable to start streamable-http transport with installed MCP SDK API")


def _doctor_output(settings: Settings, capability_manager: object) -> dict[str, object]:
    report = None
    try:
        get_report = getattr(capability_manager, "get_report", None)
        if callable(get_report):
            report = get_report(force_refresh=True).to_dict()
    except Exception as exc:
        report = {"error": f"Failed to compute capability report: {exc}"}

    checks: list[dict[str, object]] = []

    def add(status: str, name: str, message: str) -> None:
        checks.append({"status": status, "name": name, "message": message})

    add("ok", "config_loaded", "Configuration loaded with precedence CLI > env > defaults.")
    add("ok", "transport", f"Effective transport: {settings.transport}.")

    if settings.transport == "stdio":
        add(
            "ok",
            "stdio_logging",
            "Stdio mode: protocol on stdout; logs must be routed to stderr/file.",
        )
    else:
        if settings.http_host in {"127.0.0.1", "localhost", "::1"}:
            add(
                "ok",
                "http_bind",
                "Streamable HTTP bound to localhost-safe host "
                f"{settings.http_host}:{settings.http_port}{settings.http_path}.",
            )
        else:
            add(
                "warn",
                "http_bind",
                "Streamable HTTP is not bound to localhost. Use TLS/reverse-proxy auth and "
                "origin/DNS-rebinding protections; MVP has no built-in multi-tenant auth.",
            )
        add(
            "info",
            "http_auth",
            "MVP Streamable HTTP posture: localhost + deployment hooks; no built-in "
            "shared bearer auth enforcement.",
        )

    if settings.medium_token_configured:
        add(
            "info",
            "medium_token",
            "MEDIUM_TOKEN is configured (redacted). Official API capability is opt-in "
            "and will be verified on probe/use; availability may vary.",
        )
    else:
        add(
            "ok",
            "medium_token",
            "No MEDIUM_TOKEN configured. Export/prepare and public feed_read modes "
            "remain available.",
        )

    if settings.medium_enable_unofficial:
        add(
            "warn",
            "unofficial_mode",
            "MEDIUM_ENABLE_UNOFFICIAL is set, but unofficial automation is not "
            "implemented in this MVP.",
        )

    return {
        "ok": True,
        "version": __version__,
        "settings": settings.redacted_dict(),
        "capabilities": report,
        "checks": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    parser = build_arg_parser()
    args = parser.parse_args(argv_list)

    if getattr(args, "version", False):
        print(__version__)
        return 0

    settings, args = load_settings(argv_list)
    command = getattr(args, "command", None) or "serve"
    # argparse with shared options on both parser and subparser can be quirky; normalize.
    if command not in {"serve", "doctor"}:
        command = "serve"

    # Default to stdio when unspecified.
    if not settings.transport:
        settings.transport = DEFAULT_TRANSPORT

    configure_logging(settings)
    logger = get_logger(__name__)

    try:
        mcp, capability_manager = create_server(settings)

        if command == "doctor":
            payload = _doctor_output(settings, capability_manager)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        if settings.transport == "stdio":
            return _run_stdio(mcp, settings)
        if settings.transport == "streamable-http":
            return _run_streamable_http(mcp, settings)
        print(
            f"Unsupported transport: {settings.transport}. Expected 'stdio' or 'streamable-http'.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        logger.info("Server interrupted, shutting down")
        return 130
    except Exception as exc:
        logger.exception("Failed to start or run Medium MCP server: %s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
