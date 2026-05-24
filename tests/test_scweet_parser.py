"""Scweet TweetRecord dict -> RawPost dönüşümünün saf testi."""

from datetime import datetime, timezone

from mmxm.scraping.x_scrape import _parse_twitter_timestamp, scweet_dict_to_raw_post


def _sample(tweet_id: str = "1700000000000000001", **overrides) -> dict:
    base = {
        "tweet_id": tweet_id,
        "user": {"screen_name": "example_trader", "name": "Example"},
        "timestamp": "Wed May 01 12:00:00 +0000 2024",
        "text": "BTC long entry 60000 SL 58500 TP 64000",
        "embedded_text": None,
        "likes": 42,
        "retweets": 5,
        "comments": 3,
        "media": {"image_links": []},
        "tweet_url": f"https://x.com/example_trader/status/{tweet_id}",
        "raw": {"legacy": {}},
    }
    base.update(overrides)
    return base


def test_basic_mapping():
    post = scweet_dict_to_raw_post(_sample(), "example_trader")
    assert post is not None
    assert post.post_id == "1700000000000000001"
    assert post.handle == "example_trader"
    assert "BTC long" in post.text
    assert post.created_at == datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    assert post.url and "status/1700000000000000001" in post.url
    assert post.is_reply is False
    assert post.raw == {"likes": 42, "retweets": 5, "comments": 3}


def test_reply_detection_via_legacy():
    d = _sample(raw={"legacy": {"in_reply_to_status_id_str": "999"}})
    post = scweet_dict_to_raw_post(d, "example_trader")
    assert post is not None
    assert post.is_reply is True
    assert post.in_reply_to == "999"


def test_falls_back_to_embedded_text():
    d = _sample(text="", embedded_text="quoted body")
    post = scweet_dict_to_raw_post(d, "example_trader")
    assert post is not None
    assert post.text == "quoted body"


def test_missing_tweet_id_returns_none():
    d = _sample()
    d.pop("tweet_id")
    assert scweet_dict_to_raw_post(d, "example_trader") is None


def test_missing_timestamp_returns_none():
    assert scweet_dict_to_raw_post(_sample(timestamp=None), "example_trader") is None


def test_handle_lowercased_and_at_stripped():
    d = _sample()
    d["user"]["screen_name"] = "@Example_Trader"
    post = scweet_dict_to_raw_post(d, "ignored")
    assert post is not None
    assert post.handle == "example_trader"


def test_media_urls_propagated():
    d = _sample(media={"image_links": ["https://pbs.twimg.com/media/abc.jpg"]})
    post = scweet_dict_to_raw_post(d, "example_trader")
    assert post is not None
    assert post.media_urls == ["https://pbs.twimg.com/media/abc.jpg"]


def test_parse_twitter_timestamp_variants():
    assert _parse_twitter_timestamp("Wed May 01 12:00:00 +0000 2024") == datetime(
        2024, 5, 1, 12, 0, tzinfo=timezone.utc
    )
    assert _parse_twitter_timestamp("2024-05-01T12:00:00Z") == datetime(
        2024, 5, 1, 12, 0, tzinfo=timezone.utc
    )
    assert _parse_twitter_timestamp("") is None
    assert _parse_twitter_timestamp(None) is None  # type: ignore[arg-type]
    assert _parse_twitter_timestamp("garbage") is None
