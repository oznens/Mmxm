"""MMXM strategy unit testleri."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from mmxm.parsing.schema import Side
from mmxm.strategies import MMXMStrategy


def _bars(start: datetime, ohlc: list[tuple[float, float, float, float]], tf_min: int = 60) -> pd.DataFrame:
    rows = []
    for i, (o, h, l, c) in enumerate(ohlc):
        ts = start + timedelta(minutes=tf_min * i)
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def test_mmxm_bullish_mmbm_detected():
    """Range [98,102], 30 bar konsolidasyon, bar 31 manipülasyon altta + SMR up."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 30 bar [98-102] arası range
    ohlc = [(100, 102, 98, 100)] * 30
    # bar 30 (31. bar): low 95 (range low altı manip), close 99 (SMR up, lower half)
    ohlc.append((100, 101, 95, 99))
    # devamı yukarı
    ohlc.extend([(99, 102, 98, 101)] * 3)
    df = _bars(start, ohlc)

    strat = MMXMStrategy(consolidation_bars=30, max_range_pct=0.10,
                        sweep_min_pct=0.005, reclaim_min_pct=0.005,
                        min_target_r=0.5)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == Side.LONG
    assert s.entry == 99.0
    assert s.stop_loss is not None and s.stop_loss < 95
    # TP range high'a yakın
    assert s.targets[0] >= 100  # range high ~ 102


def test_mmxm_bearish_mmsm_detected():
    """Range [98,102], bar 31 manipülasyon üstte + SMR down."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 30
    # high 105 (üst manip), close 101 (SMR down, upper half)
    ohlc.append((100, 105, 97, 101))
    ohlc.extend([(101, 102, 99, 100)] * 3)
    df = _bars(start, ohlc)

    strat = MMXMStrategy(consolidation_bars=30, max_range_pct=0.10,
                        sweep_min_pct=0.005, reclaim_min_pct=0.005,
                        min_target_r=0.5)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == Side.SHORT
    assert s.stop_loss is not None and s.stop_loss > 105


def test_mmxm_no_signal_when_range_too_wide():
    """%5'ten geniş range → konsolidasyon değil, sinyal yok."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 110, 90, 100)] * 30  # %20 range
    ohlc.append((100, 110, 85, 99))
    df = _bars(start, ohlc)
    strat = MMXMStrategy(consolidation_bars=30, max_range_pct=0.05)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs == []


def test_mmxm_no_signal_when_no_manipulation():
    """Bar 31 range içinde kalıyor → manipülasyon yok."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 30
    ohlc.append((100, 101, 99, 99))  # range içinde
    df = _bars(start, ohlc)
    strat = MMXMStrategy(consolidation_bars=30, sweep_min_pct=0.005, reclaim_min_pct=0.005)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs == []


def test_mmxm_tp_filtered_when_rr_too_low():
    """R:R < min_target_r → sinyal düşürülür."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 100.5, 99.5, 100)] * 30  # dar range %1
    # manip ufak, TP'ye mesafe kısa → R:R düşük
    ohlc.append((100, 100.5, 99.4, 99.6))
    df = _bars(start, ohlc)
    # min_target_r=3 ile filtrelenir
    strat = MMXMStrategy(consolidation_bars=30, max_range_pct=0.05,
                        sweep_min_pct=0.001, reclaim_min_pct=0.0005,
                        min_target_r=3.0)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs == []


def test_mmxm_record_has_mmxm_concepts():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 30
    ohlc.append((100, 101, 95, 99))
    ohlc.extend([(99, 102, 98, 101)] * 3)
    df = _bars(start, ohlc)
    strat = MMXMStrategy(consolidation_bars=30, max_range_pct=0.10,
                        sweep_min_pct=0.005, reclaim_min_pct=0.005,
                        min_target_r=0.5)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs
    s = sigs[0]
    assert "mmxm" in s.concepts
    assert "mmbm" in s.concepts  # long olduğu için
    assert s.handle == "STRATEGY_MMXM"
