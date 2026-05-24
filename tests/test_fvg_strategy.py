"""FVG retest strategy unit testleri."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from mmxm.parsing.schema import Side
from mmxm.strategies import FVGRetestStrategy


def _bars(start: datetime, ohlc: list[tuple[float, float, float, float]], tf_min: int = 60) -> pd.DataFrame:
    rows = []
    for i, (o, h, l, c) in enumerate(ohlc):
        ts = start + timedelta(minutes=tf_min * i)
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def test_bullish_fvg_detected_and_retested():
    """3-mum bullish FVG → fiyat geri çekilip retest → long sinyali."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # bar 0: high 100, low 99
    # bar 1: hızlı yukarı (büyük yeşil mum)
    # bar 2: low 105 (gap created: [100, 105])
    # bar 3-5: yukarı devam
    # bar 6: retest — low 101 (FVG zone içine geri dön)
    ohlc = [
        (99, 100, 99, 99.5),   # bar 0
        (99.5, 106, 99.5, 105.5),  # bar 1 — displacement
        (105.5, 108, 105, 107),  # bar 2 — gap [100, 105]
        (107, 108, 106, 107),  # bar 3
        (107, 109, 106, 108),  # bar 4
        (108, 110, 107, 109),  # bar 5
        (109, 109, 101, 102),  # bar 6 — retest low 101 (içinde FVG [100, 105])
    ]
    df = _bars(start, ohlc)

    strat = FVGRetestStrategy(min_fvg_size_pct=0.01, max_age_bars=20, target_r=2.0)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) >= 1
    s = sigs[0]
    assert s.side == Side.LONG
    assert s.entry == 102.0  # bar 6 close
    assert s.stop_loss is not None and s.stop_loss < 100  # FVG lower altı
    assert s.targets and s.targets[0] > s.entry


def test_bearish_fvg_detected_and_retested():
    """3-mum bearish FVG → retest yukarı → short."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # bar 0: low 105 (yüksek)
    # bar 1: hızlı aşağı
    # bar 2: high 100 (gap [100, 105])
    # bar 3-5: aşağı devam
    # bar 6: retest — high 104 (FVG zone içine geri dön)
    ohlc = [
        (106, 107, 105, 106),  # bar 0
        (106, 106, 99, 100),  # bar 1 — bearish displacement
        (100, 100.5, 95, 96),  # bar 2 — gap [100, 105]
        (96, 97, 94, 95),
        (95, 96, 93, 94),
        (94, 95, 92, 93),
        (93, 104, 93, 103),  # bar 6 — retest high 104 (içinde FVG [100, 105])
    ]
    df = _bars(start, ohlc)

    strat = FVGRetestStrategy(min_fvg_size_pct=0.01, max_age_bars=20, target_r=2.0)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) >= 1
    s = sigs[0]
    assert s.side == Side.SHORT
    assert s.stop_loss is not None and s.stop_loss > 105


def test_no_signal_when_fvg_too_small():
    """min_fvg_size_pct altındaki gap'ler filtrelenir."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Çok küçük gap: 100.0 → 100.05 (sadece %0.05)
    ohlc = [
        (99.5, 100.0, 99, 99.8),
        (99.8, 100.5, 99.8, 100.4),
        (100.4, 100.5, 100.05, 100.2),  # tiny gap
        (100.2, 100.5, 99.95, 100.0),
    ]
    df = _bars(start, ohlc)
    strat = FVGRetestStrategy(min_fvg_size_pct=0.005)  # %0.5 min
    sigs = strat.scan("BTC/USDT", df)
    # FVG çok küçük → tespit edilmez
    assert sigs == []


def test_fvg_expires_after_max_age():
    """max_age_bars sonra FVG retest sinyali üretmez."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # bullish FVG + uzun süre yukarı + en sonda retest
    ohlc = [
        (99, 100, 99, 99.5),
        (99.5, 106, 99.5, 105.5),
        (105.5, 108, 105, 107),  # gap [100, 105]
    ]
    # 30 bar yukarıda kal (max_age_bars=10 ile expire eder)
    ohlc.extend([(107 + i * 0.1, 108 + i * 0.1, 106 + i * 0.1, 107 + i * 0.1) for i in range(30)])
    # 33. bar retest
    ohlc.append((137, 137, 101, 102))
    df = _bars(start, ohlc)

    strat = FVGRetestStrategy(min_fvg_size_pct=0.01, max_age_bars=10)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs == []


def test_record_has_fvg_concepts():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [
        (99, 100, 99, 99.5),
        (99.5, 106, 99.5, 105.5),
        (105.5, 108, 105, 107),
        (107, 108, 106, 107),
        (107, 108, 101, 102),
    ]
    df = _bars(start, ohlc)
    strat = FVGRetestStrategy(min_fvg_size_pct=0.01)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs
    s = sigs[0]
    assert "fvg" in s.concepts
    assert s.matched_setups == ["fvg_retest_entry"]
    assert s.handle == "STRATEGY_FVG_RETEST"
