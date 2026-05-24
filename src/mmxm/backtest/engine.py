"""Backtest orkestrasyonu: trade-call'ları yükle, simüle et, özetle."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from mmxm.backtest.data import fetch_ohlcv
from mmxm.backtest.metrics import BacktestSummary, summarize
from mmxm.backtest.simulator import TradeResult, simulate_trade
from mmxm.patterns.schema import TradeCallRecord


def load_trade_calls(path: Path | str) -> list[TradeCallRecord]:
    out: list[TradeCallRecord] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(TradeCallRecord.model_validate_json(line))
    return out


def _resolve_timeframe(trade: TradeCallRecord, default: str = "1h") -> str:
    """Trade'in timeframes listesinden CCXT-uyumlu en küçük TF'i seç."""
    tf_map = {
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "h1": "1h", "1H": "1h",
        "4h": "4h", "h4": "4h",
        "1d": "1d", "d1": "1d", "daily": "1d", "1D": "1d",
        "1w": "1w", "weekly": "1w",
    }
    for tf in trade.timeframes:
        if tf in tf_map:
            return tf_map[tf]
    return default


def run_backtest(
    trades: list[TradeCallRecord],
    *,
    exchange_id: str = "binance",
    default_timeframe: str = "1h",
    max_hold_days: int = 90,
    history_pad_days: int = 7,
    entry_mode: str = "at_market",
) -> tuple[list[TradeResult], BacktestSummary]:
    """Her trade için OHLCV indir + simüle + aggregate."""
    results: list[TradeResult] = []
    setup_map: dict[str, list[str]] = {}

    # OHLCV cache'ini sembol/TF bazında grupla — aynı sembol + TF kombinasyonu için tek fetch
    fetch_keys: dict[tuple[str, str], tuple[datetime, datetime]] = {}
    for t in trades:
        if t.entry is None or t.stop_loss is None or not t.targets:
            continue
        tf = _resolve_timeframe(t, default_timeframe)
        key = (t.symbol, tf)
        since = t.posted_at - timedelta(days=history_pad_days)
        until = t.posted_at + timedelta(days=max_hold_days + history_pad_days)
        if key in fetch_keys:
            cs, cu = fetch_keys[key]
            since = min(since, cs)
            until = max(until, cu)
        fetch_keys[key] = (since, until)

    ohlcv_cache: dict[tuple[str, str], "Any"] = {}
    for (symbol, tf), (since, until) in fetch_keys.items():
        logger.info("fetching ohlcv {} {} {} → {}", symbol, tf, since.date(), until.date())
        try:
            df = fetch_ohlcv(symbol, tf, since=since, until=until, exchange_id=exchange_id)
            ohlcv_cache[(symbol, tf)] = df
        except Exception as e:
            logger.error("ohlcv fetch fail {} {}: {}", symbol, tf, e)
            ohlcv_cache[(symbol, tf)] = None

    # Simulate
    for t in trades:
        setup_map[t.post_id] = list(t.matched_setups)
        tf = _resolve_timeframe(t, default_timeframe)
        ohlcv = ohlcv_cache.get((t.symbol, tf))
        if ohlcv is None or len(ohlcv) == 0:
            res = simulate_trade(t, _empty_df(), max_hold_days=max_hold_days, entry_mode=entry_mode)
            res.note = (res.note or "") + " (ohlcv eksik)"
        else:
            res = simulate_trade(t, ohlcv, max_hold_days=max_hold_days, entry_mode=entry_mode)
        results.append(res)

    summary = summarize(results, per_setup_map=setup_map)
    return results, summary


def _empty_df():
    import pandas as pd
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


def write_results(path: Path | str, results: list[TradeResult]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(r.model_dump_json() + "\n")


def write_summary(path: Path | str, summary: BacktestSummary) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
