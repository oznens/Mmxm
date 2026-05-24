"""TwExportly (twexportly.com) CSV dump'ını RawPost JSONL'e çevirir.

TwExportly format kolonları:
  tweet_id  (apostrofla quoted: 'XXX')
  text
  language
  type             : Tweet | Reply | Retweet
  bookmark_count, favorite_count, retweet_count, reply_count, view_count
  created_at       : 'YYYY-MM-DD HH:MM:SS' (UTC varsayıyoruz)
  client
  hashtags, urls
  media_type       : photo | video | animated_gif | (boş)
  media_urls       : virgül-ayrılmış URL listesi

Filtre stratejisi:
- Retweet: SKIP (başkasının içeriği)
- Tweet: KEEP
- Reply: include_text_only_replies True ise hepsi; False ise yalnızca media içerenler
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mmxm.models import RawPost

# Tweet metnindeki bilgisiz t.co URL'lerini (uçlardaki) temizle.
_TCO_TAIL = re.compile(r"\s*https?://t\.co/\S+\s*$")
# tweet_id 'XXX' formatından çıkar
_ID_QUOTES = re.compile(r"^['\"]?(\d+)['\"]?$")


def _clean_id(raw: str) -> Optional[str]:
    m = _ID_QUOTES.match(raw.strip())
    return m.group(1) if m else None


def _split_media(raw: str) -> list[str]:
    if not raw:
        return []
    return [u.strip() for u in raw.split(",") if u.strip().startswith("http")]


def _parse_ts(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _clean_text(text: str) -> str:
    """Tweet metnindeki sonda asılı t.co URL'sini sil (görsel için otomatik eklenir)."""
    return _TCO_TAIL.sub("", text).strip()


def iter_csv_posts(
    path: Path | str,
    handle: str,
    *,
    include_replies_with_media: bool = True,
    include_text_only_replies: bool = False,
    include_retweets: bool = False,
) -> Iterator[RawPost]:
    """CSV'den RawPost yield et. Filtreler default davranışı belirler."""
    handle_lc = handle.lstrip("@").lower()
    path = Path(path)
    with path.open("r", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            tweet_type = (row.get("type") or "").strip()
            if tweet_type == "Retweet" and not include_retweets:
                continue

            media_urls = _split_media(row.get("media_urls") or "")
            is_reply = tweet_type == "Reply"

            if is_reply:
                if media_urls:
                    if not include_replies_with_media:
                        continue
                else:
                    if not include_text_only_replies:
                        continue

            post_id = _clean_id(row.get("tweet_id") or "")
            created_at = _parse_ts(row.get("created_at") or "")
            text = _clean_text(row.get("text") or "")

            if not post_id or created_at is None:
                continue

            yield RawPost(
                post_id=post_id,
                handle=handle_lc,
                text=text,
                created_at=created_at,
                url=f"https://x.com/{handle_lc}/status/{post_id}",
                is_reply=is_reply,
                media_urls=media_urls,
                raw={
                    "type": tweet_type,
                    "language": row.get("language") or "",
                    "media_type": row.get("media_type") or "",
                    "view_count": int(row.get("view_count") or 0),
                    "favorite_count": int(row.get("favorite_count") or 0),
                },
            )
