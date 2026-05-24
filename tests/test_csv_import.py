"""TwExportly CSV import testleri."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mmxm.scraping.csv_import import (
    _clean_id,
    _clean_text,
    _parse_ts,
    _split_media,
    iter_csv_posts,
)

SAMPLE_CSV = """﻿tweet_id,text,language,type,bookmark_count,favorite_count,retweet_count,reply_count,view_count,created_at,client,hashtags,urls,media_type,media_urls
'2057194905642901575',Tweet metni link sonda https://t.co/abc,tr,Tweet,0,7,0,1,1189,2026-05-20 23:21:00,client,,,photo,https://pbs.twimg.com/media/A.jpg
'2056398862026248376',@usr Reply foto'lu,tr,Reply,0,23,1,0,1035,2026-05-18 18:37:49,client,,,photo,"https://pbs.twimg.com/media/B.jpg,https://pbs.twimg.com/media/C.jpg"
'2050000000000000001',@usr text-only reply,tr,Reply,0,5,0,0,100,2026-05-15 12:00:00,client,,,,
'2049000000000000002',RT @x: bir şey,en,Retweet,0,0,5,0,500,2026-05-10 10:00:00,client,,,photo,https://pbs.twimg.com/media/D.jpg
"""


def _write(tmp: Path, text: str) -> Path:
    p = tmp / "in.csv"
    p.write_text(text, encoding="utf-8")
    return p


# -- helper unit tests --


def test_clean_id_strips_quotes():
    assert _clean_id("'12345'") == "12345"
    assert _clean_id('"12345"') == "12345"
    assert _clean_id("12345") == "12345"
    assert _clean_id("not-a-number") is None


def test_split_media_handles_comma_list():
    assert _split_media("https://a.jpg,https://b.jpg") == ["https://a.jpg", "https://b.jpg"]
    assert _split_media("") == []
    assert _split_media("https://a.jpg") == ["https://a.jpg"]


def test_parse_ts_returns_utc():
    dt = _parse_ts("2026-05-20 23:21:00")
    assert dt == datetime(2026, 5, 20, 23, 21, 0, tzinfo=timezone.utc)
    assert _parse_ts("garbage") is None


def test_clean_text_strips_trailing_tco():
    assert _clean_text("hello https://t.co/abc") == "hello"
    # Sadece sondaki temizlenir, ortadaki kalır
    assert _clean_text("a https://t.co/x b") == "a https://t.co/x b"


# -- iterator filter tests --


def test_default_filters_keep_tweet_and_reply_with_media(tmp_path: Path):
    csv = _write(tmp_path, SAMPLE_CSV)
    posts = list(iter_csv_posts(csv, handle="@trader"))
    ids = [p.post_id for p in posts]
    assert "2057194905642901575" in ids  # Tweet
    assert "2056398862026248376" in ids  # Reply + photo
    assert "2050000000000000001" not in ids  # Reply text-only — atlanır
    assert "2049000000000000002" not in ids  # Retweet — atlanır


def test_include_text_only_replies(tmp_path: Path):
    csv = _write(tmp_path, SAMPLE_CSV)
    posts = list(iter_csv_posts(csv, handle="trader", include_text_only_replies=True))
    ids = {p.post_id for p in posts}
    assert "2050000000000000001" in ids


def test_include_retweets(tmp_path: Path):
    csv = _write(tmp_path, SAMPLE_CSV)
    posts = list(iter_csv_posts(csv, handle="trader", include_retweets=True))
    ids = {p.post_id for p in posts}
    assert "2049000000000000002" in ids


def test_post_fields_populated_correctly(tmp_path: Path):
    csv = _write(tmp_path, SAMPLE_CSV)
    posts = list(iter_csv_posts(csv, handle="@TRADER"))
    by_id = {p.post_id: p for p in posts}

    tweet = by_id["2057194905642901575"]
    assert tweet.handle == "trader"  # @ stripped, lowercased
    assert tweet.is_reply is False
    assert tweet.text == "Tweet metni link sonda"  # trailing t.co stripped
    assert tweet.media_urls == ["https://pbs.twimg.com/media/A.jpg"]
    assert tweet.created_at == datetime(2026, 5, 20, 23, 21, 0, tzinfo=timezone.utc)
    assert tweet.url == "https://x.com/trader/status/2057194905642901575"

    reply = by_id["2056398862026248376"]
    assert reply.is_reply is True
    assert len(reply.media_urls) == 2  # multi-media virgülle ayrılmış
