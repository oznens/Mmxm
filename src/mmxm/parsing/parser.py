"""LLM ile RawPost -> ParsedPost çevirisi.

Tasarım:
- Anthropic Python SDK `messages.parse()` ile structured output (pydantic validation).
- System prompt prompt-caching ile (cache_control ephemeral) — 418 tweet parse
  edileceğinden ciddi tasarruf.
- Adaptive thinking + effort=high (Opus 4.7 — ICT/SMC çıkarımı gibi karmaşık
  multimodal extraction için doğru ayar).
- Görseller URL block olarak gönderiliyor (Scweet'in verdiği pbs.twimg.com URL'leri
  public, Claude direkt fetch ediyor).
- Async — batch parse'ta semaphore ile concurrency kontrolü.

Maliyet hesabı (yaklaşık):
- System prompt ~3K token, caching ile sonraki çağrılarda 0.1× maliyet.
- Görsel başına ~1500 token (Opus 4.7 hi-res vision).
- Output ~500 token.
- 418 tweet * ~3500 input + 500 output ≈ $7-10 (Opus 4.7).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Optional

import anthropic
from loguru import logger

from mmxm.models import RawPost
from mmxm.parsing.prompts import SYSTEM_PROMPT, build_user_message
from mmxm.parsing.schema import ParsedPost

DEFAULT_MODEL = "claude-opus-4-7"


class ParseError(Exception):
    """Tek bir post parse edilemedi."""

    def __init__(self, post_id: str, cause: Exception):
        super().__init__(f"post_id={post_id} parse hatası: {cause}")
        self.post_id = post_id
        self.cause = cause


def _build_messages(post: RawPost, include_images: bool) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": build_user_message(post)}]
    if include_images:
        for url in post.media_urls:
            # Video thumbnail'ları (tweet_video_thumb, amplify_video_thumb)
            # genelde grafik içermez — atla. Düz "media/" path'leri foto/grafik.
            if "/media/" not in url and "video_thumb" in url:
                continue
            content.append({"type": "image", "source": {"type": "url", "url": url}})
    return [{"role": "user", "content": content}]


async def parse_post(
    post: RawPost,
    client: anthropic.AsyncAnthropic,
    *,
    model: str = DEFAULT_MODEL,
    include_images: bool = True,
    max_tokens: int = 4096,
) -> ParsedPost:
    """Tek bir postu structured ParsedPost'a çevir."""
    try:
        response = await client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=_build_messages(post, include_images),
            output_format=ParsedPost,
        )
    except anthropic.APIError as e:
        raise ParseError(post.post_id, e) from e

    parsed = response.parsed_output
    if parsed is None:
        raise ParseError(
            post.post_id, RuntimeError("parsed_output boş — schema validation başarısız")
        )

    usage = response.usage
    logger.debug(
        "parse_post id={} type={} confidence={:.2f} "
        "tokens in={} cache_read={} cache_write={} out={}",
        post.post_id,
        parsed.post_type.value,
        parsed.confidence,
        usage.input_tokens,
        usage.cache_read_input_tokens or 0,
        usage.cache_creation_input_tokens or 0,
        usage.output_tokens,
    )
    return parsed


async def parse_batch(
    posts: Iterable[RawPost],
    client: anthropic.AsyncAnthropic,
    *,
    model: str = DEFAULT_MODEL,
    include_images: bool = True,
    concurrency: int = 4,
) -> list[tuple[RawPost, Optional[ParsedPost], Optional[Exception]]]:
    """Birden fazla postu paralel parse et.

    Returns: her post için (post, parsed_or_None, error_or_None) üçlüsü.
    Concurrency=4 — Anthropic rate limit'lerini zorlamamak için ılımlı default.
    İlk çağrı cache yazıyor; ondan sonra eş zamanlı çağrılar cache okuyor.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(post: RawPost):
        async with sem:
            try:
                parsed = await parse_post(
                    post, client, model=model, include_images=include_images
                )
                return (post, parsed, None)
            except Exception as e:
                logger.warning("parse fail id={} err={}", post.post_id, e)
                return (post, None, e)

    return await asyncio.gather(*(_one(p) for p in posts))
