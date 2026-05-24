"""Strateji parametre grid search.

Her parametre kombinasyonu için:
1. Strategy instance oluştur
2. Aynı OHLCV üstünde tara
3. Sinyalleri simulate et (cached OHLCV)
4. Aggregate metrikleri hesapla

Sonuç: parametre setleri seçilen kritere göre (default: total_r) sıralanır.

Cached OHLCV ile çok hızlı — 100+ kombinasyon dakikalar içinde tamamlanır.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Callable, Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel

from mmxm.backtest.metrics import BacktestSummary, summarize
from mmxm.backtest.simulator import TradeResult, simulate_trade
from mmxm.strategies.base import Strategy


class GridResult(BaseModel):
    params: dict[str, Any]
    n_signals: int
    summary: BacktestSummary


def simulate_signals(
    signals: list,
    ohlcv: pd.DataFrame,
    *,
    max_hold_days: int = 30,
    entry_mode: str = "at_market",
) -> list[TradeResult]:
    """Pre-fetched OHLCV ile sinyalleri toplu simüle et."""
    return [
        simulate_trade(s, ohlcv, max_hold_days=max_hold_days, entry_mode=entry_mode)
        for s in signals
    ]


def grid_search(
    strategy_class: type[Strategy],
    param_grid: dict[str, list],
    symbol: str,
    ohlcv: pd.DataFrame,
    *,
    max_hold_days: int = 30,
    entry_mode: str = "at_market",
    rank_by: str = "total_r",
    min_signals: int = 10,  # az sinyalli setupları ele
) -> list[GridResult]:
    """Tüm parametre kombinasyonlarını tara, rank_by'a göre sırala."""
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]
    combos = list(product(*values))
    logger.info("grid search: {} kombinasyon, sembol={}, sinyal min={}",
                len(combos), symbol, min_signals)

    results: list[GridResult] = []
    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        try:
            strategy = strategy_class(**params)
            signals = strategy.scan(symbol, ohlcv)
        except Exception as e:
            logger.warning("kombinasyon {} fail: {}", params, e)
            continue
        if len(signals) < min_signals:
            continue
        trade_results = simulate_signals(
            signals, ohlcv, max_hold_days=max_hold_days, entry_mode=entry_mode
        )
        summary = summarize(trade_results)
        results.append(GridResult(
            params=params, n_signals=len(signals), summary=summary,
        ))
        if (i + 1) % 20 == 0:
            logger.info("  ilerleme {}/{}", i + 1, len(combos))

    # Sırala
    def _sort_key(g: GridResult) -> float:
        v = getattr(g.summary, rank_by)
        return -v if isinstance(v, (int, float)) else 0

    results.sort(key=_sort_key)
    return results
