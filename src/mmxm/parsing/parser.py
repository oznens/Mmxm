"""LLM ile RawPost -> ParsedPost çevirisi (Gemini 2.5 Flash backend).

Tasarım:
- Google Gemini 2.5 Flash (ücretsiz tier) — multimodal, Pydantic structured output.
- Görseller httpx ile indirilip `types.Part.from_bytes` ile inline gönderiliyor
  (pbs.twimg.com URL'leri Gemini'nin URL fetch'i için garanti değil).
- System prompt `system_instruction` olarak — her çağrıda gönderiliyor; free tier
  için maliyet 0, context caching gerekmiyor.
- Rate limit: Gemini 2.5 Flash free tier limiti **5 RPM** (API'nin döndürdüğü
  quota error'dan teyit edildi). Default 4 RPM, güvenlik payıyla. 418 tweet ≈ 100 dk.
- 429 RESOURCE_EXHAUSTED durumunda response'taki `retryDelay`'i okuyup bekleyip
  yeniden deniyoruz (max 3 retry).
- Thinking budget düşük: ICT çıkarımı için yeterli; daha hızlı çevirim.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Iterable
from typing import Any, Optional

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from loguru import logger

from mmxm.models import RawPost
from mmxm.parsing.prompts import SYSTEM_PROMPT, build_user_message
from mmxm.parsing.schema import ParsedPost

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_RPM = 4  # Gemini 2.5 Flash free tier 5 RPM; güvenlik payıyla 4
MAX_RETRIES_ON_429 = 3


class ParseError(Exception):
    """Tek bir post parse edilemedi."""

    def __init__(self, post_id: str, cause: Exception, *, summary: Optional[str] = None):
        msg = summary or str(cause)
        # Çok uzun JSON dump'ları logda kısalt.
        if len(msg) > 240:
            msg = msg[:240] + "...[truncated]"
        super().__init__(f"post_id={post_id} parse hatası: {msg}")
        self.post_id = post_id
        self.cause = cause


_RETRY_DELAY_RE = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')


def _extract_retry_delay_seconds(err: genai_errors.APIError) -> Optional[float]:
    """429 yanıtından retryDelay'i çıkar (saniye olarak)."""
    details: Any = getattr(err, "details", None)
    if isinstance(details, dict):
        # error.details[*].retryDelay
        for d in (details.get("error", {}) or {}).get("details", []) or []:
            rd = d.get("retryDelay")
            if isinstance(rd, str) and rd.endswith("s"):
                try:
                    return float(rd[:-1])
                except ValueError:
                    continue
    # Son çare: stringify edilmiş mesajdan regex.
    m = _RETRY_DELAY_RE.search(str(err))
    return float(m.group(1)) if m else None


class RateLimiter:
    """Asenkron, dakika başına N istek sınırlayıcı (basit interval bazlı)."""

    def __init__(self, requests_per_minute: int):
        self._interval = 60.0 / max(1, requests_per_minute)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


async def _fetch_image(
    url: str, http_client: httpx.AsyncClient
) -> Optional[tuple[bytes, str]]:
    """Görseli indir, (bytes, mime_type) döndür. Hata varsa None."""
    try:
        resp = await http_client.get(url, timeout=10.0)
    except httpx.HTTPError as e:
        logger.debug("görsel indirilemedi url={} err={}", url, e)
        return None
    if resp.status_code != 200:
        logger.debug("görsel HTTP {} url={}", resp.status_code, url)
        return None
    mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if not mime.startswith("image/"):
        return None
    return resp.content, mime


async def _build_contents(
    post: RawPost,
    http_client: httpx.AsyncClient,
    *,
    include_images: bool,
) -> list:
    parts: list = [build_user_message(post)]
    if not include_images:
        return parts

    for url in post.media_urls:
        # Video thumbnail'lar grafik içermez — atla.
        if "/media/" not in url and "video_thumb" in url:
            continue
        fetched = await _fetch_image(url, http_client)
        if fetched is None:
            continue
        data, mime = fetched
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    return parts


async def parse_post(
    post: RawPost,
    client: genai.Client,
    *,
    http_client: Optional[httpx.AsyncClient] = None,
    model: str = DEFAULT_MODEL,
    include_images: bool = True,
    thinking_budget: int = 1024,
    max_output_tokens: int = 4096,
    rate_limiter: Optional[RateLimiter] = None,
) -> ParsedPost:
    """Tek bir postu structured ParsedPost'a çevir."""
    own_http = http_client is None
    if own_http:
        http_client = httpx.AsyncClient()

    try:
        contents = await _build_contents(post, http_client, include_images=include_images)

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ParsedPost,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        )

        response = None
        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES_ON_429 + 1):
            if rate_limiter is not None:
                await rate_limiter.acquire()
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                break
            except genai_errors.APIError as e:
                last_err = e
                if e.code == 429 and attempt < MAX_RETRIES_ON_429:
                    delay = _extract_retry_delay_seconds(e) or (5.0 * (attempt + 1))
                    # Limiter'ı sıfırlamadan; sleep'in akıbetinden sonra limiter zaten cooldown'ı yönetiyor.
                    logger.info(
                        "429 rate limit id={} attempt={}/{}, {:.1f}s bekleniyor",
                        post.post_id,
                        attempt + 1,
                        MAX_RETRIES_ON_429,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Diğer hatalar veya retry hakkı bitti.
                raise ParseError(post.post_id, e, summary=f"{e.code} {e.status}") from e

        if response is None:
            assert last_err is not None
            raise ParseError(post.post_id, last_err)

        parsed = response.parsed
        if parsed is None:
            raise ParseError(
                post.post_id,
                RuntimeError("parsed boş — schema validation başarısız"),
                summary=f"schema fail; raw: {(response.text or '')[:120]}",
            )

        usage = response.usage_metadata
        logger.debug(
            "parse_post id={} type={} confidence={:.2f} "
            "tokens prompt={} thinking={} out={}",
            post.post_id,
            parsed.post_type.value,
            parsed.confidence,
            usage.prompt_token_count if usage else "?",
            usage.thoughts_token_count if usage else "?",
            usage.candidates_token_count if usage else "?",
        )
        return parsed
    finally:
        if own_http:
            await http_client.aclose()


async def parse_batch(
    posts: Iterable[RawPost],
    client: genai.Client,
    *,
    model: str = DEFAULT_MODEL,
    include_images: bool = True,
    concurrency: int = 3,
    requests_per_minute: int = DEFAULT_RPM,
    thinking_budget: int = 1024,
) -> list[tuple[RawPost, Optional[ParsedPost], Optional[Exception]]]:
    """Birden fazla postu paralel parse et.

    Concurrency `concurrency` paralel görev; `RateLimiter` ile dakika başına
    `requests_per_minute` üst sınırı uygulanır (free tier 15 RPM, default 12).
    """
    sem = asyncio.Semaphore(concurrency)
    limiter = RateLimiter(requests_per_minute)

    async with httpx.AsyncClient(timeout=15.0) as http_client:

        async def _one(post: RawPost):
            async with sem:
                try:
                    parsed = await parse_post(
                        post,
                        client,
                        http_client=http_client,
                        model=model,
                        include_images=include_images,
                        thinking_budget=thinking_budget,
                        rate_limiter=limiter,
                    )
                    return (post, parsed, None)
                except Exception as e:
                    logger.warning("parse fail id={} err={}", post.post_id, e)
                    return (post, None, e)

        return await asyncio.gather(*(_one(p) for p in posts))
