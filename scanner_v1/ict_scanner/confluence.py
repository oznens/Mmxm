from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass(slots=True)
class PDState:
    range_high: float
    range_low: float
    equilibrium: float
    zone: str
    ote_low: float | None
    ote_high: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SMTState:
    present: bool
    kind: str

    def to_dict(self) -> dict:
        return asdict(self)


def premium_discount(df: pd.DataFrame, direction: str, lookback: int = 60) -> PDState:
    x = df.iloc[-lookback:] if len(df) >= lookback else df
    hi = float(x.high.max())
    lo = float(x.low.min())
    eq = (hi + lo) / 2.0
    price = float(x.close.iloc[-1])
    zone = "PREMIUM" if price > eq else "DISCOUNT" if price < eq else "EQUILIBRIUM"
    r = hi - lo
    if direction == "LONG":
        # Retracement from high toward low: classic 62%-79% OTE band.
        ote_low = hi - 0.79 * r
        ote_high = hi - 0.62 * r
    else:
        ote_low = lo + 0.62 * r
        ote_high = lo + 0.79 * r
    return PDState(hi, lo, eq, zone, float(min(ote_low, ote_high)), float(max(ote_low, ote_high)))


def latest_fvg(df: pd.DataFrame, direction: str, search: int = 40) -> tuple[bool, float | None, float | None]:
    x = df.iloc[-search:] if len(df) > search else df
    if len(x) < 3:
        return False, None, None
    for i in range(len(x) - 1, 1, -1):
        a, c = x.iloc[i - 2], x.iloc[i]
        if direction == "LONG" and c.low > a.high:
            return True, float(a.high), float(c.low)
        if direction == "SHORT" and c.high < a.low:
            return True, float(c.high), float(a.low)
    return False, None, None


def latest_ifvg(df: pd.DataFrame, direction: str, search: int = 60) -> tuple[bool, float | None, float | None]:
    """Find a recently inverted opposite-direction FVG zone."""
    opposite = "SHORT" if direction == "LONG" else "LONG"
    x = df.iloc[-search:] if len(df) > search else df
    if len(x) < 5:
        return False, None, None
    zones: list[tuple[int, float, float]] = []
    for i in range(2, len(x) - 1):
        a, c = x.iloc[i - 2], x.iloc[i]
        if opposite == "LONG" and c.low > a.high:
            zones.append((i, float(a.high), float(c.low)))
        elif opposite == "SHORT" and c.high < a.low:
            zones.append((i, float(c.high), float(a.low)))
    for i, lo, hi in reversed(zones):
        later = x.iloc[i + 1:]
        if later.empty:
            continue
        if direction == "LONG" and (later.close > hi).any():
            return True, lo, hi
        if direction == "SHORT" and (later.close < lo).any():
            return True, lo, hi
    return False, None, None


def order_block(df: pd.DataFrame, direction: str, lookback: int = 20) -> tuple[bool, float | None, float | None]:
    x = df.iloc[-lookback:]
    if len(x) < 3:
        return False, None, None
    if direction == "LONG":
        opp = x.iloc[:-1][x.close.iloc[:-1] < x.open.iloc[:-1]]
    else:
        opp = x.iloc[:-1][x.close.iloc[:-1] > x.open.iloc[:-1]]
    if opp.empty:
        return False, None, None
    c = opp.iloc[-1]
    return True, float(c.low), float(c.high)


def smt_divergence(primary: pd.DataFrame, benchmark: pd.DataFrame, direction: str, lookback: int = 12) -> SMTState:
    """Simple relative-liquidity divergence against BTC/ETH benchmark.

    LONG: primary makes a lower low while benchmark does not.
    SHORT: primary makes a higher high while benchmark does not.
    """
    n = min(len(primary), len(benchmark), lookback + 1)
    if n < 5:
        return SMTState(False, "NONE")
    p = primary.iloc[-n:]
    b = benchmark.iloc[-n:]
    if direction == "LONG":
        p_break = float(p.low.iloc[-1]) < float(p.low.iloc[:-1].min())
        b_break = float(b.low.iloc[-1]) < float(b.low.iloc[:-1].min())
        return SMTState(bool(p_break and not b_break), "BULLISH" if p_break and not b_break else "NONE")
    p_break = float(p.high.iloc[-1]) > float(p.high.iloc[:-1].max())
    b_break = float(b.high.iloc[-1]) > float(b.high.iloc[:-1].max())
    return SMTState(bool(p_break and not b_break), "BEARISH" if p_break and not b_break else "NONE")


def rr(entry: float | None, stop: float | None, target: float | None) -> float | None:
    if entry is None or stop is None or target is None:
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    return round(abs(target - entry) / risk, 2)
