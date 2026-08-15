from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

import pandas as pd

Direction = Literal["LONG", "SHORT", "NONE"]


@dataclass(slots=True)
class Signal:
    symbol: str
    direction: Direction
    score: int
    htf_bias: str
    mmxm: str
    turtle_soup: bool
    mss: bool
    fvg: bool
    entry_low: float | None = None
    entry_high: float | None = None
    stop: float | None = None
    target: float | None = None
    liquidity_level: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def htf_bias(df4h: pd.DataFrame) -> str:
    if len(df4h) < 30:
        return "NEUTRAL"
    recent = df4h.iloc[-20:]
    midpoint = (recent.high.max() + recent.low.min()) / 2
    last = df4h.iloc[-1]
    hh = recent.high.iloc[-10:].max() > recent.high.iloc[:10].max()
    ll = recent.low.iloc[-10:].min() < recent.low.iloc[:10].min()
    if last.close < midpoint and ll:
        return "BEARISH"
    if last.close > midpoint and hh:
        return "BULLISH"
    return "NEUTRAL"


def _previous_extreme(df: pd.DataFrame, lookback: int = 20) -> tuple[float, float]:
    prior = df.iloc[-(lookback + 1):-1]
    return float(prior.high.max()), float(prior.low.min())


def turtle_soup(df: pd.DataFrame, direction: Direction, lookback: int = 20) -> tuple[bool, float | None]:
    if len(df) < lookback + 1:
        return False, None
    prev_high, prev_low = _previous_extreme(df, lookback)
    c = df.iloc[-1]
    if direction == "SHORT":
        ok = c.high > prev_high and c.close < prev_high
        return bool(ok), prev_high if ok else None
    if direction == "LONG":
        ok = c.low < prev_low and c.close > prev_low
        return bool(ok), prev_low if ok else None
    return False, None


def market_structure_shift(df: pd.DataFrame, direction: Direction) -> bool:
    if len(df) < 12:
        return False
    recent = df.iloc[-10:]
    last = recent.iloc[-1]
    if direction == "SHORT":
        return bool(last.close < recent.low.iloc[:-2].min() and last.close < last.open)
    if direction == "LONG":
        return bool(last.close > recent.high.iloc[:-2].max() and last.close > last.open)
    return False


def latest_fvg(df: pd.DataFrame, direction: Direction) -> tuple[bool, float | None, float | None]:
    if len(df) < 3:
        return False, None, None
    for i in range(len(df) - 1, 1, -1):
        a, c = df.iloc[i - 2], df.iloc[i]
        if direction == "LONG" and c.low > a.high:
            return True, float(a.high), float(c.low)
        if direction == "SHORT" and c.high < a.low:
            return True, float(c.high), float(a.low)
    return False, None, None


def mmxm_model(df1h: pd.DataFrame, direction: Direction) -> str:
    if len(df1h) < 30:
        return "NONE"
    recent = df1h.iloc[-24:]
    first, second = recent.iloc[:12], recent.iloc[12:]
    if direction == "SHORT":
        return "MMSM" if second.high.max() > first.high.max() and second.close.iloc[-1] < second.open.iloc[0] else "NONE"
    if direction == "LONG":
        return "MMBM" if second.low.min() < first.low.min() and second.close.iloc[-1] > second.open.iloc[0] else "NONE"
    return "NONE"


def analyze_symbol(symbol: str, tf: dict[str, pd.DataFrame]) -> Signal:
    bias = htf_bias(tf["240"])
    candidates: list[Signal] = []
    for direction in ("LONG", "SHORT"):
        ts, level = turtle_soup(tf["15"], direction)
        mss = market_structure_shift(tf["5"], direction)
        fvg, lo, hi = latest_fvg(tf["5"], direction)
        model = mmxm_model(tf["60"], direction)
        score = 0
        aligned = (direction == "LONG" and bias == "BULLISH") or (direction == "SHORT" and bias == "BEARISH")
        score += 20 if aligned else 8 if bias == "NEUTRAL" else 0
        score += 20 if model != "NONE" else 0
        score += 25 if ts else 0
        score += 20 if mss else 0
        score += 15 if fvg else 0
        stop = target = None
        if ts and level is not None:
            if direction == "SHORT":
                stop = float(tf["15"].high.iloc[-1])
                target = float(tf["60"].low.iloc[-24:].min())
            else:
                stop = float(tf["15"].low.iloc[-1])
                target = float(tf["60"].high.iloc[-24:].max())
        candidates.append(Signal(symbol, direction, score, bias, model, ts, mss, fvg, lo, hi, stop, target, level))
    best = max(candidates, key=lambda x: x.score)
    if best.score < 40:
        best.direction = "NONE"
    return best
