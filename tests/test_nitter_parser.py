"""Nitter RSS parser'ın network'süz testi."""

from datetime import datetime, timezone
from pathlib import Path

from mmxm.scraping.x_scrape import parse_nitter_rss

FIXTURE = Path(__file__).parent / "fixtures" / "nitter_sample.xml"


def _load() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_filters_retweets_and_replies_by_default():
    posts = parse_nitter_rss(_load(), requested_handle="example_trader")
    assert len(posts) == 2  # 4 item: 1 reply + 1 retweet atılır
    ids = [p.post_id for p in posts]
    assert ids == ["1785000000000000001", "1785000000000000004"]


def test_include_replies():
    posts = parse_nitter_rss(
        _load(), requested_handle="example_trader", include_replies=True
    )
    # Retweet hâlâ atılır (creator farklı), ama reply gelir → 3
    assert len(posts) == 3
    assert any(p.is_reply for p in posts)


def test_handle_case_insensitive():
    posts = parse_nitter_rss(_load(), requested_handle="@Example_Trader")
    assert len(posts) == 2
    assert all(p.handle == "example_trader" for p in posts)


def test_strips_html_and_parses_pubdate():
    posts = parse_nitter_rss(_load(), requested_handle="example_trader")
    p = posts[0]
    assert p.created_at == datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    assert "<p>" not in p.text
    assert "RSI bullish divergence" in p.text
    assert p.url and "status/1785000000000000001" in p.url


def test_extracts_status_id_from_link():
    posts = parse_nitter_rss(_load(), requested_handle="example_trader")
    assert posts[0].post_id == "1785000000000000001"


def test_empty_or_malformed_returns_empty():
    posts = parse_nitter_rss(
        '<?xml version="1.0"?><rss><channel></channel></rss>',
        requested_handle="x",
    )
    assert posts == []
