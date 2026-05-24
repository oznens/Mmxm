"""Scraper backend kontratı.

Veri kaynağı kararı (resmi X API v2 mi, unofficial scrape mı) sonraki session'da
yapılacak. Bu modül, somut implementasyondan bağımsız olarak iki tarafın da
uyacağı arayüzü tanımlar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from mmxm.models import RawPost


class TraderConfig(BaseModel):
    handle: str
    tags: list[str] = Field(default_factory=list)
    include_replies: bool = False
    since: Optional[datetime] = None
    notes: Optional[str] = None


class TradersFile(BaseModel):
    traders: list[TraderConfig]

    @classmethod
    def load(cls, path: Path | str) -> TradersFile:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)


class ScraperBackend(ABC):
    """Tüm X scraper implementasyonlarının uyması gereken arayüz."""

    name: str = "base"

    @abstractmethod
    async def fetch_user_posts(
        self,
        handle: str,
        since: Optional[datetime] = None,
        include_replies: bool = False,
        limit: Optional[int] = None,
    ) -> AsyncIterator[RawPost]:
        """Bir kullanıcının tweet'lerini en yeniden eskiye doğru yield et."""
        raise NotImplementedError
        yield  # type: ignore[unreachable]  # pragma: no cover -- async iterator imzası

    async def close(self) -> None:
        """Backend kaynaklarını (HTTP client, vb.) kapat."""
        return None
