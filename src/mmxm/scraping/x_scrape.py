"""Scweet (https://github.com/Altimis/Scweet) tabanlı X scrape backend.

Auth modeli: X'in `auth_token` cookie'si yetiyor — `X_AUTH_TOKEN` env'i veya
constructor argümanı ile geçilir. Bir throwaway X hesabıyla DevTools üzerinden
çıkarılabiliyor. Login akışı yok.

Avantajları (Nitter RSS'e göre):
- Tarihsel arşiv: `since`/`until` ile geriye doğru ~aylar/yıllar çekilebilir.
- Resmi GraphQL endpoint'leri kullanılıyor → metin, medya, sayaçlar tam.
- Reply filtresi GraphQL düzeyinde (`tweet_type="exclude_replies"`).

Sınırlar:
- Hesap günlük kotası var; `limit` mutlaka set edilmeli.
- Scweet auth_token cookie'si X hesabına bağlı; banlanırsa yeni hesap gerekir.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from mmxm.models import RawPost
from mmxm.scraping.base import ScraperBackend

_TWITTER_TS_FMT = "%a %b %d %H:%M:%S %z %Y"  # ör. "Wed Oct 10 20:19:24 +0000 2018"


class ScweetBackend(ScraperBackend):
    name = "scweet"

    def __init__(
        self,
        auth_token: Optional[str] = None,
        *,
        db_path: str = "data/scweet_state.db",
        client: Any = None,
    ) -> None:
        """
        Args:
            auth_token: X auth_token cookie. Yoksa `client` enjekte edilmeli.
            db_path: Scweet'in resume/queue state'i için sqlite dosyası.
            client: Test için Scweet client mock'u (asearch metoduna sahip olmalı).
        """
        if client is not None:
            self._client = client
        else:
            if not auth_token:
                raise ValueError(
                    "Scweet için auth_token gerekli. X_AUTH_TOKEN env'ini doldur "
                    "veya --auth-token flag'i ile geç."
                )
            from Scweet import Scweet

            from pathlib import Path

            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._client = Scweet(auth_token=auth_token, db_path=db_path)

    async def fetch_user_posts(
        self,
        handle: str,
        since: Optional[datetime] = None,
        include_replies: bool = False,
        limit: Optional[int] = None,
    ) -> AsyncIterator[RawPost]:
        handle = handle.lstrip("@").lower()

        kwargs: dict[str, Any] = {"from_users": [handle]}
        if since is not None:
            kwargs["since"] = since.date().isoformat()
        if limit is not None:
            kwargs["limit"] = limit
        if not include_replies:
            kwargs["tweet_type"] = "exclude_replies"

        logger.info("scweet asearch handle={} kwargs={}", handle, kwargs)
        tweets = await self._client.asearch("", **kwargs)
        logger.info("scweet bitti handle={} n_raw={}", handle, len(tweets))

        for t in tweets:
            post = scweet_dict_to_raw_post(t, handle)
            if post is not None:
                yield post


def _parse_twitter_timestamp(ts: Any) -> Optional[datetime]:
    """X'in 'Wed Oct 10 20:19:24 +0000 2018' formatını datetime'a çevir."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.strptime(ts, _TWITTER_TS_FMT)
    except ValueError:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None


def scweet_dict_to_raw_post(d: dict, requested_handle: str) -> Optional[RawPost]:
    """Bir Scweet TweetRecord dict'ini RawPost'a çevir. None dönerse atla."""
    tweet_id = d.get("tweet_id")
    if not tweet_id:
        return None

    user = d.get("user") or {}
    handle = (user.get("screen_name") or requested_handle).lstrip("@").lower()

    text = d.get("text") or d.get("embedded_text") or ""

    created_at = _parse_twitter_timestamp(d.get("timestamp"))
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    legacy = ((d.get("raw") or {}).get("legacy")) or {}
    in_reply_to = legacy.get("in_reply_to_status_id_str")
    is_reply = bool(in_reply_to)

    media = d.get("media") or {}
    media_urls = list(media.get("image_links") or [])

    return RawPost(
        post_id=str(tweet_id),
        handle=handle,
        text=text,
        created_at=created_at,
        url=d.get("tweet_url"),
        is_reply=is_reply,
        in_reply_to=in_reply_to,
        media_urls=media_urls,
        raw={
            "likes": d.get("likes"),
            "retweets": d.get("retweets"),
            "comments": d.get("comments"),
        },
    )
