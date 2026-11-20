from __future__ import annotations

from pathlib import Path

from medium_mcp_server.adapters import feeds

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_normalize_feed_source_variants() -> None:
    cases = [
        ("@alice", None, "user", "https://medium.com/feed/@alice"),
        ("alice", "user", "user", "https://medium.com/feed/@alice"),
        ("https://medium.com/@alice", "user", "user", "https://medium.com/feed/@alice"),
        ("my-publication", "publication", "publication", "https://medium.com/feed/my-publication"),
        ("python", "tag", "tag", "https://medium.com/feed/tag/python"),
        ("https://medium.com/feed/tag/python", "url", "url", "https://medium.com/feed/tag/python"),
        ("https://medium.com/feed/@alice", None, "url", "https://medium.com/feed/@alice"),
    ]
    for source, source_type, expected_type, expected_url in cases:
        normalized = feeds.normalize_feed_source(source, source_type)
        assert not isinstance(normalized, feeds.ToolError)
        assert normalized.source_type == expected_type
        assert normalized.feed_url == expected_url


def test_normalize_feed_source_validation_errors() -> None:
    for source, source_type in [
        ("", None),
        ("   ", "user"),
        ("alice", "invalid"),
        ("not-a-url", "url"),
    ]:
        err = feeds.normalize_feed_source(source, source_type)
        assert isinstance(err, feeds.ToolError)
        assert err.code.value == "validation_error"


def test_bounded_limit() -> None:
    assert feeds._bounded_limit(None) == (feeds.DEFAULT_LIMIT, [])
    assert feeds._bounded_limit(5) == (5, [])
    capped = feeds._bounded_limit(999)
    assert capped[0] == feeds.MAX_LIMIT
    assert capped[1]
    assert isinstance(feeds._bounded_limit(0), feeds.ToolError)
    assert isinstance(feeds._bounded_limit("x"), feeds.ToolError)


def test_parse_feed_items_from_fixture() -> None:
    warnings: list[str] = []
    items = feeds._parse_feed_items(
        read_fixture("sample_rss.xml"),
        limit=10,
        include_content=False,
        warnings=warnings,
    )
    assert len(items) == 2
    assert items[0]["id"] == "https://medium.com/p/abc123"
    assert items[0]["title"] == "First Post"
    assert items[0]["link"] == "https://medium.com/@sample/first-post-abc123"
    assert items[0]["author"] == "Sample Author"
    assert "python" in (items[0]["tags"] or [])
    assert "mcp" in (items[0]["tags"] or [])
    assert items[0]["summary"] is not None
    assert items[0]["content"] is None  # include_content=False
    assert items[1]["title"] == "Second Post"


def test_parse_feed_items_with_content_and_limit() -> None:
    warnings: list[str] = []
    items = feeds._parse_feed_items(
        read_fixture("sample_rss.xml"),
        limit=1,
        include_content=True,
        warnings=warnings,
    )
    assert len(items) == 1
    assert items[0]["content"] is not None
    assert "Full content" in (items[0]["content"] or "") or "Summary" in (items[0]["content"] or "")
    assert any("returning first 1" in w.lower() for w in warnings)


def test_parse_malformed_feed_warns() -> None:
    warnings: list[str] = []
    items = feeds._parse_feed_items(
        read_fixture("malformed_feed.xml"),
        limit=10,
        include_content=True,
        warnings=warnings,
    )
    # best-effort: may parse partially or yield empty items, but must warn/fail gracefully
    assert isinstance(items, list)
    assert warnings  # bozo/malformed warning or related warning expected
