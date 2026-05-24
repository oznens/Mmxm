"""Strateji sinyallerini birleştirme (AND / OR / VOTE).

Multi-strategy confluence: aynı sinyal birden fazla stratejide aynı yönde
çıkıyorsa trade kararının "confluence" puanı artar. ICT/SMC mantığı:
HTF bias + Turtle Soup + FVG retest birlikteyse setup A+ kalitede.

Rule'lar:
- "and": tüm stratejilerde sinyal olmalı (en sıkı filtre, en yüksek kalite)
- "or":   herhangi birinde sinyal yeterli (dedup, broader signal set)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from mmxm.parsing.schema import Side
from mmxm.patterns.schema import TradeCallRecord


def _merge_signals(sigs: list[TradeCallRecord]) -> TradeCallRecord:
    """Birden fazla strateji sinyalini tek bir confluence kaydına birleştir.

    Entry/SL/TP'leri en son (geç) sinyalden al — en güncel fiyat seviyeleri.
    Concept/setup'ları union al, confidence'ı bonus ile artır (max 1.0).
    """
    latest = max(sigs, key=lambda s: s.posted_at)
    setups = []
    concepts = []
    for s in sigs:
        for x in s.matched_setups:
            if x not in setups:
                setups.append(x)
        for x in s.concepts:
            if x not in concepts:
                concepts.append(x)
    bonus = 0.1 * (len(sigs) - 1)
    conf = min(1.0, min(s.confidence for s in sigs) + bonus)

    short_ids = [s.post_id[-12:] for s in sigs]
    handles = "+".join(s.handle.replace("STRATEGY_", "") for s in sigs)
    return TradeCallRecord(
        post_id=f"combined_{latest.symbol.replace('/', '_')}_{latest.posted_at.isoformat()}_{handles}",
        handle=f"COMBINED({handles})",
        posted_at=latest.posted_at,
        symbol=latest.symbol,
        side=latest.side,
        entry=latest.entry,
        stop_loss=latest.stop_loss,
        targets=latest.targets,
        timeframes=latest.timeframes,
        concepts=concepts,
        matched_setups=setups,
        key_levels=latest.key_levels,
        confidence=conf,
        rationale=f"Confluence ({len(sigs)} strateji): " + ", ".join(short_ids),
    )


def combine_and(
    signal_sets: list[list[TradeCallRecord]],
    time_window_hours: float = 4.0,
) -> list[TradeCallRecord]:
    """Her sinyalin DİĞER TÜM stratejilerde eşleşmesi gerekir."""
    if not signal_sets:
        return []
    if len(signal_sets) == 1:
        return list(signal_sets[0])

    primary, *others = signal_sets
    combined: list[TradeCallRecord] = []
    used_in_others: list[set[str]] = [set() for _ in others]

    for s0 in primary:
        matches: list[TradeCallRecord] = [s0]
        all_found = True
        for i, other_set in enumerate(others):
            found: Optional[TradeCallRecord] = None
            for s in other_set:
                if s.post_id in used_in_others[i]:
                    continue
                if s.symbol != s0.symbol or s.side != s0.side:
                    continue
                dh = abs((s.posted_at - s0.posted_at).total_seconds() / 3600)
                if dh <= time_window_hours:
                    found = s
                    break
            if found is None:
                all_found = False
                break
            matches.append(found)

        if all_found:
            for i, m in enumerate(matches[1:]):
                used_in_others[i].add(m.post_id)
            combined.append(_merge_signals(matches))
    return combined


def combine_or(
    signal_sets: list[list[TradeCallRecord]],
    time_window_hours: float = 1.0,
) -> list[TradeCallRecord]:
    """Tüm sinyalleri birleştir, ±time_window içinde duplikatları dedup et."""
    all_signals = [s for set_ in signal_sets for s in set_]
    all_signals.sort(key=lambda s: s.posted_at)
    out: list[TradeCallRecord] = []
    for s in all_signals:
        is_dup = False
        for o in out:
            if o.symbol == s.symbol and o.side == s.side:
                dh = abs((s.posted_at - o.posted_at).total_seconds() / 3600)
                if dh <= time_window_hours:
                    is_dup = True
                    break
        if not is_dup:
            out.append(s)
    return out


def combine(
    signal_sets: list[list[TradeCallRecord]],
    rule: str = "and",
    time_window_hours: float = 4.0,
) -> list[TradeCallRecord]:
    if rule == "and":
        return combine_and(signal_sets, time_window_hours=time_window_hours)
    if rule == "or":
        return combine_or(signal_sets, time_window_hours=time_window_hours)
    raise ValueError(f"bilinmeyen kural: {rule} (and | or)")
