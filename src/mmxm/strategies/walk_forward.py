"""Walk-forward validation — overfitting test.

Train (in-sample) periyodunda grid search ile optimal parametre bul,
sonra Test (out-of-sample) periyodunda aynı parametreyi kullan.
IS vs OOS performans karşılaştırması overfitting'i ortaya çıkarır.

- IS yüksek + OOS yüksek = robust strateji
- IS yüksek + OOS düşük = overfitted (curve-fit)
- IS düşük + OOS yüksek = lucky test (genelde değil)
- IS düşük + OOS düşük = parametreler kötü
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel

from mmxm.backtest.metrics import BacktestSummary, summarize
from mmxm.backtest.simulator import simulate_trade
from mmxm.strategies.base import Strategy
from mmxm.strategies.tuning import grid_search


class WalkForwardResult(BaseModel):
    symbol: str
    strategy_name: str
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    optimal_params: dict[str, Any]
    in_sample: BacktestSummary
    out_of_sample: BacktestSummary
    is_rsig: float
    oos_rsig: float
    degradation_pct: float  # (OOS - IS) / IS, negative = overfitting


def walk_forward_single(
    strategy_class: type[Strategy],
    symbol: str,
    train_ohlcv: pd.DataFrame,
    test_ohlcv: pd.DataFrame,
    param_grid: dict[str, list],
    *,
    max_hold_days: int = 30,
    rank_by: str = "total_r",
    min_signals: int = 20,
) -> WalkForwardResult:
    """Tek walk-forward: train periyodunda grid, test periyodunda doğrula."""
    if train_ohlcv.empty or test_ohlcv.empty:
        raise ValueError("train veya test OHLCV boş")

    logger.info(
        "walk-forward {}: train {} bar [{}→{}], test {} bar [{}→{}]",
        strategy_class.__name__,
        len(train_ohlcv), train_ohlcv.index.min(), train_ohlcv.index.max(),
        len(test_ohlcv), test_ohlcv.index.min(), test_ohlcv.index.max(),
    )

    # 1) Train üzerinde grid
    train_results = grid_search(
        strategy_class, param_grid, symbol, train_ohlcv,
        max_hold_days=max_hold_days, rank_by=rank_by, min_signals=min_signals,
    )
    if not train_results:
        raise RuntimeError("train grid hiçbir geçerli kombinasyon üretmedi")
    best = train_results[0]
    logger.info("  best train params: {} → R/sig {:.2f}, PF {:.2f}",
                best.params, best.summary.total_r / max(1, best.n_signals),
                best.summary.profit_factor)

    # 2) Test periyodunda aynı params
    strat = strategy_class(**best.params)
    test_signals = strat.scan(symbol, test_ohlcv)
    test_trade_results = [
        simulate_trade(s, test_ohlcv, max_hold_days=max_hold_days, entry_mode="at_market")
        for s in test_signals
    ]
    test_summary = summarize(test_trade_results)
    logger.info("  test (OOS) sinyali: {}, R/sig {:.2f}, PF {:.2f}",
                len(test_signals),
                test_summary.total_r / max(1, len(test_signals)),
                test_summary.profit_factor)

    is_rsig = best.summary.total_r / max(1, best.n_signals)
    oos_rsig = test_summary.total_r / max(1, test_summary.n_trades_total)
    degradation = (oos_rsig - is_rsig) / abs(is_rsig) if is_rsig != 0 else 0.0

    return WalkForwardResult(
        symbol=symbol,
        strategy_name=strategy_class.__name__,
        train_start=train_ohlcv.index.min().to_pydatetime(),
        train_end=train_ohlcv.index.max().to_pydatetime(),
        test_start=test_ohlcv.index.min().to_pydatetime(),
        test_end=test_ohlcv.index.max().to_pydatetime(),
        optimal_params=best.params,
        in_sample=best.summary,
        out_of_sample=test_summary,
        is_rsig=round(is_rsig, 3),
        oos_rsig=round(oos_rsig, 3),
        degradation_pct=round(degradation * 100, 1),
    )
