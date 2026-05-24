"""Nitter RSS tabanlı ücretsiz X scrape backend'i.

Yaklaşım:
- Public bir Nitter instance'ına `{instance}/{handle}/rss` GET et.
- Dönen RSS XML'ini stdlib `xml.etree` ile parse et.
- Item'lardan `RawPost` üret. Retweet ve yanıtları (isteğe göre) filtrele.
- Birden fazla instance verilirse sırayla dene (rate-limit / 404 / 5xx
  durumunda bir sonrakine geç).

Notlar:
- Nitter public instance'lar yıllar içinde sık sık kapanıyor / rate-limit'leniyor.
  Çalışan instance listesi `NITTER_INSTANCES` env değişkeniyle ya da CLI flag'iyle
  geçilebiliyor.
- RSS feed yalnızca son ~20 tweet'i veriyor; derin arşiv için cursor desteği yok.
  Tarihsel veri gerekirse twscrape benzeri bir backend'e geçilecek.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Optional
from xml.etree import ElementTree as ET

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mmxm.models import RawPost
from mmxm.scraping.base import ScraperBackend

_DC_NS = "{http://purl.org/dc/elements/1.1/}"
_STATUS_ID_RE = re.compile(r"/status/(\d+)")
_TAG_RE = re.compile(r"<[^>]+>")


class NitterUnavailable(Exception):
    """Tüm denenen instance'lar başarısız oldu."""


class NitterScrapeBackend(ScraperBackend):
    name = "nitter_rss"

    def __init__(
        self,
        instances: list[str],
        timeout: float = 15.0,
        user_agent: str = "Mozilla/5.0 (mmxm-research/0.0.1)",
    ) -> None:
        if not instances:
            raise ValueError(
                "En az bir Nitter instance gerekli. Örnek: 'https://nitter.net'. "
                "NITTER_INSTANCES env değişkenine virgülle ayrılmış URL listesi gir."
            )
        self.instances = [u.rstrip("/") for u in instances]
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/rss+xml, */*"},
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _fetch_rss(self, handle: str) -> str:
        last_err: Optional[Exception] = None
        for instance in self.instances:
            url = f"{instance}/{handle}/rss"
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=8),
                    retry=retry_if_exception_type(httpx.TransportError),
                    reraise=True,
                ):
                    with attempt:
                        resp = await self._client.get(url)
                if resp.status_code == 200 and resp.text.lstrip().startswith("<?xml"):
                    logger.debug("nitter ok handle={} instance={}", handle, instance)
                    return resp.text
                logger.warning(
                    "nitter başarısız handle={} instance={} status={} body_prefix={!r}",
                    handle,
                    instance,
                    resp.status_code,
                    resp.text[:120],
                )
                last_err = NitterUnavailable(
                    f"{instance} -> HTTP {resp.status_code}"
                )
            except httpx.HTTPError as e:
                logger.warning("nitter hata handle={} instance={} err={}", handle, instance, e)
                last_err = e

        raise NitterUnavailable(
            f"Tüm Nitter instance'ları başarısız: {self.instances}. Son hata: {last_err}"
        )

    async def fetch_user_posts(
        self,
        handle: str,
        since: Optional[datetime] = None,
        include_replies: bool = False,
        limit: Optional[int] = None,
    ) -> AsyncIterator[RawPost]:
        xml_text = await self._fetch_rss(handle)
        count = 0
        for post in parse_nitter_rss(xml_text, handle, include_replies=include_replies):
            if since is not None and post.created_at < _aware(since):
                continue
            yield post
            count += 1
            if limit is not None and count >= limit:
                return


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _clean_html(s: str) -> str:
    return unescape(_TAG_RE.sub("", s)).strip()


def _extract_status_id(url: str) -> Optional[str]:
    m = _STATUS_ID_RE.search(url)
    return m.group(1) if m else None


def parse_nitter_rss(
    xml_text: str,
    requested_handle: str,
    *,
    include_replies: bool = False,
) -> list[RawPost]:
    """Nitter RSS XML'ini RawPost listesine çevir.

    Filtreleme kuralları:
    - Retweet: `dc:creator` istenen handle'dan farklıysa atla.
    - Reply: `title` "R to @..." ile başlıyorsa, `include_replies` False ise atla.
    """
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    handle_lc = requested_handle.lstrip("@").lower()
    posts: list[RawPost] = []

    for item in channel.findall("item"):
        creator_el = item.find(f"{_DC_NS}creator")
        creator = (creator_el.text or "").lstrip("@").lower() if creator_el is not None else ""
        if creator and creator != handle_lc:
            # Retweet / başkasının postu — atla.
            continue

        title_raw = (item.findtext("title") or "").strip()
        is_reply = title_raw.startswith("R to @")
        if is_reply and not include_replies:
            continue

        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        status_id = _extract_status_id(link) or _extract_status_id(guid)
        if not status_id:
            continue

        description = item.findtext("description") or ""
        text = _clean_html(description) or _clean_html(title_raw)

        pub_date_str = item.findtext("pubDate")
        try:
            created_at = parsedate_to_datetime(pub_date_str) if pub_date_str else None
        except (TypeError, ValueError):
            created_at = None
        if created_at is None:
            continue
        created_at = _aware(created_at)

        posts.append(
            RawPost(
                post_id=status_id,
                handle=handle_lc,
                text=text,
                created_at=created_at,
                url=link or None,
                is_reply=is_reply,
                raw={"title": title_raw, "creator": creator},
            )
        )

    return posts
