"""Trader çağrıları vs. rule-based strateji sinyallerinin overlap analizi.

Her bir trader trade için:
- Aynı sembol + aynı yön + ±max_window saat içinde stratejinin sinyalleri taranır
- Eşleşme sayısı, en yakın eşleşme tarihi, fiyat farkları raporlanır
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from mmxm.patterns.schema import TradeCallRecord


class Match(BaseModel):
    trader_post_id: str
    strategy_post_id: str
    trader_ts: datetime
    strategy_ts: datetime
    hours_diff: float  # strategy - trader (pozitif = strateji geç)
    trader_entry: Optional[float]
    strategy_entry: float
    entry_diff_pct: Optional[float]
    trader_target: Optional[float]
    strategy_target: float
    target_diff_pct: Optional[float]


class TraderMatchSummary(BaseModel):
    trader_post_id: str
    trader_handle: str
    trader_symbol: str
    trader_side: str
    trader_posted_at: datetime
    n_matches: int  # ±window içindeki sinyal sayısı
    best_match: Optional[Match] = None  # zaman olarak en yakın


def load_jsonl_as_trade_calls(path: Path | str) -> list[TradeCallRecord]:
    out = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out.append(TradeCallRecord.model_validate_json(line))
    return out


def find_matches(
    trader_trades: list[TradeCallRecord],
    strategy_signals: list[TradeCallRecord],
    *,
    max_hours: float = 48.0,
) -> list[TraderMatchSummary]:
    """Her trader trade için strateji eşleşmelerini bul."""
    summaries: list[TraderMatchSummary] = []
    for t in trader_trades:
        candidates: list[Match] = []
        for s in strategy_signals:
            if s.symbol != t.symbol or s.side != t.side:
                continue
            dh = (s.posted_at - t.posted_at).total_seconds() / 3600.0
            if abs(dh) > max_hours:
                continue
            entry_diff_pct = None
            if t.entry and s.entry:
                entry_diff_pct = 100 * (s.entry - t.entry) / t.entry
            target_diff_pct = None
            if t.targets and s.targets:
                target_diff_pct = 100 * (s.targets[0] - t.targets[0]) / t.targets[0]
            candidates.append(Match(
                trader_post_id=t.post_id, strategy_post_id=s.post_id,
                trader_ts=t.posted_at, strategy_ts=s.posted_at,
                hours_diff=round(dh, 1),
                trader_entry=t.entry, strategy_entry=s.entry,
                entry_diff_pct=round(entry_diff_pct, 2) if entry_diff_pct is not None else None,
                trader_target=t.targets[0] if t.targets else None,
                strategy_target=s.targets[0],
                target_diff_pct=round(target_diff_pct, 2) if target_diff_pct is not None else None,
            ))
        best = min(candidates, key=lambda m: abs(m.hours_diff)) if candidates else None
        summaries.append(TraderMatchSummary(
            trader_post_id=t.post_id, trader_handle=t.handle,
            trader_symbol=t.symbol, trader_side=t.side.value,
            trader_posted_at=t.posted_at,
            n_matches=len(candidates),
            best_match=best,
        ))
    return summaries


def overlap_stats(summaries: list[TraderMatchSummary]) -> dict:
    matched = [s for s in summaries if s.n_matches > 0]
    return {
        "n_trader_trades": len(summaries),
        "n_with_at_least_one_match": len(matched),
        "n_zero_matches": len(summaries) - len(matched),
        "coverage": round(len(matched) / max(1, len(summaries)), 3),
        "avg_matches_per_trade": round(
            sum(s.n_matches for s in summaries) / max(1, len(summaries)), 2
        ),
    }
