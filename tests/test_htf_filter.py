"""HTF bias filter unit testleri."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from mmxm.parsing.schema import Side
from mmxm.patterns.schema import TradeCallRecord
from mmxm.strategies.htf_filter import (
    HTFBias,
    compute_bias,
    filter_signals_by_htf_bias,
)


def _htf_bars(start: datetime, closes: list[float], tf_days: int = 1) -> pd.DataFrame:
    """Sadece close değişen daily bar serisi (open=high=low=close)."""
    rows = []
    for i, c in enumerate(closes):
        ts = start + timedelta(days=tf_days * i)
        rows.append({"ts": ts, "open": c, "high": c, "low": c, "close": c, "volume": 1.0})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def _sig(side: Side, ts: datetime, post_id: str = "s") -> TradeCallRecord:
    return TradeCallRecord(
        post_id=post_id, handle="STRAT", posted_at=ts,
        symbol="BTC/USDT", side=side,
        entry=100.0, stop_loss=99.0, targets=[102.0],
        confidence=0.5, rationale="test",
    )


def test_compute_bias_ma_cross_bullish():
    """Yükselen seri → fast > slow → bullish."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = list(range(100, 130))  # düz yükseliş
    df = _htf_bars(start, closes)
    bias = compute_bias(df, method="ma_cross", fast=3, slow=10)
    # Son birkaç bar tüm bullish olmalı
    assert bias.iloc[-1] == HTFBias.BULLISH.value


def test_compute_bias_ma_cross_bearish():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = list(range(130, 100, -1))
    df = _htf_bars(start, closes)
    bias = compute_bias(df, method="ma_cross", fast=3, slow=10)
    assert bias.iloc[-1] == HTFBias.BEARISH.value


def test_filter_keeps_long_in_bullish_htf():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = list(range(100, 140))  # bullish HTF
    htf = _htf_bars(start, closes)
    # Sinyal bir noktada
    sig_ts = start + timedelta(days=30, hours=5)
    signals = [_sig(Side.LONG, sig_ts), _sig(Side.SHORT, sig_ts, post_id="s2")]
    filtered = filter_signals_by_htf_bias(signals, htf, method="ma_cross", fast=3, slow=10)
    sides = [s.side for s in filtered]
    assert Side.LONG in sides
    assert Side.SHORT not in sides


def test_filter_keeps_short_in_bearish_htf():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = list(range(140, 100, -1))  # bearish HTF
    htf = _htf_bars(start, closes)
    sig_ts = start + timedelta(days=30, hours=5)
    signals = [_sig(Side.LONG, sig_ts), _sig(Side.SHORT, sig_ts, post_id="s2")]
    filtered = filter_signals_by_htf_bias(signals, htf, method="ma_cross", fast=3, slow=10)
    sides = [s.side for s in filtered]
    assert Side.SHORT in sides
    assert Side.LONG not in sides


def test_neutral_htf_filters_everything_by_default():
    """Bias hesaplanamayan ilk bar'larda (NEUTRAL) sinyaller atlanır."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = [100.0] * 5  # sabit, bias yok
    htf = _htf_bars(start, closes)
    sig_ts = start + timedelta(days=2)  # MA henüz oluşmadı veya neutral
    signals = [_sig(Side.LONG, sig_ts), _sig(Side.SHORT, sig_ts, post_id="s2")]
    filtered = filter_signals_by_htf_bias(signals, htf, method="ma_cross", fast=3, slow=10)
    assert filtered == []


def test_neutral_passes_when_allow_neutral_true():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = [100.0] * 5
    htf = _htf_bars(start, closes)
    sig_ts = start + timedelta(days=2)
    signals = [_sig(Side.LONG, sig_ts)]
    filtered = filter_signals_by_htf_bias(
        signals, htf, method="ma_cross", fast=3, slow=10, allow_neutral=True
    )
    assert len(filtered) == 1


def test_signal_before_htf_data_is_dropped():
    """HTF data sinyalden sonra başlıyorsa sinyal düşürülür."""
    start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    htf = _htf_bars(start, list(range(100, 120)))
    early_sig = _sig(Side.LONG, datetime(2024, 1, 1, tzinfo=timezone.utc))
    filtered = filter_signals_by_htf_bias([early_sig], htf, method="ma_cross", fast=3, slow=10)
    assert filtered == []
