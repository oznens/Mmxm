"""Parser'ın Gemini API'sine ne gönderdiğini doğrula (gerçek çağrı yapmadan).

Image fetch + content assembly + config forwarding yapısını kontrol eder.
"""

from datetime import datetime, timezone

import httpx
import pytest

from mmxm.models import RawPost
from mmxm.parsing.parser import (
    RateLimiter,
    _build_contents,
    _fetch_image,
    parse_post,
)
from mmxm.parsing.prompts import SYSTEM_PROMPT, build_user_message
from mmxm.parsing.schema import ParsedPost, PostType


def _sample_post(media_urls: list[str] | None = None) -> RawPost:
    return RawPost(
        post_id="1700000000000000001",
        handle="example_trader",
        text="BTC için 4h FVG geri test edildi, long açtım. Entry 60000, SL 58500, TP 64000.",
        created_at=datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc),
        url="https://x.com/example_trader/status/1700000000000000001",
        media_urls=media_urls or [],
    )


def test_user_message_contains_metadata_and_text():
    post = _sample_post()
    msg = build_user_message(post)
    assert "@example_trader" in msg
    assert "BTC için" in msg
    assert "2024-05-01" in msg
    assert "POST METADATA" in msg


def test_system_prompt_includes_ict_ontology_and_examples():
    """Prompt'un kritik bölümleri yerli yerinde mi."""
    assert "FVG" in SYSTEM_PROMPT
    assert "turtle_soup" in SYSTEM_PROMPT
    assert "amd" in SYSTEM_PROMPT
    assert "post_type" in SYSTEM_PROMPT
    # 5 worked example
    assert "Örnek 1" in SYSTEM_PROMPT
    assert "Örnek 5" in SYSTEM_PROMPT


# --- _fetch_image (httpx MockTransport) ---


def _img_transport(status: int = 200, content: bytes = b"\x89PNG fake", ctype: str = "image/png"):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content, headers={"content-type": ctype})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_image_returns_bytes_and_mime():
    async with httpx.AsyncClient(transport=_img_transport()) as c:
        result = await _fetch_image("https://pbs.twimg.com/media/x.png", c)
    assert result is not None
    data, mime = result
    assert mime == "image/png"
    assert data == b"\x89PNG fake"


@pytest.mark.asyncio
async def test_fetch_image_returns_none_on_404():
    async with httpx.AsyncClient(transport=_img_transport(status=404)) as c:
        result = await _fetch_image("https://pbs.twimg.com/media/x.png", c)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_image_returns_none_on_non_image_ctype():
    async with httpx.AsyncClient(transport=_img_transport(ctype="text/html")) as c:
        result = await _fetch_image("https://pbs.twimg.com/media/x.png", c)
    assert result is None


# --- _build_contents ---


@pytest.mark.asyncio
async def test_build_contents_no_images():
    async with httpx.AsyncClient(transport=_img_transport()) as c:
        parts = await _build_contents(_sample_post(), c, include_images=True)
    assert len(parts) == 1
    assert isinstance(parts[0], str)
    assert "@example_trader" in parts[0]


@pytest.mark.asyncio
async def test_build_contents_with_images_downloads_and_inlines():
    urls = [
        "https://pbs.twimg.com/media/A.jpg",
        "https://pbs.twimg.com/media/B.jpg",
    ]
    async with httpx.AsyncClient(transport=_img_transport()) as c:
        parts = await _build_contents(_sample_post(urls), c, include_images=True)
    assert len(parts) == 3  # 1 text + 2 image Part
    # parts[1], parts[2] should be Part with inline_data
    for p in parts[1:]:
        assert hasattr(p, "inline_data") or hasattr(p, "model_dump")


@pytest.mark.asyncio
async def test_build_contents_skips_video_thumbnails():
    urls = [
        "https://pbs.twimg.com/media/Real.jpg",
        "https://pbs.twimg.com/amplify_video_thumb/12345/img/thumb.jpg",
        "https://pbs.twimg.com/tweet_video_thumb/AB.jpg",
    ]
    async with httpx.AsyncClient(transport=_img_transport()) as c:
        parts = await _build_contents(_sample_post(urls), c, include_images=True)
    assert len(parts) == 2  # 1 text + 1 real image


@pytest.mark.asyncio
async def test_build_contents_skips_failed_image_downloads():
    """200 OK ama text/html — atlanmalı."""
    urls = ["https://pbs.twimg.com/media/Broken.jpg"]
    async with httpx.AsyncClient(
        transport=_img_transport(ctype="text/html")
    ) as c:
        parts = await _build_contents(_sample_post(urls), c, include_images=True)
    assert len(parts) == 1


@pytest.mark.asyncio
async def test_no_images_flag_drops_all():
    async with httpx.AsyncClient(transport=_img_transport()) as c:
        parts = await _build_contents(
            _sample_post(["https://pbs.twimg.com/media/A.jpg"]),
            c,
            include_images=False,
        )
    assert len(parts) == 1
    assert isinstance(parts[0], str)


# --- RateLimiter ---


@pytest.mark.asyncio
async def test_rate_limiter_enforces_interval():
    import time

    limiter = RateLimiter(requests_per_minute=600)  # 10/sec = 0.1s aralık
    t0 = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    elapsed = time.monotonic() - t0
    # 3 acquire → 2 interval bekler ≈ 0.2s minimum
    assert elapsed >= 0.18


# --- parse_post end-to-end with mocked client ---


class _FakeAioModels:
    def __init__(self, parsed: ParsedPost):
        self.parsed = parsed
        self.calls: list[dict] = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})

        class _Usage:
            prompt_token_count = 3000
            thoughts_token_count = 500
            candidates_token_count = 200

        class _Response:
            usage_metadata = _Usage()
            parsed = self.parsed
            text = '{"ok": true}'

        return _Response()


class _FakeAio:
    def __init__(self, parsed: ParsedPost):
        self.models = _FakeAioModels(parsed)


class _FakeClient:
    def __init__(self, parsed: ParsedPost):
        self.aio = _FakeAio(parsed)


@pytest.mark.asyncio
async def test_parse_post_forwards_config():
    expected = ParsedPost(
        post_type=PostType.TRADE_CALL,
        language="tr",
        rationale="ok",
        confidence=0.9,
    )
    client = _FakeClient(expected)
    async with httpx.AsyncClient(transport=_img_transport()) as http:
        result = await parse_post(_sample_post(), client, http_client=http)  # type: ignore[arg-type]
    assert result is expected

    call = client.aio.models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    cfg = call["config"]
    assert cfg.system_instruction == SYSTEM_PROMPT
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema is ParsedPost
    assert cfg.thinking_config.thinking_budget == 1024


@pytest.mark.asyncio
async def test_parse_post_raises_when_schema_validation_fails():
    """parsed=None → ParseError."""
    from mmxm.parsing.parser import ParseError

    client = _FakeClient(None)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=_img_transport()) as http:
        with pytest.raises(ParseError):
            await parse_post(_sample_post(), client, http_client=http)  # type: ignore[arg-type]
