"""Unofficial scrape backend iskeleti (snscrape veya benzeri).

Karar henüz verilmedi. Bu modül de arayüze uyan stub.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Optional

from mmxm.models import RawPost
from mmxm.scraping.base import ScraperBackend


class XScrapeBackend(ScraperBackend):
    name = "x_scrape"

    async def fetch_user_posts(
        self,
        handle: str,
        since: Optional[datetime] = None,
        include_replies: bool = False,
        limit: Optional[int] = None,
    ) -> AsyncIterator[RawPost]:
        raise NotImplementedError(
            "Unofficial X scrape backend henüz implement edilmedi — "
            "sonraki session'da snscrape/httpx tabanlı çözüm seçilecek."
        )
        yield  # type: ignore[unreachable]
