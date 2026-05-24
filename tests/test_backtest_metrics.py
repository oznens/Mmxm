"""Aggregate metrik testleri."""

from datetime import datetime, timezone

import pytest

from mmxm.backtest.metrics import summarize
from mmxm.backtest.simulator import TradeOutcome, TradeResult
from mmxm.parsing.schema import Side


_T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _r(outcome: str, r_mult: float, *, post_id: str = "p", symbol: str = "BTC/USDT", side: Side = Side.LONG, seq: int = 0) -> TradeResult:
    from datetime import timedelta as _td
    return TradeResult(
        post_id=post_id,
        symbol=symbol,
        side=side,
        posted_at=_T0,
        outcome=outcome,
        r_multiple=r_mult,
        entry_time=_T0 + _td(days=seq),
        exit_time=_T0 + _td(days=seq + 1),
    )


def test_summary_counts():
    results = [
        _r(TradeOutcome.TP, 2.0),
        _r(TradeOutcome.TP, 1.5),
        _r(TradeOutcome.SL, -1.0),
        _r(TradeOutcome.OPEN, 0.3),
        _r(TradeOutcome.SKIPPED, 0.0),
        _r(TradeOutcome.NO_ENTRY, 0.0),
    ]
    s = summarize(results)
    assert s.n_trades_total == 6
    assert s.n_tp == 2
    assert s.n_sl == 1
    assert s.n_open == 1
    assert s.n_skipped == 1
    assert s.n_no_entry == 1
    assert s.n_closed == 3
    assert s.win_rate == pytest.approx(2 / 3, abs=0.001)


def test_summary_r_and_pf():
    results = [
        _r(TradeOutcome.TP, 2.0),
        _r(TradeOutcome.TP, 3.0),
        _r(TradeOutcome.SL, -1.0),
    ]
    s = summarize(results)
    assert s.total_r == 4.0
    assert s.avg_r == pytest.approx(4 / 3, abs=0.01)
    assert s.avg_winner_r == 2.5
    assert s.avg_loser_r == -1.0
    assert s.profit_factor == 5.0  # 5 / 1


def test_max_drawdown():
    """Equity: 0, 2, 1, -0.5, 1.5 — peak 2 → trough -0.5 → DD=2.5"""
    results = [
        _r(TradeOutcome.TP, 2.0, post_id="a", seq=0),
        _r(TradeOutcome.SL, -1.0, post_id="b", seq=1),
        _r(TradeOutcome.SL, -1.5, post_id="c", seq=2),
        _r(TradeOutcome.TP, 2.0, post_id="d", seq=3),
    ]
    s = summarize(results)
    assert s.max_drawdown_r == 2.5
    assert s.equity_curve == [0, 2.0, 1.0, -0.5, 1.5]


def test_per_symbol_grouping():
    results = [
        _r(TradeOutcome.TP, 2.0, symbol="BTC/USDT"),
        _r(TradeOutcome.SL, -1.0, symbol="BTC/USDT"),
        _r(TradeOutcome.TP, 3.0, symbol="ETH/USDT"),
    ]
    s = summarize(results)
    assert s.per_symbol["BTC/USDT"]["n"] == 2
    assert s.per_symbol["BTC/USDT"]["win_rate"] == 0.5
    assert s.per_symbol["ETH/USDT"]["n"] == 1


def test_per_setup_grouping():
    results = [
        _r(TradeOutcome.TP, 2.0, post_id="p1"),
        _r(TradeOutcome.SL, -1.0, post_id="p2"),
        _r(TradeOutcome.TP, 3.0, post_id="p3"),
    ]
    setup_map = {
        "p1": ["turtle_soup"],
        "p2": ["turtle_soup", "amd_cycle"],
        "p3": ["amd_cycle"],
    }
    s = summarize(results, per_setup_map=setup_map)
    assert s.per_setup["turtle_soup"]["n"] == 2
    assert s.per_setup["turtle_soup"]["win_rate"] == 0.5
    assert s.per_setup["amd_cycle"]["n"] == 2
    assert s.per_setup["amd_cycle"]["win_rate"] == 0.5
