"""Trader listesini scrape edip ham postları JSONL'e yazan koordinatör."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from mmxm.scraping.base import ScraperBackend, TraderConfig, TradersFile
from mmxm.scraping.storage import write_jsonl


async def scrape_trader(
    backend: ScraperBackend,
    trader: TraderConfig,
    out_dir: Path,
    since: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> int:
    effective_since = since or trader.since
    logger.info(
        "scrape başlıyor handle={} since={} include_replies={}",
        trader.handle,
        effective_since,
        trader.include_replies,
    )
    posts = []
    async for post in backend.fetch_user_posts(
        handle=trader.handle,
        since=effective_since,
        include_replies=trader.include_replies,
        limit=limit,
    ):
        posts.append(post)

    out_path = out_dir / f"{trader.handle}.jsonl"
    n = write_jsonl(out_path, posts)
    logger.info("scrape bitti handle={} n_posts={} path={}", trader.handle, n, out_path)
    return n


async def scrape_all(
    backend: ScraperBackend,
    traders_path: Path | str,
    out_dir: Path | str,
    since: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> dict[str, int]:
    cfg = TradersFile.load(traders_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        results = await asyncio.gather(
            *(scrape_trader(backend, t, out_dir, since, limit) for t in cfg.traders),
            return_exceptions=True,
        )
    finally:
        await backend.close()

    summary: dict[str, int] = {}
    for trader, result in zip(cfg.traders, results):
        if isinstance(result, Exception):
            logger.error("handle={} hata={}", trader.handle, result)
            summary[trader.handle] = -1
        else:
            summary[trader.handle] = result
    return summary
