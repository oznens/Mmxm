from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd


@dataclass(slots=True)
class StructureState:
    bos: bool
    mss: bool
    cisd: bool
    displacement: bool
    swing_level: float | None
    displacement_ratio: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df.close.shift(1)
    return pd.concat(
        [
            df.high - df.low,
            (df.high - prev_close).abs(),
            (df.low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < period + 1:
        return 0.0
    value = _true_range(df).rolling(period).mean().iloc[-1]
    return float(value) if pd.notna(value) else 0.0


def displacement(df: pd.DataFrame, direction: str, atr_mult: float = 1.25) -> tuple[bool, float]:
    if len(df) < 16:
        return False, 0.0
    c = df.iloc[-1]
    a = atr(df.iloc[:-1])
    if a <= 0:
        return False, 0.0
    body = abs(float(c.close - c.open))
    ratio = body / a
    directional = c.close > c.open if direction == "LONG" else c.close < c.open
    close_location = (
        (c.close - c.low) / max(c.high - c.low, 1e-12)
        if direction == "LONG"
        else (c.high - c.close) / max(c.high - c.low, 1e-12)
    )
    return bool(directional and ratio >= atr_mult and close_location >= 0.65), float(ratio)


def _pivot_high(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[tuple[int, float]]:
    out = []
    highs = df.high.to_numpy()
    for i in range(left, len(df) - right):
        if highs[i] > highs[i-left:i].max() and highs[i] >= highs[i+1:i+1+right].max():
            out.append((i, float(highs[i])))
    return out


def _pivot_low(df: pd.DataFrame, left: int = 2, right: int = 2) -> list[tuple[int, float]]:
    out = []
    lows = df.low.to_numpy()
    for i in range(left, len(df) - right):
        if lows[i] < lows[i-left:i].min() and lows[i] <= lows[i+1:i+1+right].min():
            out.append((i, float(lows[i])))
    return out


def cisd(df: pd.DataFrame, direction: str, lookback: int = 12) -> bool:
    """Close through the open of the most recent opposing candle cluster."""
    if len(df) < lookback + 1:
        return False
    prior = df.iloc[-(lookback + 1):-1]
    last = df.iloc[-1]
    if direction == "LONG":
        bearish = prior[prior.close < prior.open]
        if bearish.empty:
            return False
        level = float(bearish.open.iloc[-1])
        return bool(last.close > level and last.close > last.open)
    bullish = prior[prior.close > prior.open]
    if bullish.empty:
        return False
    level = float(bullish.open.iloc[-1])
    return bool(last.close < level and last.close < last.open)


def structure_state(df: pd.DataFrame, direction: str) -> StructureState:
    if len(df) < 20:
        return StructureState(False, False, False, False, None, None)
    work = df.iloc[-80:].reset_index(drop=True)
    last = work.iloc[-1]
    disp, ratio = displacement(work, direction)
    ci = cisd(work, direction)

    if direction == "LONG":
        pivots = _pivot_high(work.iloc[:-1])
        level = pivots[-1][1] if pivots else float(work.high.iloc[-12:-1].max())
        bos = bool(last.close > level)
    else:
        pivots = _pivot_low(work.iloc[:-1])
        level = pivots[-1][1] if pivots else float(work.low.iloc[-12:-1].min())
        bos = bool(last.close < level)

    # Scanner treats first decisive break after a liquidity event as MSS candidate.
    mss = bool(bos and disp)
    return StructureState(bos, mss, ci, disp, level, ratio)
