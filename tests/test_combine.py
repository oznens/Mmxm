"""Multi-strategy combine testleri."""

from datetime import datetime, timedelta, timezone

from mmxm.parsing.schema import Side
from mmxm.patterns.schema import TradeCallRecord
from mmxm.strategies.combine import combine_and, combine_or


def _sig(side: Side, ts: datetime, *, post_id: str, handle: str = "STRAT_A",
         symbol: str = "BTC/USDT", entry: float = 100.0,
         sl: float = 99.0, tp: float = 102.0, conf: float = 0.7) -> TradeCallRecord:
    return TradeCallRecord(
        post_id=post_id, handle=handle, posted_at=ts,
        symbol=symbol, side=side,
        entry=entry, stop_loss=sl, targets=[tp],
        matched_setups=[handle.lower()],
        concepts=[handle.lower() + "_concept"],
        confidence=conf, rationale="test",
    )


T0 = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


# --- AND ---


def test_and_returns_only_overlapping_signals():
    """Aynı sembol+yön, ±window içinde her iki strateji de sinyal → confluence."""
    a = [_sig(Side.LONG, T0, post_id="a1", handle="STRATEGY_TS")]
    b = [_sig(Side.LONG, T0 + timedelta(hours=2), post_id="b1", handle="STRATEGY_FVG")]
    merged = combine_and([a, b], time_window_hours=4.0)
    assert len(merged) == 1
    m = merged[0]
    assert m.side == Side.LONG
    # En son sinyalin (b1) entry/SL kullanılır
    assert m.posted_at == T0 + timedelta(hours=2)
    # Confluence: handle birleşmiş
    assert "TS" in m.handle and "FVG" in m.handle
    # Setup'lar union
    assert len(m.matched_setups) == 2


def test_and_drops_non_overlapping():
    """Sinyal eşleşmesi olmayan trade düşürülür."""
    a = [_sig(Side.LONG, T0, post_id="a1")]
    b = [_sig(Side.LONG, T0 + timedelta(hours=10), post_id="b1")]
    merged = combine_and([a, b], time_window_hours=4.0)
    assert merged == []


def test_and_drops_opposite_direction():
    """Aynı zaman, zıt yön → eşleşme yok."""
    a = [_sig(Side.LONG, T0, post_id="a1")]
    b = [_sig(Side.SHORT, T0 + timedelta(hours=1), post_id="b1")]
    merged = combine_and([a, b])
    assert merged == []


def test_and_three_strategies():
    """3 strateji hepsi eşleşmeli."""
    a = [_sig(Side.LONG, T0, post_id="a1")]
    b = [_sig(Side.LONG, T0 + timedelta(hours=1), post_id="b1")]
    c = [_sig(Side.LONG, T0 + timedelta(hours=2), post_id="c1")]
    merged = combine_and([a, b, c], time_window_hours=4.0)
    assert len(merged) == 1
    # 4. strateji boş → tümü eşleşmez
    d: list[TradeCallRecord] = []
    merged = combine_and([a, b, c, d], time_window_hours=4.0)
    assert merged == []


def test_and_confidence_bonus_for_confluence():
    a = [_sig(Side.LONG, T0, post_id="a1", conf=0.6)]
    b = [_sig(Side.LONG, T0, post_id="b1", conf=0.7)]
    merged = combine_and([a, b])
    # min(0.6, 0.7) + 0.1 bonus = 0.7
    assert merged[0].confidence == 0.7


def test_and_does_not_double_match_same_signal():
    """Aynı b sinyali iki kez kullanılmaz."""
    a = [
        _sig(Side.LONG, T0, post_id="a1"),
        _sig(Side.LONG, T0 + timedelta(hours=1), post_id="a2"),
    ]
    b = [_sig(Side.LONG, T0 + timedelta(hours=1), post_id="b1")]
    merged = combine_and([a, b], time_window_hours=5.0)
    # Sadece 1 eşleşme (b1 yalnız bir kez kullanılabilir)
    assert len(merged) == 1


# --- OR ---


def test_or_unions_and_dedups():
    a = [_sig(Side.LONG, T0, post_id="a1")]
    b = [_sig(Side.LONG, T0 + timedelta(minutes=30), post_id="b1")]  # ±1h içinde
    merged = combine_or([a, b], time_window_hours=1.0)
    # Birinci kalır (ts sıralı)
    assert len(merged) == 1


def test_or_keeps_different_directions():
    a = [_sig(Side.LONG, T0, post_id="a1")]
    b = [_sig(Side.SHORT, T0, post_id="b1")]
    merged = combine_or([a, b], time_window_hours=1.0)
    # Yön farklı, ikisi de kalır
    assert len(merged) == 2


def test_or_keeps_different_symbols():
    a = [_sig(Side.LONG, T0, post_id="a1", symbol="BTC/USDT")]
    b = [_sig(Side.LONG, T0, post_id="b1", symbol="ETH/USDT")]
    merged = combine_or([a, b], time_window_hours=1.0)
    assert len(merged) == 2
