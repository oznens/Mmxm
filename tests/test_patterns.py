"""Pattern mining unit testleri — pure function'lar, mock parsed kayıtlarla."""

from datetime import datetime, timezone

from mmxm.patterns import (
    build_report,
    concept_cooccurrence,
    concept_frequencies,
    extract_trade_calls,
    find_setup_matches,
    match_setups,
    summarize_setups,
    trader_profiles,
)
from mmxm.patterns.setups import SETUPS


def _parsed_record(
    *,
    post_id: str = "p1",
    handle: str = "trader_a",
    posted_at: str = "2024-05-01T12:00:00+00:00",
    post_type: str = "methodology",
    concepts: list[str] | None = None,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    bias: str | None = None,
    confidence: float = 0.85,
    trade: dict | None = None,
) -> dict:
    return {
        "source_post_id": post_id,
        "handle": handle,
        "posted_at": posted_at,
        "source_url": f"https://x.com/{handle}/status/{post_id}",
        "parsed": {
            "post_type": post_type,
            "language": "tr",
            "bias": bias,
            "timeframes": timeframes or [],
            "symbols_mentioned": symbols or [],
            "concepts": concepts or [],
            "trade": trade,
            "methodology_summary": None,
            "rationale": "test rationale",
            "key_levels": [],
            "confidence": confidence,
            "parser_notes": None,
        },
    }


# ---------- setups ----------


def test_setup_definitions_have_unique_names():
    names = [s.name for s in SETUPS]
    assert len(names) == len(set(names))


def test_match_amd_via_full_triple():
    matches = match_setups({"accumulation", "manipulation", "distribution"})
    names = [s.name for s, _ in matches]
    assert "amd_cycle" in names


def test_match_amd_via_shorthand():
    matches = match_setups({"amd", "wyckoff"})
    names = [s.name for s, _ in matches]
    assert "amd_cycle" in names


def test_match_fvg_requires_htf_or_ltf():
    assert "fvg_retest_entry" not in [s.name for s, _ in match_setups({"fvg"})]
    assert "fvg_retest_entry" in [
        s.name for s, _ in match_setups({"fvg", "htf_bias"})
    ]
    assert "fvg_retest_entry" in [
        s.name for s, _ in match_setups({"fvg", "ltf_entry"})
    ]


def test_liquidity_sweep_needs_companion_concept():
    """Sadece liquidity_sweep yeterli olmamalı (companion concept gerekli)."""
    assert "liquidity_sweep_reversal" not in [
        s.name for s, _ in match_setups({"liquidity_sweep"})
    ]
    assert "liquidity_sweep_reversal" in [
        s.name for s, _ in match_setups({"liquidity_sweep", "ob"})
    ]


def test_turtle_soup_simple():
    assert "turtle_soup" in [s.name for s, _ in match_setups({"turtle_soup"})]


def test_match_setups_returns_triggered_concepts():
    matches = match_setups({"amd", "manipulation", "fvg", "htf_bias"})
    by_name = {s.name: triggered for s, triggered in matches}
    # AMD seed setinden tetiklenen kavramlar
    assert "amd" in by_name["amd_cycle"]
    # FVG seed setinden
    assert "fvg" in by_name["fvg_retest_entry"]


# ---------- frequencies + cooccurrence ----------


def test_concept_frequencies():
    records = [
        _parsed_record(concepts=["fvg", "ob"]),
        _parsed_record(concepts=["fvg", "liquidity_sweep"]),
        _parsed_record(concepts=["amd"]),
    ]
    freq = concept_frequencies(records)
    assert freq["fvg"] == 2
    assert freq["ob"] == 1
    assert freq["amd"] == 1


def test_concept_cooccurrence_alphabetical_pairs():
    records = [
        _parsed_record(concepts=["fvg", "ob", "liquidity_sweep"]),
        _parsed_record(concepts=["fvg", "ob"]),
        _parsed_record(concepts=["fvg", "ob"]),
    ]
    pairs = concept_cooccurrence(records, min_count=2)
    # ("fvg","ob") çiftinin 3'ü de var
    assert pairs[("fvg", "ob")] == 3
    # ("fvg","liquidity_sweep") sadece 1, min_count=2 ile filtrelenir
    assert ("fvg", "liquidity_sweep") not in pairs


# ---------- trader profiles ----------


def test_trader_profiles_per_handle():
    records = [
        _parsed_record(handle="alice", post_type="trade_call", concepts=["fvg"]),
        _parsed_record(handle="alice", post_type="methodology", concepts=["fvg", "ob"]),
        _parsed_record(handle="bob", post_type="noise", concepts=[]),
    ]
    profiles = trader_profiles(records)
    by_handle = {p.handle: p for p in profiles}

    alice = by_handle["alice"]
    assert alice.n_posts == 2
    assert alice.n_trade_calls == 1
    assert alice.post_type_dist == {"trade_call": 1, "methodology": 1}
    assert dict(alice.top_concepts)["fvg"] == 2

    bob = by_handle["bob"]
    assert bob.n_posts == 1
    assert bob.n_trade_calls == 0


# ---------- setup matching + summary ----------


def test_find_setup_matches_yields_multiple_per_post():
    rec = _parsed_record(
        post_id="px", concepts=["fvg", "htf_bias", "amd", "liquidity_sweep", "ob"]
    )
    matches = find_setup_matches([rec])
    setup_names = {m.setup_name for m in matches}
    # Birden fazla setup eşleşebilir
    assert "fvg_retest_entry" in setup_names
    assert "amd_cycle" in setup_names
    assert "liquidity_sweep_reversal" in setup_names
    # Hepsi aynı post_id'ye işaret ediyor
    assert all(m.post_id == "px" for m in matches)


def test_summarize_setups_aggregates_correctly():
    records = [
        _parsed_record(post_id="p1", handle="alice", concepts=["fvg", "htf_bias"], confidence=0.9),
        _parsed_record(post_id="p2", handle="alice", concepts=["fvg", "ltf_entry"], confidence=0.8),
        _parsed_record(post_id="p3", handle="bob", concepts=["turtle_soup"], confidence=0.95),
    ]
    matches = find_setup_matches(records)
    summaries = summarize_setups(matches)
    by_name = {s.setup_name: s for s in summaries}

    fvg_setup = by_name["fvg_retest_entry"]
    assert fvg_setup.n_matches == 2
    assert fvg_setup.handles == {"alice": 2}
    assert abs(fvg_setup.avg_confidence - 0.85) < 1e-6

    ts = by_name["turtle_soup"]
    assert ts.n_matches == 1
    assert ts.handles == {"bob": 1}


# ---------- trade call extraction ----------


def test_extract_trade_calls_filters_to_trade_call_post_type():
    records = [
        _parsed_record(
            post_id="t1",
            post_type="trade_call",
            concepts=["fvg", "htf_bias"],
            symbols=["BTC/USDT"],
            trade={
                "symbol": "BTC/USDT",
                "side": "long",
                "entry": 60000.0,
                "stop_loss": 58500.0,
                "targets": [62000.0, 64000.0],
                "leverage": None,
                "risk_reward": 2.5,
                "entry_zone_low": None,
                "entry_zone_high": None,
            },
        ),
        _parsed_record(post_id="m1", post_type="methodology", concepts=["fvg"]),
        _parsed_record(post_id="n1", post_type="noise"),
    ]
    calls = extract_trade_calls(records)
    assert len(calls) == 1
    c = calls[0]
    assert c.post_id == "t1"
    assert c.symbol == "BTC/USDT"
    assert c.entry == 60000.0
    assert c.targets == [62000.0, 64000.0]
    # matched_setups: bu post fvg_retest_entry'e uyuyor
    assert "fvg_retest_entry" in c.matched_setups


def test_extract_trade_calls_skips_when_trade_field_missing():
    """post_type=trade_call ama trade alanı None → atla."""
    rec = _parsed_record(post_id="bad", post_type="trade_call", trade=None)
    assert extract_trade_calls([rec]) == []


# ---------- full report ----------


def test_build_report_end_to_end():
    records = [
        _parsed_record(
            post_id="t1",
            handle="alice",
            post_type="trade_call",
            concepts=["turtle_soup", "fvg", "htf_bias"],
            trade={
                "symbol": "BTC/USDT",
                "side": "long",
                "entry": 60000.0,
                "stop_loss": 58500.0,
                "targets": [62000.0],
                "leverage": None,
                "risk_reward": None,
                "entry_zone_low": None,
                "entry_zone_high": None,
            },
        ),
        _parsed_record(handle="alice", concepts=["fvg", "ob"]),
        _parsed_record(handle="bob", concepts=["amd", "accumulation"]),
    ]
    report, calls = build_report(records)
    assert report.n_parsed_posts == 3
    assert report.n_trade_calls == 1
    assert len(calls) == 1
    handles = {p.handle for p in report.trader_profiles}
    assert handles == {"alice", "bob"}
    # En sık setup'lar listede
    setup_names = {s.setup_name for s in report.setup_summaries}
    assert setup_names  # boş değil
