from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timedelta
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


@dataclass(slots=True)
class LiquidityMap:
    pdh: float | None = None
    pdl: float | None = None
    pwh: float | None = None
    pwl: float | None = None
    asia_high: float | None = None
    asia_low: float | None = None
    london_high: float | None = None
    london_low: float | None = None
    ny_high: float | None = None
    ny_low: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _with_dt(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "timestamp" in out.columns:
        dt = pd.to_datetime(out["timestamp"], utc=True)
    elif "time" in out.columns:
        dt = pd.to_datetime(out["time"], utc=True)
    elif isinstance(out.index, pd.DatetimeIndex):
        dt = pd.to_datetime(out.index, utc=True)
    else:
        raise ValueError("DataFrame needs timestamp/time column or DatetimeIndex")
    out = out.assign(_dt=dt)
    return out


def _range(df: pd.DataFrame) -> tuple[float | None, float | None]:
    if df.empty:
        return None, None
    return float(df.high.max()), float(df.low.min())


def _local_ts(d, hhmm: str) -> pd.Timestamp:
    return pd.Timestamp(f"{d.isoformat()} {hhmm}", tz=NY)


def daily_levels(df: pd.DataFrame, now: pd.Timestamp | None = None) -> tuple[float | None, float | None]:
    x = _with_dt(df)
    now_utc = (now if now is not None else x._dt.iloc[-1]).tz_convert(UTC)
    day = now_utc.date()
    prev = day - timedelta(days=1)
    s = x[x._dt.dt.date == prev]
    return _range(s)


def weekly_levels(df: pd.DataFrame, now: pd.Timestamp | None = None) -> tuple[float | None, float | None]:
    x = _with_dt(df)
    now_utc = (now if now is not None else x._dt.iloc[-1]).tz_convert(UTC)
    monday = now_utc.date() - timedelta(days=now_utc.weekday())
    prev_monday = monday - timedelta(days=7)
    s = x[(x._dt.dt.date >= prev_monday) & (x._dt.dt.date < monday)]
    return _range(s)


def session_levels(df: pd.DataFrame, session: str, now: pd.Timestamp | None = None) -> tuple[float | None, float | None]:
    """ICT-oriented crypto session ranges in New York local time.

    Asia:    20:00 previous calendar day -> 00:00
    London:  02:00 -> 05:00
    NewYork: 07:00 -> 10:00
    """
    x = _with_dt(df)
    x = x.assign(_ny=x._dt.dt.tz_convert(NY))
    now_ny = (now if now is not None else x._dt.iloc[-1]).tz_convert(NY)
    d = now_ny.date()

    if session == "asia":
        start = _local_ts(d - timedelta(days=1), "20:00")
        end = _local_ts(d, "00:00")
    elif session == "london":
        start = _local_ts(d, "02:00")
        end = _local_ts(d, "05:00")
    elif session == "ny":
        start = _local_ts(d, "07:00")
        end = _local_ts(d, "10:00")
    else:
        raise ValueError(f"unknown session: {session}")

    s = x[(x._ny >= start) & (x._ny < end)]
    return _range(s)


def build_liquidity_map(df: pd.DataFrame) -> LiquidityMap:
    pdh, pdl = daily_levels(df)
    pwh, pwl = weekly_levels(df)
    ah, al = session_levels(df, "asia")
    lh, ll = session_levels(df, "london")
    nh, nl = session_levels(df, "ny")
    return LiquidityMap(pdh, pdl, pwh, pwl, ah, al, lh, ll, nh, nl)


def nearest_draw(price: float, direction: str, m: LiquidityMap) -> tuple[str | None, float | None]:
    levels = m.to_dict()
    if direction == "LONG":
        valid = [
            (k, float(v))
            for k, v in levels.items()
            if v is not None and float(v) > price and (k.endswith("high") or k in {"pdh", "pwh"})
        ]
        return min(valid, key=lambda kv: kv[1], default=(None, None))
    valid = [
        (k, float(v))
        for k, v in levels.items()
        if v is not None and float(v) < price and (k.endswith("low") or k in {"pdl", "pwl"})
    ]
    return max(valid, key=lambda kv: kv[1], default=(None, None))
