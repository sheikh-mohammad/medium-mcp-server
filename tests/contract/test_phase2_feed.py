from __future__ import annotations

import asyncio
from pathlib import Path

from medium_mcp_server.adapters import feeds
from medium_mcp_server.config import load_settings
from medium_mcp_server.server import create_server

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _FakeStreamResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self._text = text
        self.encoding = "utf-8"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_bytes(self):
        yield self._text.encode("utf-8")


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url):
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _structured(result):
    if isinstance(result, tuple) and len(result) == 2:
        return result[1]
    if hasattr(result, "structured_content"):
        sc = getattr(result, "structured_content", None)
        if isinstance(sc, dict):
            return sc
    if isinstance(result, dict):
        return result
    return None


def test_read_public_feed_tool_contract(monkeypatch) -> None:
    def _client_ctor(*args, **kwargs):
        return _FakeClient([_FakeStreamResponse(200, read_fixture("sample_rss.xml"))])

    monkeypatch.setattr(feeds.httpx, "Client", _client_ctor)

    settings, _ = load_settings([])
    mcp, _ = create_server(settings)
    result = _structured(
        asyncio.run(
            mcp.call_tool(
                "read_public_feed",
                {"source": "@alice", "limit": 5, "include_content": False},
            )
        )
    )
    assert result is not None
    assert result["ok"] is True
    assert result["mode"] == "feed_read"
    assert result["data"]["source"]["type"] == "user"
    assert isinstance(result["data"]["items"], list)
    assert len(result["data"]["items"]) == 2
    assert "fetched_at" in result["data"]
    assert "warnings" in result["data"]


def test_read_public_feed_tool_validation_contract(monkeypatch) -> None:
    settings, _ = load_settings([])
    mcp, _ = create_server(settings)
    result = _structured(asyncio.run(mcp.call_tool("read_public_feed", {"source": ""})))
    assert result is not None
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
