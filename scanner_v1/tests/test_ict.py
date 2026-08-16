import pandas as pd

from ict_scanner.confluence import latest_fvg, premium_discount, smt_divergence
from ict_scanner.ict import liquidity_raid
from ict_scanner.liquidity import LiquidityMap, daily_levels, session_levels
from ict_scanner.structure import displacement, structure_state


def df(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).astype(float)


def test_bullish_fvg():
    x = df([
        [100, 101, 99, 100],
        [100, 103, 100, 102],
        [103, 104, 102, 103],
    ])
    ok, lo, hi = latest_fvg(x, "LONG")
    assert ok
    assert lo == 101
    assert hi == 102


def test_liquidity_raid_uses_named_pdh():
    x = df([[99, 101, 98, 99.5], [100, 102, 99, 100.5]])
    m = LiquidityMap(pdh=101.5)
    ok, name, level = liquidity_raid(x, "SHORT", m)
    assert ok
    assert name == "pdh"
    assert level == 101.5


def test_premium_discount_and_ote():
    x = df([[100 + i, 102 + i, 98 + i, 101 + i] for i in range(60)])
    state = premium_discount(x, "LONG")
    assert state.range_high > state.range_low
    assert state.ote_low < state.ote_high


def test_smt_bullish_when_primary_takes_low_benchmark_does_not():
    p = df([[100, 101, 99, 100] for _ in range(12)] + [[100, 101, 97, 100]])
    b = df([[100, 101, 99, 100] for _ in range(12)] + [[100, 101, 99.2, 100]])
    state = smt_divergence(p, b, "LONG")
    assert state.present
    assert state.kind == "BULLISH"


def test_daily_and_asia_session_levels_are_timezone_aware():
    ts = pd.date_range("2026-08-14 00:00", "2026-08-16 04:00", freq="15min", tz="UTC")
    x = pd.DataFrame({
        "timestamp": ts,
        "open": 100.0,
        "high": range(100, 100 + len(ts)),
        "low": range(99, 99 + len(ts)),
        "close": 100.0,
    })
    pdh, pdl = daily_levels(x)
    ah, al = session_levels(x, "asia")
    assert pdh is not None and pdl is not None
    assert ah is not None and al is not None


def test_displacement_and_structure_state():
    rows = [[100, 101, 99, 100] for _ in range(30)]
    rows[-1] = [100, 106, 99.8, 105.5]
    x = df(rows)
    ok, ratio = displacement(x, "LONG")
    state = structure_state(x, "LONG")
    assert ok
    assert ratio > 1.0
    assert state.displacement
