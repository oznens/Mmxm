"""Resmi X API v2 backend iskeleti.

Karar henüz verilmedi — bu modül arayüze uyan boş bir stub. Sonraki session'da
auth ve endpoint detayları doldurulacak (tweepy veya doğrudan httpx ile).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Optional

from mmxm.models import RawPost
from mmxm.scraping.base import ScraperBackend


class XApiBackend(ScraperBackend):
    name = "x_api_v2"

    def __init__(self, bearer_token: str) -> None:
        if not bearer_token:
            raise ValueError("X_BEARER_TOKEN gerekli")
        self.bearer_token = bearer_token

    async def fetch_user_posts(
        self,
        handle: str,
        since: Optional[datetime] = None,
        include_replies: bool = False,
        limit: Optional[int] = None,
    ) -> AsyncIterator[RawPost]:
        raise NotImplementedError(
            "X API v2 backend henüz implement edilmedi — sonraki session'da yapılacak."
        )
        yield  # type: ignore[unreachable]
