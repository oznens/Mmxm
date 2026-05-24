"""OHLCV fetch + parquet cache.

Backendler:
- "binance", "kucoin", vb. → CCXT (public crypto exchange API'leri).
  Bu container'dan public crypto API'leri network-block'lu çıkıyor; kullanıcı
  lokalde çalıştırırsa OK.
- "yahoo" → yfinance üzerinden Yahoo Finance. Sembol mapping: BTC/USDT → BTC-USD,
  ETH/USDT → ETH-USD vb. Free, container'dan erişilebilir, kripto + forex + index var.

Cache: data/prices/{backend}_{symbol}_{timeframe}.parquet
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import ccxt
import pandas as pd
from loguru import logger

DEFAULT_CACHE_DIR = Path("data/prices")

# Yahoo Finance sembol mapping — kripto için "X-USD"
_YAHOO_SYMBOL_MAP = {
    "BTC/USDT": "BTC-USD", "BTC/USD": "BTC-USD", "BTC": "BTC-USD",
    "ETH/USDT": "ETH-USD", "ETH/USD": "ETH-USD", "ETH": "ETH-USD",
    "SOL/USDT": "SOL-USD", "SUI/USDT": "SUI-USD",
    "XRP/USDT": "XRP-USD", "DOGE/USDT": "DOGE-USD",
    "ONDO/USDT": "ONDO-USD", "ARB/USDT": "ARB-USD",
    "NEAR/USDT": "NEAR-USD", "FET/USDT": "FET-USD",
    "RNDR/USDT": "RNDR-USD",
    # Forex / metals (Yahoo: "EURUSD=X" etc.)
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X",
    "XAU/USD": "GC=F", "XAUUSD": "GC=F",  # Gold futures
    # US index futures
    "NQ1!": "NQ=F", "NQ": "NQ=F", "ES1!": "ES=F", "ES": "ES=F",
}

_YAHOO_TF_MAP = {
    "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "60m": "1h",
    "1d": "1d", "5d": "5d",
    "1w": "1wk", "1mo": "1mo",
    # 4h/3m yfinance native değil; en yakın alt'a düşür
    "3m": "5m", "4h": "1h",
}


def _cache_path(exchange_id: str, symbol: str, timeframe: str, cache_dir: Path) -> Path:
    safe_symbol = symbol.replace("/", "_").replace(":", "_")
    return cache_dir / f"{exchange_id}_{safe_symbol}_{timeframe}.parquet"


def _tf_to_ms(timeframe: str) -> int:
    """'1h' -> 3600000, '1d' -> 86400000 vb."""
    unit = timeframe[-1]
    n = int(timeframe[:-1])
    multipliers = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    if unit not in multipliers:
        raise ValueError(f"bilinmeyen timeframe: {timeframe}")
    return n * multipliers[unit]


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    exchange_id: str = "binance",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
) -> pd.DataFrame:
    """OHLCV indir, parquet cache et, DataFrame döndür.

    Returns: DatetimeIndex (UTC) + open/high/low/close/volume kolonları.
    """
    if exchange_id == "yahoo":
        return _fetch_ohlcv_yahoo(symbol, timeframe, since, until, cache_dir, refresh)

    cache_dir = Path(cache_dir)
    cache_file = _cache_path(exchange_id, symbol, timeframe, cache_dir)

    cached: Optional[pd.DataFrame] = None
    if cache_file.exists() and not refresh:
        cached = pd.read_parquet(cache_file)
        if not cached.empty and since is not None and until is not None:
            cmin, cmax = cached.index.min(), cached.index.max()
            since_aware = _aware(since)
            until_aware = _aware(until)
            if cmin <= since_aware and cmax >= until_aware:
                return cached.loc[since_aware:until_aware].copy()

    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    tf_ms = _tf_to_ms(timeframe)
    limit = 1000

    since_ms = int(_aware(since).timestamp() * 1000) if since else int(
        (datetime(2024, 1, 1, tzinfo=timezone.utc)).timestamp() * 1000
    )
    until_ms = int(_aware(until).timestamp() * 1000) if until else int(time.time() * 1000)

    # Cache varsa eksik aralığı doldur; en son cached bar'dan devam et.
    if cached is not None and not cached.empty:
        last_cached_ms = int(cached.index.max().timestamp() * 1000)
        if last_cached_ms + tf_ms > since_ms:
            since_ms = last_cached_ms + tf_ms

    candles: list[list] = []
    while since_ms < until_ms:
        try:
            batch = exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=limit)
        except ccxt.BaseError as e:
            logger.error("CCXT hata symbol={} tf={} err={}", symbol, timeframe, e)
            break
        if not batch:
            break
        candles.extend(batch)
        last_ts = batch[-1][0]
        if last_ts + tf_ms >= until_ms:
            break
        since_ms = last_ts + tf_ms
        time.sleep(exchange.rateLimit / 1000.0)  # CCXT rate-limit dostu

    if not candles and cached is None:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    if candles:
        new_df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume"])
        new_df["ts"] = pd.to_datetime(new_df["ts"], unit="ms", utc=True)
        new_df = new_df.set_index("ts")
        if cached is not None and not cached.empty:
            combined = pd.concat([cached, new_df])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        else:
            combined = new_df
    else:
        combined = cached  # type: ignore[assignment]

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(cache_file)
    logger.info(
        "ohlcv cached symbol={} tf={} rows={} range={} → {}",
        symbol,
        timeframe,
        len(combined),
        combined.index.min(),
        combined.index.max(),
    )

    if since is not None and until is not None:
        return combined.loc[_aware(since):_aware(until)].copy()
    return combined


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch_ohlcv_yahoo(
    symbol: str,
    timeframe: str,
    since: Optional[datetime],
    until: Optional[datetime],
    cache_dir: Path,
    refresh: bool,
) -> pd.DataFrame:
    """Yahoo Finance backend (yfinance ile)."""
    cache_dir = Path(cache_dir)
    cache_file = _cache_path("yahoo", symbol, timeframe, cache_dir)

    if cache_file.exists() and not refresh:
        cached = pd.read_parquet(cache_file)
        if not cached.empty and since is not None and until is not None:
            cmin, cmax = cached.index.min(), cached.index.max()
            since_aware = _aware(since)
            until_aware = _aware(until)
            if cmin <= since_aware and cmax >= until_aware:
                return cached.loc[since_aware:until_aware].copy()

    ticker = _YAHOO_SYMBOL_MAP.get(symbol)
    if not ticker:
        # Fallback: USDT pair → "BASE-USD" formatı denesin
        if symbol.endswith("/USDT") or symbol.endswith("/USD"):
            base = symbol.split("/")[0]
            ticker = f"{base}-USD"
        else:
            raise ValueError(f"Yahoo sembol mapping yok: {symbol}")

    yf_tf = _YAHOO_TF_MAP.get(timeframe, timeframe)
    if timeframe != yf_tf:
        logger.warning("yahoo: {} TF native değil → {}'a düşüldü", timeframe, yf_tf)

    import yfinance as yf
    yf_ticker = yf.Ticker(ticker)
    start = _aware(since) if since else datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = _aware(until) if until else datetime.now(timezone.utc)

    df = yf_ticker.history(start=start, end=end, interval=yf_tf, auto_adjust=False)
    if df.empty:
        logger.error("yahoo {} {} empty", ticker, yf_tf)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = df.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "ts"
    df = df[~df.index.duplicated(keep="last")].sort_index()

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file)
    logger.info(
        "yahoo cached {} → {} rows={} range={} → {}",
        symbol, ticker, len(df), df.index.min(), df.index.max(),
    )
    if since is not None and until is not None:
        return df.loc[_aware(since):_aware(until)].copy()
    return df
