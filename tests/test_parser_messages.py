"""Parser'ın Anthropic API'sine ne gönderdiğini doğrula (gerçek çağrı yapmadan).

Burası kritik: prompt caching, image block formatı, system prompt yapısı
yanlışsa cache miss olur ve maliyet patlar. Yapısal doğrulama.
"""

from datetime import datetime, timezone

import anthropic
import pytest

from mmxm.models import RawPost
from mmxm.parsing.parser import _build_messages, parse_post
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


def test_build_messages_no_images():
    msgs = _build_messages(_sample_post(), include_images=True)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    content = msgs[0]["content"]
    assert len(content) == 1  # sadece text
    assert content[0]["type"] == "text"


def test_build_messages_with_images():
    urls = [
        "https://pbs.twimg.com/media/HIIN1iEXUAATZTW.jpg",
        "https://pbs.twimg.com/media/ANOTHER.png",
    ]
    msgs = _build_messages(_sample_post(urls), include_images=True)
    content = msgs[0]["content"]
    assert len(content) == 3  # 1 text + 2 image
    assert content[1] == {
        "type": "image",
        "source": {"type": "url", "url": urls[0]},
    }


def test_build_messages_skips_video_thumbnails():
    """Video thumbnail'lar grafik içermiyor — atlanmalı."""
    urls = [
        "https://pbs.twimg.com/media/RealChart.jpg",
        "https://pbs.twimg.com/amplify_video_thumb/12345/img/thumb.jpg",
        "https://pbs.twimg.com/tweet_video_thumb/AB12.jpg",
    ]
    msgs = _build_messages(_sample_post(urls), include_images=True)
    content = msgs[0]["content"]
    # 1 text + 1 real image (videolar atlandı)
    assert len(content) == 2
    assert content[1]["source"]["url"] == urls[0]


def test_no_images_flag_drops_all():
    msgs = _build_messages(_sample_post(["https://pbs.twimg.com/media/A.jpg"]), include_images=False)
    assert len(msgs[0]["content"]) == 1
    assert msgs[0]["content"][0]["type"] == "text"


def test_system_prompt_is_long_enough_for_caching():
    """Opus 4.7 prompt caching minimum 4096 token. Tahminen 1 token ≈ 3-4 karakter."""
    # Yaklaşık alt sınır: ~12K karakter ≈ ~3-4K token. Türkçe biraz daha yoğun olabilir.
    assert len(SYSTEM_PROMPT) >= 4000, (
        f"system prompt çok kısa ({len(SYSTEM_PROMPT)} chars) — caching çalışmayabilir"
    )


class _FakeMessages:
    def __init__(self, parsed: ParsedPost):
        self.parsed = parsed
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)

        class _Usage:
            input_tokens = 100
            output_tokens = 50
            cache_read_input_tokens = 0
            cache_creation_input_tokens = 3000

        class _Response:
            usage = _Usage()
            parsed_output = self.parsed

        return _Response()


class _FakeClient:
    def __init__(self, parsed: ParsedPost):
        self.messages = _FakeMessages(parsed)


@pytest.mark.asyncio
async def test_parse_post_forwards_caching_and_thinking_config():
    expected = ParsedPost(
        post_type=PostType.TRADE_CALL,
        language="tr",
        rationale="ok",
        confidence=0.9,
    )
    client = _FakeClient(expected)
    result = await parse_post(_sample_post(), client)  # type: ignore[arg-type]
    assert result is expected

    call = client.messages.calls[0]
    # System prompt cache_control'lu mu?
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    # Adaptive thinking + effort=high?
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "high"}
    # Pydantic output_format gitti mi?
    assert call["output_format"] is ParsedPost
    # Model default
    assert call["model"] == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_parse_post_raises_on_api_error():
    class _ErrorMessages:
        async def parse(self, **kwargs):
            raise anthropic.APIError(
                "boom", request=None, body=None  # type: ignore[arg-type]
            )

    class _ErrClient:
        messages = _ErrorMessages()

    from mmxm.parsing.parser import ParseError

    with pytest.raises(ParseError):
        await parse_post(_sample_post(), _ErrClient())  # type: ignore[arg-type]
