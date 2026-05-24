"""Strategy detector testleri — sentetik OHLCV ile."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from mmxm.parsing.schema import Side
from mmxm.strategies import TurtleSoupStrategy


def _bars(start: datetime, ohlc: list[tuple[float, float, float, float]], tf_min: int = 60) -> pd.DataFrame:
    rows = []
    for i, (o, h, l, c) in enumerate(ohlc):
        ts = start + timedelta(minutes=tf_min * i)
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def test_turtle_soup_detects_bullish_sweep():
    """22 bar range etrafında 100; sonra bir bar 95'e sweep + 102'ye reclaim."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # 22 sıkışma barı (low ~ 98-99, swing low ~ 98)
    ohlc = [(100, 102, 98, 100)] * 22
    # 23. bar: TS — low 95 (sweep), close 102 (reclaim)
    ohlc.append((99, 103, 95, 102))
    # devamı uzun
    ohlc.extend([(102, 104, 101, 103)] * 5)
    df = _bars(start, ohlc)

    strat = TurtleSoupStrategy(lookback=20, sweep_min_pct=0.005, reclaim_min_pct=0.005, debounce_bars=5)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == Side.LONG
    assert s.entry == 102.0
    assert s.stop_loss is not None and s.stop_loss < 95.0  # wick altı buffer
    # TP = entry + R*risk
    assert s.targets and s.targets[0] > s.entry


def test_turtle_soup_detects_bearish_sweep():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # swing high ~ 102
    ohlc = [(100, 102, 98, 100)] * 22
    # bearish TS: high 105 (sweep above), close 98 (reclaim down)
    ohlc.append((101, 105, 97, 98))
    ohlc.extend([(98, 99, 96, 97)] * 5)
    df = _bars(start, ohlc)

    strat = TurtleSoupStrategy(lookback=20, sweep_min_pct=0.005, reclaim_min_pct=0.005, debounce_bars=5)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == Side.SHORT
    assert s.entry == 98.0
    assert s.stop_loss is not None and s.stop_loss > 105.0


def test_turtle_soup_no_signal_when_no_reclaim():
    """Sweep var ama close hâlâ swing low'un altında — sinyal yok."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 22
    # low 95 (sweep), close 96 (reclaim yok — hala swing low 98 altında)
    ohlc.append((99, 100, 95, 96))
    df = _bars(start, ohlc)
    strat = TurtleSoupStrategy(lookback=20)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs == []


def test_turtle_soup_no_signal_when_sweep_too_shallow():
    """Sweep miktarı sweep_min_pct altında — sinyal yok."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 22
    # low 97.95 (sweep miktarı %0.05, sweep_min_pct %0.5 olsun → atla)
    ohlc.append((99, 103, 97.95, 102))
    df = _bars(start, ohlc)
    strat = TurtleSoupStrategy(lookback=20, sweep_min_pct=0.005)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs == []


def test_turtle_soup_debounce_blocks_consecutive_signals():
    """İki ardışık TS sinyali debounce ile tek'e iner."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 22
    # İki ardışık TS bar
    ohlc.append((99, 103, 95, 102))
    ohlc.append((102, 105, 96, 103))
    df = _bars(start, ohlc)
    strat = TurtleSoupStrategy(lookback=20, debounce_bars=10, sweep_min_pct=0.005, reclaim_min_pct=0.005)
    sigs = strat.scan("BTC/USDT", df)
    assert len(sigs) == 1  # ikincisi debounce ile filtrelenir


def test_turtle_soup_record_has_concepts_and_setups():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlc = [(100, 102, 98, 100)] * 22
    ohlc.append((99, 103, 95, 102))
    df = _bars(start, ohlc)
    strat = TurtleSoupStrategy(lookback=20, sweep_min_pct=0.005, reclaim_min_pct=0.005)
    sigs = strat.scan("BTC/USDT", df)
    assert sigs[0].matched_setups == ["turtle_soup", "liquidity_sweep_reversal"]
    assert "turtle_soup" in sigs[0].concepts
    assert sigs[0].handle == "STRATEGY_TURTLE_SOUP"
    assert len(sigs[0].key_levels) >= 4
