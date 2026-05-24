"""Setup -> BacktestResult simülasyon motoru (iskelet)."""

from __future__ import annotations

from mmxm.models import BacktestResult, Setup


def run_backtest(setup: Setup, symbol: str, timeframe: str) -> BacktestResult:
    raise NotImplementedError("Backtest engine sonraki adımda eklenecek.")
