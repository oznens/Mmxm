"""NitterScrapeBackend için httpx mocklu integration testi."""

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from mmxm.scraping.x_scrape import NitterScrapeBackend, NitterUnavailable

FIXTURE = (Path(__file__).parent / "fixtures" / "nitter_sample.xml").read_text(encoding="utf-8")


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetches_and_filters_by_since():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FIXTURE)

    backend = NitterScrapeBackend(instances=["https://nitter.test"])
    backend._client = httpx.AsyncClient(transport=_mock_transport(handler))

    since = datetime(2024, 4, 30, tzinfo=timezone.utc)
    posts = [
        p
        async for p in backend.fetch_user_posts("example_trader", since=since)
    ]
    await backend.close()

    # 1 May (geçer) ve 29 Apr (since öncesi, atlanır). Reply ve RT zaten filtreli.
    assert [p.post_id for p in posts] == ["1785000000000000001"]


@pytest.mark.asyncio
async def test_falls_back_to_second_instance():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        calls.append(host)
        if host == "broken.test":
            return httpx.Response(503, text="bad gateway")
        return httpx.Response(200, text=FIXTURE)

    backend = NitterScrapeBackend(
        instances=["https://broken.test", "https://nitter.ok"]
    )
    backend._client = httpx.AsyncClient(transport=_mock_transport(handler))
    posts = [p async for p in backend.fetch_user_posts("example_trader")]
    await backend.close()

    assert calls == ["broken.test", "nitter.ok"]
    assert len(posts) == 2


@pytest.mark.asyncio
async def test_raises_when_all_instances_fail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limit")

    backend = NitterScrapeBackend(instances=["https://a.test", "https://b.test"])
    backend._client = httpx.AsyncClient(transport=_mock_transport(handler))

    with pytest.raises(NitterUnavailable):
        async for _ in backend.fetch_user_posts("example_trader"):
            pass
    await backend.close()


@pytest.mark.asyncio
async def test_limit_is_respected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FIXTURE)

    backend = NitterScrapeBackend(instances=["https://nitter.test"])
    backend._client = httpx.AsyncClient(transport=_mock_transport(handler))
    posts = [
        p async for p in backend.fetch_user_posts("example_trader", limit=1)
    ]
    await backend.close()
    assert len(posts) == 1
