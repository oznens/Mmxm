"""Walk-forward simulator unit testleri — sentetik OHLCV ile."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from mmxm.backtest.simulator import TradeOutcome, simulate_trade
from mmxm.parsing.schema import Side
from mmxm.patterns.schema import TradeCallRecord


def _bars(start: datetime, ohlc: list[tuple[float, float, float, float]], tf_minutes: int = 60) -> pd.DataFrame:
    """Build OHLCV DataFrame from (o,h,l,c) tuples."""
    rows = []
    for i, (o, h, l, c) in enumerate(ohlc):
        ts = start + timedelta(minutes=tf_minutes * i)
        rows.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": 1.0})
    df = pd.DataFrame(rows).set_index("ts")
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def _trade(side: Side, entry: float, sl: float, targets: list[float], **kw) -> TradeCallRecord:
    return TradeCallRecord(
        post_id=kw.pop("post_id", "test"),
        handle="test",
        posted_at=kw.pop("posted_at", datetime(2024, 1, 1, tzinfo=timezone.utc)),
        symbol="BTC/USDT",
        side=side,
        entry=entry,
        stop_loss=sl,
        targets=targets,
        confidence=0.9,
        rationale="test",
        **kw,
    )


# --- LONG senaryoları ---


def test_long_tp_hit_clean():
    """Entry hit → fiyat yukarı → TP hit. R = 2."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # bar0: entry 100 hit (low<=100<=high); bar1: high reaches 120 (TP)
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 120, 100, 118)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.TP
    assert r.r_multiple == 2.0  # (120-100)/(100-90)
    assert r.tp_hit_index == 0


def test_long_sl_hit():
    """Entry hit → fiyat aşağı → SL hit. R = -1."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 102, 89, 92)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SL
    assert r.r_multiple == -1.0


def test_long_same_bar_sl_and_tp_conservative_sl_wins():
    """Aynı bar SL+TP → konservatif SL."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 125, 85, 110)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SL
    assert r.note and "aynı bar" in r.note


def test_long_no_entry_within_wait_limit_mode():
    """Limit mode: entry hiç ulaşılmaz → no_entry."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(110, 115, 108, 112)] * 5)
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, max_wait_for_entry_bars=3, entry_mode="limit")
    assert r.outcome == TradeOutcome.NO_ENTRY


def test_at_market_skips_when_open_below_sl_long():
    """at_market: open zaten SL'in altında → SKIPPED."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(85, 95, 80, 92)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="at_market")
    assert r.outcome == TradeOutcome.SKIPPED


def test_at_market_uses_open_as_entry():
    """at_market: ilk bar open entry; SL/TP declared."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(102, 105, 100, 103), (103, 121, 102, 119)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="at_market")
    assert r.outcome == TradeOutcome.TP
    assert r.entry_price == 102.0
    assert r.r_multiple == pytest.approx(1.5, abs=0.01)


def test_long_tp1_hit_with_multi_tp():
    """Multi-TP: TP1 hit, kayıt orada kapanır."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 121, 100, 119)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120, 130], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.TP
    assert r.tp_hit_index == 0
    assert r.exit_price == 120


# --- SHORT senaryoları ---


def test_short_tp_hit():
    """SHORT: entry 100, SL 110, TP 80 → fiyat 80'e iner."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 100, 78, 82)])
    trade = _trade(Side.SHORT, entry=100, sl=110, targets=[80], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.TP
    assert r.r_multiple == 2.0  # (100-80)/(110-100)


def test_short_sl_hit():
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 112, 99, 111)])
    trade = _trade(Side.SHORT, entry=100, sl=110, targets=[80], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SL
    assert r.r_multiple == -1.0


# --- Yön tutarsızlığı / skipped ---


def test_skipped_when_long_sl_above_entry():
    """LONG'ta SL > entry mantıksız → skipped."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100)])
    trade = _trade(Side.LONG, entry=100, sl=110, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SKIPPED
    assert r.note and "tutarsız" in r.note


def test_skipped_when_short_levels_wrong():
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100)])
    # SHORT entry=100, SL=90 (entry'nin altı, yanlış), TP=80
    trade = _trade(Side.SHORT, entry=100, sl=90, targets=[80], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SKIPPED


def test_skipped_when_missing_sl():
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100)])
    trade = _trade(Side.LONG, entry=100, sl=None, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SKIPPED


def test_skipped_when_side_unknown():
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ohlcv = _bars(posted, [(99, 101, 98, 100)])
    trade = _trade(Side.UNKNOWN, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.SKIPPED


# --- MAE/MFE ---


def test_mae_mfe_calculated():
    """MFE: max'a kadar yükseldi, sonra düştü; MAE: önce SL'ye yaklaştı."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # entry 100, SL 90, TP 120
    # bar0: entry hit; bar1: high=115 (1.5R MFE), low=95 (-0.5R MAE); bar2: TP hit
    ohlcv = _bars(posted, [(99, 101, 98, 100), (100, 115, 95, 110), (110, 121, 108, 120)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[120], posted_at=posted)
    r = simulate_trade(trade, ohlcv, entry_mode="limit")
    assert r.outcome == TradeOutcome.TP
    # MAE = (95-100)/10 = -0.5 (en kötü adverse)
    assert r.mae is not None and r.mae <= -0.4
    # MFE = at TP bar high=121, (121-100)/10 = 2.1; or before TP bar 115 = 1.5. Final at TP bar = 2.1
    assert r.mfe is not None and r.mfe >= 1.5


# --- Window boş / kapsama dışı ---


def test_open_when_max_hold_reached():
    """Ne TP ne SL hit → open, partial R."""
    posted = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Sadece 1 bar var (entry), sonrası yok; max_hold içinde
    ohlcv = _bars(posted, [(99, 101, 98, 100)])
    trade = _trade(Side.LONG, entry=100, sl=90, targets=[200], posted_at=posted)
    r = simulate_trade(trade, ohlcv, max_hold_days=90)
    # Entry sonrası bar yok → "entry sonrası veri yok" notuyla OPEN
    assert r.outcome == TradeOutcome.OPEN
