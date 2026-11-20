from __future__ import annotations

from pathlib import Path

import httpx

from medium_mcp_server.adapters import feeds

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _FakeStreamResponse:
    def __init__(self, status_code: int, text: str = "", chunks: list[bytes] | None = None):
        self.status_code = status_code
        self._text = text
        self._chunks = chunks
        self.encoding = "utf-8"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_bytes(self):
        if self._chunks is not None:
            yield from self._chunks
        else:
            yield self._text.encode("utf-8")


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url):
        self.calls.append((method, url))
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _patch_client(monkeypatch, responses):
    fake = _FakeClient(responses)

    def _client_ctor(*args, **kwargs):
        return fake

    monkeypatch.setattr(feeds.httpx, "Client", _client_ctor)
    return fake


def test_read_public_feed_success_user_source(monkeypatch) -> None:
    fake = _patch_client(
        monkeypatch,
        [_FakeStreamResponse(200, read_fixture("sample_rss.xml"))],
    )
    result = feeds.read_public_feed(source="@alice", include_content=False, limit=10)
    assert result["ok"] is True
    assert result["mode"] == "feed_read"
    assert result["data"]["source"]["type"] == "user"
    assert result["data"]["source"]["feed_url"] == "https://medium.com/feed/@alice"
    assert len(result["data"]["items"]) == 2
    assert result["data"]["items"][0]["title"] == "First Post"
    assert "fetched_at" in result["data"]
    assert fake.calls and fake.calls[0][0] == "GET"


def test_read_public_feed_limit_capped_and_content_included(monkeypatch) -> None:
    _patch_client(monkeypatch, [_FakeStreamResponse(200, read_fixture("sample_rss.xml"))])
    result = feeds.read_public_feed(source="alice", limit=999, include_content=True)
    assert result["ok"] is True
    assert any("capped" in w.lower() for w in result["warnings"])
    assert len(result["data"]["items"]) <= feeds.MAX_LIMIT
    assert result["data"]["items"][0]["content"] is not None


def test_read_public_feed_not_found(monkeypatch) -> None:
    _patch_client(monkeypatch, [_FakeStreamResponse(404, "not found")])
    result = feeds.read_public_feed(source="https://medium.com/feed/@missing", source_type="url")
    assert result["ok"] is False
    assert result["error"]["code"] == "unavailable"


def test_read_public_feed_rate_limited(monkeypatch) -> None:
    _patch_client(monkeypatch, [_FakeStreamResponse(429, "rate limited")])
    result = feeds.read_public_feed(source="alice")
    assert result["ok"] is False
    assert result["error"]["code"] == "rate_limited"


def test_read_public_feed_timeout_with_retry(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(feeds.time, "sleep", lambda s: sleeps.append(s))
    _patch_client(
        monkeypatch,
        [httpx.TimeoutException("timeout"), httpx.TimeoutException("timeout")],
    )
    result = feeds.read_public_feed(source="alice")
    assert result["ok"] is False
    assert result["error"]["code"] == "timeout"
    assert sleeps  # retried before failing


def test_read_public_feed_transient_upstream_then_success(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(feeds.time, "sleep", lambda s: sleeps.append(s))
    _patch_client(
        monkeypatch,
        [
            _FakeStreamResponse(503, "unavailable"),
            _FakeStreamResponse(200, read_fixture("sample_rss.xml")),
        ],
    )
    result = feeds.read_public_feed(source="alice")
    assert result["ok"] is True
    assert len(result["data"]["items"]) == 2
    assert sleeps


def test_read_public_feed_malformed_feed_is_best_effort(monkeypatch) -> None:
    _patch_client(monkeypatch, [_FakeStreamResponse(200, read_fixture("malformed_feed.xml"))])
    result = feeds.read_public_feed(source="alice")
    # best-effort: should not crash; may be ok with warnings/items or unavailable-ish parse result
    assert result["ok"] is True
    assert result["mode"] == "feed_read"
    assert "warnings" in result["data"]
    assert result["data"]["warnings"]


def test_read_public_feed_validation_error() -> None:
    result = feeds.read_public_feed(source="", source_type="user")
    assert result["ok"] is False
    assert result["error"]["code"] == "validation_error"
