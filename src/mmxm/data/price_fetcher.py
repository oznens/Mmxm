"""OHLCV fetch + parquet cache (iskelet)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def fetch_ohlcv(
    symbol: str,
    timeframe: str,
    since: datetime,
    until: datetime,
    cache_dir: Path | str = "data/prices",
):
    raise NotImplementedError("CCXT fetch sonraki adımda eklenecek.")
