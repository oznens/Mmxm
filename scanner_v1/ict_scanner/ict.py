from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

import pandas as pd

from .confluence import latest_fvg, latest_ifvg, order_block, premium_discount, rr, smt_divergence
from .liquidity import LiquidityMap, build_liquidity_map, nearest_draw
from .structure import StructureState, structure_state

Direction = Literal["LONG", "SHORT", "NONE"]


@dataclass(slots=True)
class Signal:
    symbol: str
    direction: Direction
    score: int
    grade: str
    state: str
    htf_bias: str
    mmxm: str
    turtle_soup: bool
    raid_name: str | None
    raid_level: float | None
    mss: bool
    cisd: bool
    displacement: bool
    displacement_ratio: float | None
    fvg: bool
    ifvg: bool
    order_block: bool
    smt: bool
    pd_zone: str
    ote_low: float | None
    ote_high: float | None
    entry_low: float | None
    entry_high: float | None
    stop: float | None
    tp1: float | None
    tp2: float | None
    tp3: float | None
    rr_tp1: float | None
    rr_tp2: float | None
    rr_tp3: float | None
    draw_name: str | None
    liquidity: dict
    invalidation: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def htf_bias(df4h: pd.DataFrame) -> str:
    if len(df4h) < 40:
        return "NEUTRAL"
    recent = df4h.iloc[-30:]
    hi, lo = float(recent.high.max()), float(recent.low.min())
    eq = (hi + lo) / 2
    last = recent.iloc[-1]
    older, newer = recent.iloc[:15], recent.iloc[15:]
    hh = newer.high.max() > older.high.max()
    hl = newer.low.min() > older.low.min()
    ll = newer.low.min() < older.low.min()
    lh = newer.high.max() < older.high.max()
    if last.close > eq and (hh or hl):
        return "BULLISH"
    if last.close < eq and (ll or lh):
        return "BEARISH"
    return "NEUTRAL"


def mmxm_model(df1h: pd.DataFrame, direction: Direction) -> str:
    if len(df1h) < 48:
        return "NONE"
    x = df1h.iloc[-48:]
    q1, q2, q3, q4 = (x.iloc[i:i + 12] for i in range(0, 48, 12))
    if direction == "SHORT":
        engineered_high = q3.high.max() > max(q1.high.max(), q2.high.max())
        distribution = q4.close.iloc[-1] < q3.low.median()
        return "MMSM" if engineered_high and distribution else "NONE"
    engineered_low = q3.low.min() < min(q1.low.min(), q2.low.min())
    distribution = q4.close.iloc[-1] > q3.high.median()
    return "MMBM" if engineered_low and distribution else "NONE"


def _liquidity_candidates(m: LiquidityMap, direction: Direction) -> list[tuple[str, float]]:
    d = m.to_dict()
    if direction == "SHORT":
        names = ("pdh", "pwh", "asia_high", "london_high", "ny_high")
    else:
        names = ("pdl", "pwl", "asia_low", "london_low", "ny_low")
    return [(name, float(d[name])) for name in names if d.get(name) is not None]


def liquidity_raid(df15: pd.DataFrame, direction: Direction, m: LiquidityMap) -> tuple[bool, str | None, float | None]:
    if df15.empty:
        return False, None, None
    c = df15.iloc[-1]
    raids: list[tuple[str, float, float]] = []
    for name, level in _liquidity_candidates(m, direction):
        if direction == "SHORT" and c.high > level and c.close < level:
            raids.append((name, level, float(c.high - level)))
        elif direction == "LONG" and c.low < level and c.close > level:
            raids.append((name, level, float(level - c.low)))
    if not raids:
        return False, None, None
    # Prefer the deepest valid sweep when multiple session/HTF levels cluster.
    name, level, _ = max(raids, key=lambda x: x[2])
    return True, name, level


def _state(ts: bool, st: StructureState, fvg: bool) -> str:
    if not ts:
        return "WAITING_FOR_RAID"
    if not (st.mss or st.cisd):
        return "LIQUIDITY_SWEPT"
    if not fvg:
        return "MSS_CONFIRMED"
    return "ENTRY_READY"


def _grade(score: int) -> str:
    if score >= 85:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    return "NO_TRADE"


def _entry_zone(direction: Direction, fvg_zone: tuple[bool, float | None, float | None], ifvg_zone: tuple[bool, float | None, float | None], ob_zone: tuple[bool, float | None, float | None], ote: tuple[float | None, float | None]) -> tuple[float | None, float | None]:
    zones = []
    for ok, lo, hi in (fvg_zone, ifvg_zone, ob_zone):
        if ok and lo is not None and hi is not None:
            zones.append((float(min(lo, hi)), float(max(lo, hi))))
    if not zones:
        return None, None
    ote_lo, ote_hi = ote
    if ote_lo is not None and ote_hi is not None:
        overlaps = [(max(lo, ote_lo), min(hi, ote_hi)) for lo, hi in zones if max(lo, ote_lo) <= min(hi, ote_hi)]
        if overlaps:
            return overlaps[0]
    return zones[0]


def _targets(direction: Direction, price: float, m: LiquidityMap, df1h: pd.DataFrame) -> tuple[str | None, float | None, float | None, float | None]:
    draw_name, draw = nearest_draw(price, direction, m)
    if direction == "LONG":
        internal = float(df1h.high.iloc[-24:].quantile(0.75))
        external = float(df1h.high.iloc[-72:].max()) if len(df1h) >= 72 else float(df1h.high.max())
        vals = sorted({x for x in (internal, draw, external) if x is not None and x > price})
    else:
        internal = float(df1h.low.iloc[-24:].quantile(0.25))
        external = float(df1h.low.iloc[-72:].min()) if len(df1h) >= 72 else float(df1h.low.min())
        vals = sorted({x for x in (internal, draw, external) if x is not None and x < price}, reverse=True)
    vals = (vals + [None, None, None])[:3]
    return draw_name, vals[0], vals[1], vals[2]


def analyze_symbol(symbol: str, tf: dict[str, pd.DataFrame], benchmark_tf: dict[str, pd.DataFrame] | None = None) -> Signal:
    bias = htf_bias(tf["240"])
    liq = build_liquidity_map(tf["15"])
    candidates: list[Signal] = []

    for direction in ("LONG", "SHORT"):
        model = mmxm_model(tf["60"], direction)
        ts, raid_name, raid_level = liquidity_raid(tf["15"], direction, liq)
        st = structure_state(tf["5"], direction)
        fvg_zone = latest_fvg(tf["5"], direction)
        ifvg_zone = latest_ifvg(tf["5"], direction)
        ob_zone = order_block(tf["5"], direction)
        pd_state = premium_discount(tf["60"], direction)
        smt_state = smt_divergence(tf["15"], benchmark_tf["15"], direction) if benchmark_tf else None

        aligned = (direction == "LONG" and bias == "BULLISH") or (direction == "SHORT" and bias == "BEARISH")
        pd_ok = (direction == "LONG" and pd_state.zone == "DISCOUNT") or (direction == "SHORT" and pd_state.zone == "PREMIUM")

        score = 0
        score += 15 if aligned else 6 if bias == "NEUTRAL" else 0
        score += 15 if model != "NONE" else 0
        score += 20 if ts else 0
        score += 15 if st.mss else 8 if st.bos else 0
        score += 10 if st.cisd else 0
        score += 10 if st.displacement else 0
        score += 8 if fvg_zone[0] else 0
        score += 5 if ifvg_zone[0] else 0
        score += 4 if pd_ok else 0
        score += 5 if smt_state and smt_state.present else 0
        score = min(score, 100)

        entry_lo, entry_hi = _entry_zone(direction, fvg_zone, ifvg_zone, ob_zone, (pd_state.ote_low, pd_state.ote_high))
        entry = (entry_lo + entry_hi) / 2 if entry_lo is not None and entry_hi is not None else None

        stop = None
        if ts:
            stop = float(tf["15"].high.iloc[-1]) if direction == "SHORT" else float(tf["15"].low.iloc[-1])

        reference = entry if entry is not None else float(tf["5"].close.iloc[-1])
        draw_name, tp1, tp2, tp3 = _targets(direction, reference, liq, tf["60"])
        invalidation = None
        if stop is not None:
            invalidation = f"5M/15M acceptance {'above' if direction == 'SHORT' else 'below'} {stop:.8g}"

        candidates.append(
            Signal(
                symbol=symbol,
                direction=direction,
                score=score,
                grade=_grade(score),
                state=_state(ts, st, fvg_zone[0]),
                htf_bias=bias,
                mmxm=model,
                turtle_soup=ts,
                raid_name=raid_name,
                raid_level=raid_level,
                mss=st.mss,
                cisd=st.cisd,
                displacement=st.displacement,
                displacement_ratio=round(st.displacement_ratio, 2) if st.displacement_ratio is not None else None,
                fvg=fvg_zone[0],
                ifvg=ifvg_zone[0],
                order_block=ob_zone[0],
                smt=bool(smt_state.present) if smt_state else False,
                pd_zone=pd_state.zone,
                ote_low=pd_state.ote_low,
                ote_high=pd_state.ote_high,
                entry_low=entry_lo,
                entry_high=entry_hi,
                stop=stop,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                rr_tp1=rr(entry, stop, tp1),
                rr_tp2=rr(entry, stop, tp2),
                rr_tp3=rr(entry, stop, tp3),
                draw_name=draw_name,
                liquidity=liq.to_dict(),
                invalidation=invalidation,
            )
        )

    best = max(candidates, key=lambda x: x.score)
    if best.score < 40:
        best.direction = "NONE"
        best.grade = "NO_TRADE"
    return best
