"""ScweetBackend integration testi — Scweet client'ı mock'lanır."""

from datetime import datetime, timezone

import pytest

from mmxm.scraping.x_scrape import ScweetBackend


class FakeScweetClient:
    """asearch'i mock'layan minimal client."""

    def __init__(self, tweets: list[dict]):
        self.tweets = tweets
        self.calls: list[dict] = []

    async def asearch(self, query: str = "", **kwargs):
        self.calls.append({"query": query, **kwargs})
        return self.tweets


def _tweet(tweet_id: str, ts: str = "Wed May 01 12:00:00 +0000 2024") -> dict:
    return {
        "tweet_id": tweet_id,
        "user": {"screen_name": "example_trader"},
        "timestamp": ts,
        "text": f"tweet {tweet_id}",
        "tweet_url": f"https://x.com/example_trader/status/{tweet_id}",
        "raw": {"legacy": {}},
        "media": {"image_links": []},
    }


@pytest.mark.asyncio
async def test_forwards_args_to_asearch():
    fake = FakeScweetClient([_tweet("1"), _tweet("2")])
    backend = ScweetBackend(client=fake)
    since = datetime(2024, 1, 1, tzinfo=timezone.utc)

    posts = [
        p
        async for p in backend.fetch_user_posts(
            "@Example_Trader",
            since=since,
            include_replies=False,
            limit=100,
        )
    ]

    assert len(posts) == 2
    assert fake.calls == [
        {
            "query": "",
            "from_users": ["example_trader"],
            "since": "2024-01-01",
            "limit": 100,
            "tweet_type": "exclude_replies",
        }
    ]


@pytest.mark.asyncio
async def test_include_replies_drops_filter():
    fake = FakeScweetClient([_tweet("1")])
    backend = ScweetBackend(client=fake)

    _ = [p async for p in backend.fetch_user_posts("example_trader", include_replies=True)]

    assert "tweet_type" not in fake.calls[0]


@pytest.mark.asyncio
async def test_skips_unparseable_records():
    fake = FakeScweetClient([
        _tweet("1"),
        {"tweet_id": None, "timestamp": "Wed May 01 12:00:00 +0000 2024"},  # bad id
        {"tweet_id": "3", "timestamp": "garbage"},  # bad ts
        _tweet("4"),
    ])
    backend = ScweetBackend(client=fake)
    posts = [p async for p in backend.fetch_user_posts("example_trader")]
    assert [p.post_id for p in posts] == ["1", "4"]


def test_requires_auth_token_or_client():
    with pytest.raises(ValueError, match="auth_token"):
        ScweetBackend()
