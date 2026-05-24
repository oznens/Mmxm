"""Parse edilmiş postlardan pattern mining: profil, setup eşleşmesi, trade-call çıkarımı."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime
from itertools import combinations
from typing import Any

from mmxm.parsing.schema import Bias, KeyLevel, ParsedPost, PostType, Side, TradeCall
from mmxm.patterns.schema import (
    PatternsReport,
    SetupMatch,
    SetupSummary,
    TraderProfile,
    TradeCallRecord,
)
from mmxm.patterns.setups import SETUPS, match_setups


def _to_parsed(rec: dict) -> tuple[str, str, datetime, str | None, ParsedPost]:
    """JSONL satırından (post_id, handle, posted_at, source_url, ParsedPost) çıkar."""
    return (
        rec["source_post_id"],
        rec["handle"],
        datetime.fromisoformat(rec["posted_at"]),
        rec.get("source_url"),
        ParsedPost.model_validate(rec["parsed"]),
    )


def trader_profiles(records: Iterable[dict], top_n: int = 10) -> list[TraderProfile]:
    """Her trader için descriptive özet."""
    by_handle: dict[str, list[ParsedPost]] = defaultdict(list)
    for rec in records:
        _, handle, _, _, parsed = _to_parsed(rec)
        by_handle[handle].append(parsed)

    profiles = []
    for handle, posts in by_handle.items():
        post_types = Counter(p.post_type.value for p in posts)
        biases = Counter(p.bias.value for p in posts if p.bias is not None)
        languages = Counter(p.language for p in posts)
        concepts = Counter(c for p in posts for c in p.concepts)
        symbols = Counter(s for p in posts for s in p.symbols_mentioned)
        timeframes = Counter(tf for p in posts for tf in p.timeframes)

        profiles.append(
            TraderProfile(
                handle=handle,
                n_posts=len(posts),
                post_type_dist=dict(post_types),
                bias_dist=dict(biases),
                language_dist=dict(languages),
                n_trade_calls=post_types.get("trade_call", 0),
                avg_confidence=(
                    sum(p.confidence for p in posts) / len(posts) if posts else 0.0
                ),
                top_concepts=concepts.most_common(top_n),
                top_symbols=symbols.most_common(top_n),
                top_timeframes=timeframes.most_common(top_n),
            )
        )
    return sorted(profiles, key=lambda p: p.handle)


def concept_frequencies(records: Iterable[dict]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for rec in records:
        for c in rec["parsed"].get("concepts", []) or []:
            counter[c] += 1
    return counter


def concept_cooccurrence(
    records: Iterable[dict], min_count: int = 3
) -> dict[tuple[str, str], int]:
    """Konseptlerin ikili birlikte geçme matrisi (sıralı çift, alfabetik)."""
    pair_counts: Counter[tuple[str, str]] = Counter()
    for rec in records:
        concepts = sorted(set(rec["parsed"].get("concepts", []) or []))
        for a, b in combinations(concepts, 2):
            pair_counts[(a, b)] += 1
    return {pair: n for pair, n in pair_counts.items() if n >= min_count}


def find_setup_matches(records: Iterable[dict]) -> list[SetupMatch]:
    """Her post için eşleşen setup'ları çıkar (post birden fazla setup'a uyabilir)."""
    matches: list[SetupMatch] = []
    for rec in records:
        post_id, handle, posted_at, _, parsed = _to_parsed(rec)
        concepts_set = set(parsed.concepts)
        for setup, triggered in match_setups(concepts_set):
            matches.append(
                SetupMatch(
                    setup_name=setup.name,
                    post_id=post_id,
                    handle=handle,
                    posted_at=posted_at,
                    confidence=parsed.confidence,
                    matched_concepts=triggered,
                    timeframes=parsed.timeframes,
                    symbols=parsed.symbols_mentioned,
                    bias=parsed.bias,
                )
            )
    return matches


def summarize_setups(matches: list[SetupMatch]) -> list[SetupSummary]:
    """SetupMatch listesinden setup başına aggregate stats."""
    by_setup: dict[str, list[SetupMatch]] = defaultdict(list)
    for m in matches:
        by_setup[m.setup_name].append(m)

    descriptions = {s.name: s.description for s in SETUPS}
    out = []
    for name, ms in by_setup.items():
        handles = Counter(m.handle for m in ms)
        tfs = Counter(tf for m in ms for tf in m.timeframes)
        syms = Counter(s for m in ms for s in m.symbols)
        biases = Counter(m.bias.value for m in ms if m.bias is not None)
        out.append(
            SetupSummary(
                setup_name=name,
                description=descriptions.get(name, ""),
                n_matches=len(ms),
                handles=dict(handles),
                timeframe_dist=dict(tfs),
                symbol_dist=dict(syms),
                bias_dist=dict(biases),
                avg_confidence=sum(m.confidence for m in ms) / len(ms),
                sample_post_ids=[m.post_id for m in ms[:5]],
            )
        )
    return sorted(out, key=lambda s: -s.n_matches)


def extract_trade_calls(records: Iterable[dict]) -> list[TradeCallRecord]:
    """Yalnızca trade_call tipindeki postları backtest-ready formatına çevir."""
    calls: list[TradeCallRecord] = []
    for rec in records:
        post_id, handle, posted_at, source_url, parsed = _to_parsed(rec)
        if parsed.post_type != PostType.TRADE_CALL or parsed.trade is None:
            continue
        t: TradeCall = parsed.trade
        # Bu post hangi setup'lara uyuyor?
        matched = [setup.name for setup, _ in match_setups(set(parsed.concepts))]
        calls.append(
            TradeCallRecord(
                post_id=post_id,
                handle=handle,
                posted_at=posted_at,
                symbol=t.symbol,
                side=t.side,
                entry=t.entry,
                entry_zone_low=t.entry_zone_low,
                entry_zone_high=t.entry_zone_high,
                stop_loss=t.stop_loss,
                targets=list(t.targets),
                leverage=t.leverage,
                risk_reward=t.risk_reward,
                timeframes=parsed.timeframes,
                concepts=parsed.concepts,
                matched_setups=matched,
                key_levels=parsed.key_levels,
                confidence=parsed.confidence,
                rationale=parsed.rationale,
                source_url=source_url,
            )
        )
    return calls


def build_report(records: list[dict]) -> tuple[PatternsReport, list[TradeCallRecord]]:
    """Tüm pattern mining çıktısını üret."""
    profiles = trader_profiles(records)
    matches = find_setup_matches(records)
    setup_summaries = summarize_setups(matches)
    trade_calls = extract_trade_calls(records)
    concepts = concept_frequencies(records)
    pairs = concept_cooccurrence(records)
    cooc_top: list[tuple[tuple[str, str], int]] = sorted(
        pairs.items(), key=lambda kv: -kv[1]
    )[:30]

    report = PatternsReport(
        n_parsed_posts=len(records),
        n_trade_calls=len(trade_calls),
        trader_profiles=profiles,
        setup_summaries=setup_summaries,
        top_concepts_overall=concepts.most_common(25),
        concept_cooccurrence_top=cooc_top,
    )
    return report, trade_calls
