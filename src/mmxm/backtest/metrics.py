"""Backtest sonuçlarından aggregate metrikler."""

from __future__ import annotations

from collections import Counter
from typing import Optional

from pydantic import BaseModel

from mmxm.backtest.simulator import TradeOutcome, TradeResult


class BacktestSummary(BaseModel):
    """Backtest seti için tek nokta özet."""

    n_trades_total: int
    n_skipped: int  # eksik veri / yön tutarsızlığı
    n_no_entry: int  # entry hit olmadı
    n_open: int  # max_hold doldu, açık
    n_closed: int  # tp + sl

    n_tp: int
    n_sl: int
    win_rate: float  # n_tp / n_closed

    total_r: float
    avg_r: float
    avg_winner_r: float
    avg_loser_r: float
    profit_factor: float  # |sum(wins)| / |sum(losses)|

    max_drawdown_r: float
    equity_curve: list[float]  # cumulative R

    per_symbol: dict[str, dict[str, float]] = {}
    per_setup: dict[str, dict[str, float]] = {}


def summarize(results: list[TradeResult], per_setup_map: Optional[dict[str, list[str]]] = None) -> BacktestSummary:
    """Tüm sonuçlardan özet.

    `per_setup_map[post_id] = [setup_name, ...]` verilirse setup başına metrikler de hesaplanır.
    """
    n = len(results)
    skipped = [r for r in results if r.outcome == TradeOutcome.SKIPPED]
    no_entry = [r for r in results if r.outcome == TradeOutcome.NO_ENTRY]
    opens = [r for r in results if r.outcome == TradeOutcome.OPEN]
    tps = [r for r in results if r.outcome == TradeOutcome.TP]
    sls = [r for r in results if r.outcome == TradeOutcome.SL]
    closed = tps + sls

    win_rate = len(tps) / len(closed) if closed else 0.0
    total_r = sum(r.r_multiple for r in tps + sls + opens)
    avg_r = total_r / max(1, len(tps + sls + opens))
    avg_w = sum(r.r_multiple for r in tps) / len(tps) if tps else 0.0
    avg_l = sum(r.r_multiple for r in sls) / len(sls) if sls else 0.0
    gains = sum(r.r_multiple for r in tps if r.r_multiple > 0)
    losses = abs(sum(r.r_multiple for r in sls if r.r_multiple < 0))
    pf = gains / losses if losses > 0 else float("inf") if gains > 0 else 0.0

    # Equity curve (sıralı, kapanış tarihine göre)
    closed_sorted = sorted(
        tps + sls + opens,
        key=lambda r: (r.exit_time or r.entry_time or r.posted_at),
    )
    equity = [0.0]
    for r in closed_sorted:
        equity.append(equity[-1] + r.r_multiple)

    # Max drawdown (R cinsinden)
    peak = equity[0]
    mdd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > mdd:
            mdd = dd

    per_symbol: dict[str, dict[str, float]] = {}
    sym_groups: dict[str, list[TradeResult]] = {}
    for r in results:
        sym_groups.setdefault(r.symbol, []).append(r)
    for sym, lst in sym_groups.items():
        sym_closed = [x for x in lst if x.outcome in (TradeOutcome.TP, TradeOutcome.SL)]
        sym_wins = [x for x in lst if x.outcome == TradeOutcome.TP]
        per_symbol[sym] = {
            "n": len(lst),
            "n_closed": len(sym_closed),
            "win_rate": len(sym_wins) / len(sym_closed) if sym_closed else 0.0,
            "total_r": round(sum(x.r_multiple for x in lst), 3),
        }

    per_setup: dict[str, dict[str, float]] = {}
    if per_setup_map:
        setup_groups: dict[str, list[TradeResult]] = {}
        for r in results:
            for s in per_setup_map.get(r.post_id, []):
                setup_groups.setdefault(s, []).append(r)
        for setup, lst in setup_groups.items():
            s_closed = [x for x in lst if x.outcome in (TradeOutcome.TP, TradeOutcome.SL)]
            s_wins = [x for x in lst if x.outcome == TradeOutcome.TP]
            per_setup[setup] = {
                "n": len(lst),
                "n_closed": len(s_closed),
                "win_rate": len(s_wins) / len(s_closed) if s_closed else 0.0,
                "total_r": round(sum(x.r_multiple for x in lst), 3),
            }

    return BacktestSummary(
        n_trades_total=n,
        n_skipped=len(skipped),
        n_no_entry=len(no_entry),
        n_open=len(opens),
        n_closed=len(closed),
        n_tp=len(tps),
        n_sl=len(sls),
        win_rate=round(win_rate, 3),
        total_r=round(total_r, 3),
        avg_r=round(avg_r, 3),
        avg_winner_r=round(avg_w, 3),
        avg_loser_r=round(avg_l, 3),
        profit_factor=round(pf, 3) if pf != float("inf") else 999.0,
        max_drawdown_r=round(mdd, 3),
        equity_curve=[round(e, 3) for e in equity],
        per_symbol=per_symbol,
        per_setup=per_setup,
    )
