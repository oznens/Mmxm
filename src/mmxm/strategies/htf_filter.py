"""HTF (Higher Timeframe) bias filtresi.

Klasik ICT/SMC yaklaşımı:
- HTF (1D / 4H) üstünde piyasa "bias"ını belirle (bullish / bearish / neutral)
- LTF (1H / 5m) sinyallerinden yalnızca HTF bias ile uyumlu olanlara izin ver
- Beklenen etki: sinyal sayısı ciddi şekilde düşer, PF artar (gürültü filtresi)

İki bias method:
- "ma_cross": fast MA > slow MA → bullish (klasik trend-following)
- "ma_slope": slow MA'nın N-bar slope'u > 0 → bullish (smoothed momentum)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import pandas as pd

from mmxm.parsing.schema import Side
from mmxm.patterns.schema import TradeCallRecord


class HTFBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


def compute_bias(
    htf_ohlcv: pd.DataFrame,
    method: str = "ma_cross",
    fast: int = 9,
    slow: int = 21,
    slope_lookback: int = 5,
) -> pd.Series:
    """HTF bar başına bias hesabı.

    Returns: Series, index=HTF timestamp, values=HTFBias (str).
    NaN dönmez — başlangıçtaki yeterli veri yokken NEUTRAL döner.
    """
    if htf_ohlcv.empty:
        return pd.Series([], dtype=str, name="bias")

    close = htf_ohlcv["close"]
    if method == "ma_cross":
        fast_ma = close.rolling(fast).mean()
        slow_ma = close.rolling(slow).mean()
        bias = pd.Series(HTFBias.NEUTRAL.value, index=close.index, dtype=str)
        bias[fast_ma > slow_ma] = HTFBias.BULLISH.value
        bias[fast_ma < slow_ma] = HTFBias.BEARISH.value
        return bias
    elif method == "ma_slope":
        ma = close.rolling(slow).mean()
        slope = ma - ma.shift(slope_lookback)
        bias = pd.Series(HTFBias.NEUTRAL.value, index=close.index, dtype=str)
        bias[slope > 0] = HTFBias.BULLISH.value
        bias[slope < 0] = HTFBias.BEARISH.value
        return bias
    elif method == "close_above_ma":
        ma = close.rolling(slow).mean()
        bias = pd.Series(HTFBias.NEUTRAL.value, index=close.index, dtype=str)
        bias[close > ma] = HTFBias.BULLISH.value
        bias[close < ma] = HTFBias.BEARISH.value
        return bias
    else:
        raise ValueError(f"bilinmeyen bias method: {method}")


def filter_signals_by_htf_bias(
    signals: list[TradeCallRecord],
    htf_ohlcv: pd.DataFrame,
    method: str = "ma_cross",
    allow_neutral: bool = False,
    **bias_kwargs,
) -> list[TradeCallRecord]:
    """LTF sinyallerini HTF bias'la uyuştur.

    - LONG sinyali sadece HTF bullish ise geçer.
    - SHORT sinyali sadece HTF bearish ise geçer.
    - HTF neutral ise allow_neutral=False default'unda her iki yönde de elenir.
    """
    if htf_ohlcv.empty or not signals:
        return []

    bias_series = compute_bias(htf_ohlcv, method=method, **bias_kwargs)
    out: list[TradeCallRecord] = []
    for sig in signals:
        valid = bias_series.index[bias_series.index <= sig.posted_at]
        if len(valid) == 0:
            continue
        bias = bias_series.loc[valid[-1]]

        if sig.side == Side.LONG:
            if bias == HTFBias.BULLISH.value:
                out.append(sig)
            elif bias == HTFBias.NEUTRAL.value and allow_neutral:
                out.append(sig)
        elif sig.side == Side.SHORT:
            if bias == HTFBias.BEARISH.value:
                out.append(sig)
            elif bias == HTFBias.NEUTRAL.value and allow_neutral:
                out.append(sig)

    return out
