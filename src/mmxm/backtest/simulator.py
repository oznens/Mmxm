"""Tek bir trade-call için walk-forward simülasyon.

Çıktı: TradeResult — entry, hit_time, hit_price, R-multiple, MAE, MFE.

Kurallar:
- LONG: TP hit if bar.high >= TP; SL hit if bar.low <= SL.
- SHORT: TP hit if bar.low <= TP; SL hit if bar.high >= SL.
- Aynı bar'da ikisi de hit ederse → konservatif: SL önce hit (gerçek
  intra-bar sırası bilinmiyor, kötü senaryo).
- Multi-TP: TP1 hit → kayıt; trade devam ederse TP2/TP3 ararız.
- Entry triggering: entry verilmiş ama henüz hit etmemiş ise ilk bar'larda
  bekleriz (limit order modeli). max_wait_bars sonra "no_entry" kapatırız.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from pydantic import BaseModel

from mmxm.parsing.schema import Side
from mmxm.patterns.schema import TradeCallRecord


class TradeOutcome:
    TP = "tp"
    SL = "sl"
    OPEN = "open"
    NO_ENTRY = "no_entry"
    SKIPPED = "skipped"


class TradeResult(BaseModel):
    """Tek bir trade-call için simülasyon sonucu."""

    post_id: str
    symbol: str
    side: Side
    posted_at: datetime
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: list[float] = []

    outcome: str  # tp / sl / open / no_entry / skipped
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    tp_hit_index: Optional[int] = None  # hangi TP (0-indexed) hit oldu

    r_multiple: float = 0.0
    bars_to_exit: Optional[int] = None
    mae: Optional[float] = None  # max adverse excursion (R cinsinden, negatif)
    mfe: Optional[float] = None  # max favorable excursion (R cinsinden, pozitif)

    note: Optional[str] = None


def _r_distance(entry: float, sl: float) -> float:
    return abs(entry - sl)


def simulate_trade(
    trade: TradeCallRecord,
    ohlcv: pd.DataFrame,
    *,
    max_hold_days: int = 90,
    max_wait_for_entry_bars: int = 24,
    entry_mode: str = "at_market",
) -> TradeResult:
    """Bir TradeCallRecord'u OHLCV üzerinde simüle et.

    entry_mode:
      - "at_market" (default): trader post attığında işleme zaten girmiş varsay;
        posted_at sonrası ilk bar'ın open fiyatından entry. Declared SL/TP'ler
        olduğu gibi kullanılır.
      - "limit": fiyat declared entry'ye gelmeyi bekle (limit order modeli).
        max_wait_for_entry_bars içinde hit olmazsa NO_ENTRY.
    """
    # Eksik veri kontrolü
    if trade.entry is None or trade.stop_loss is None or not trade.targets:
        return TradeResult(
            post_id=trade.post_id,
            symbol=trade.symbol,
            side=trade.side,
            posted_at=trade.posted_at,
            entry_price=trade.entry,
            stop_loss=trade.stop_loss,
            targets=trade.targets,
            outcome=TradeOutcome.SKIPPED,
            note="eksik entry/SL/TP",
        )

    side = trade.side
    if side == Side.UNKNOWN:
        return TradeResult(
            post_id=trade.post_id,
            symbol=trade.symbol,
            side=side,
            posted_at=trade.posted_at,
            outcome=TradeOutcome.SKIPPED,
            note="side=unknown",
        )

    # SL/TP yön tutarlılığı (jaxiwnl21'in BTC post #7 gibi yön karışıklığını yakala)
    entry = float(trade.entry)
    sl = float(trade.stop_loss)
    tps = sorted(float(t) for t in trade.targets)
    if side == Side.LONG:
        if not (sl < entry < min(tps)):
            return TradeResult(
                post_id=trade.post_id,
                symbol=trade.symbol,
                side=side,
                posted_at=trade.posted_at,
                entry_price=entry,
                stop_loss=sl,
                targets=tps,
                outcome=TradeOutcome.SKIPPED,
                note=f"long tutarsız: SL={sl} entry={entry} TP={tps}",
            )
        # LONG için targets entry'den büyük olmalı, sıralı
    else:  # SHORT
        tps = sorted(tps, reverse=True)  # SHORT için TP1 en yüksek (entry'ye yakın)
        if not (sl > entry > max(tps)):
            return TradeResult(
                post_id=trade.post_id,
                symbol=trade.symbol,
                side=side,
                posted_at=trade.posted_at,
                entry_price=entry,
                stop_loss=sl,
                targets=tps,
                outcome=TradeOutcome.SKIPPED,
                note=f"short tutarsız: SL={sl} entry={entry} TP={tps}",
            )

    risk = _r_distance(entry, sl)
    if risk == 0:
        return TradeResult(
            post_id=trade.post_id, symbol=trade.symbol, side=side,
            posted_at=trade.posted_at, outcome=TradeOutcome.SKIPPED,
            note="risk=0 (entry==SL)",
        )

    # Posted_at sonrası bar'ları al
    posted = trade.posted_at
    if posted.tzinfo is None:
        from datetime import timezone as _tz
        posted = posted.replace(tzinfo=_tz.utc)
    deadline = posted + timedelta(days=max_hold_days)
    window = ohlcv.loc[(ohlcv.index >= posted) & (ohlcv.index <= deadline)]
    if window.empty:
        return TradeResult(
            post_id=trade.post_id, symbol=trade.symbol, side=side,
            posted_at=trade.posted_at, entry_price=entry, stop_loss=sl, targets=tps,
            outcome=TradeOutcome.SKIPPED, note="window'da OHLCV yok",
        )

    # Entry tetikleme
    actual_entry: float
    entry_idx: Optional[int] = None
    if entry_mode == "at_market":
        # Post sonrası ilk bar'ın open'ından gir
        entry_idx = 0
        actual_entry = float(window.iloc[0]["open"])
        # SL/TP yönü hâlâ trader'ın declared seviyeleri; actual_entry farklı olabilir.
        # Risk'i actual_entry-SL ile hesaplarız (gerçekçi).
        if side == Side.LONG and actual_entry <= sl:
            # Open zaten SL'in altında — geçersiz setup
            return TradeResult(
                post_id=trade.post_id, symbol=trade.symbol, side=side,
                posted_at=trade.posted_at, entry_price=actual_entry, stop_loss=sl, targets=tps,
                outcome=TradeOutcome.SKIPPED,
                note=f"at-market open {actual_entry} zaten SL {sl} altında",
            )
        if side == Side.SHORT and actual_entry >= sl:
            return TradeResult(
                post_id=trade.post_id, symbol=trade.symbol, side=side,
                posted_at=trade.posted_at, entry_price=actual_entry, stop_loss=sl, targets=tps,
                outcome=TradeOutcome.SKIPPED,
                note=f"at-market open {actual_entry} zaten SL {sl} üstünde",
            )
        risk = _r_distance(actual_entry, sl)
    else:
        # limit order: fiyat declared entry'ye gelene dek bekle
        for i, (ts, row) in enumerate(window.iterrows()):
            if row["low"] <= entry <= row["high"]:
                entry_idx = i
                break
            if i >= max_wait_for_entry_bars:
                break
        if entry_idx is None:
            return TradeResult(
                post_id=trade.post_id, symbol=trade.symbol, side=side,
                posted_at=trade.posted_at, entry_price=entry, stop_loss=sl, targets=tps,
                outcome=TradeOutcome.NO_ENTRY,
                note=f"entry {entry} fiyata {max_wait_for_entry_bars} bar'da ulaşılmadı",
            )
        actual_entry = entry

    entry_time = window.index[entry_idx]
    post_entry = window.iloc[entry_idx + 1:]
    if post_entry.empty:
        return TradeResult(
            post_id=trade.post_id, symbol=trade.symbol, side=side,
            posted_at=trade.posted_at, entry_price=actual_entry, stop_loss=sl, targets=tps,
            outcome=TradeOutcome.OPEN, entry_time=entry_time,
            note="entry sonrası veri yok",
        )

    mae_r = 0.0
    mfe_r = 0.0

    for j, (ts, row) in enumerate(post_entry.iterrows()):
        high, low = float(row["high"]), float(row["low"])
        if side == Side.LONG:
            adverse = (low - actual_entry) / risk
            favorable = (high - actual_entry) / risk
        else:
            adverse = (actual_entry - high) / risk
            favorable = (actual_entry - low) / risk
        mae_r = min(mae_r, adverse)
        mfe_r = max(mfe_r, favorable)

        sl_hit = False
        tp_hit_idx: Optional[int] = None
        if side == Side.LONG:
            sl_hit = low <= sl
            for k, tp in enumerate(tps):
                if high >= tp:
                    tp_hit_idx = k
                    break
        else:
            sl_hit = high >= sl
            for k, tp in enumerate(tps):
                if low <= tp:
                    tp_hit_idx = k
                    break

        if sl_hit and tp_hit_idx is not None:
            return _make_result(trade, side, actual_entry, sl, tps, entry_time, ts, sl,
                                outcome=TradeOutcome.SL, tp_idx=None,
                                bars=j + 1, risk=risk, mae=mae_r, mfe=mfe_r,
                                note="SL ve TP aynı bar — SL kabul")
        if sl_hit:
            return _make_result(trade, side, actual_entry, sl, tps, entry_time, ts, sl,
                                outcome=TradeOutcome.SL, tp_idx=None,
                                bars=j + 1, risk=risk, mae=mae_r, mfe=mfe_r)
        if tp_hit_idx is not None:
            tp_price = tps[tp_hit_idx]
            return _make_result(trade, side, actual_entry, sl, tps, entry_time, ts, tp_price,
                                outcome=TradeOutcome.TP, tp_idx=tp_hit_idx,
                                bars=j + 1, risk=risk, mae=mae_r, mfe=mfe_r)

    last_close = float(post_entry["close"].iloc[-1])
    if side == Side.LONG:
        r_now = (last_close - actual_entry) / risk
    else:
        r_now = (actual_entry - last_close) / risk
    return TradeResult(
        post_id=trade.post_id, symbol=trade.symbol, side=side,
        posted_at=trade.posted_at, entry_price=actual_entry, stop_loss=sl, targets=tps,
        outcome=TradeOutcome.OPEN, entry_time=entry_time,
        exit_time=post_entry.index[-1], exit_price=last_close,
        r_multiple=round(r_now, 3), bars_to_exit=len(post_entry),
        mae=round(mae_r, 3), mfe=round(mfe_r, 3),
        note=f"max_hold_days={max_hold_days} doldu",
    )


def _make_result(
    trade: TradeCallRecord, side: Side, entry: float, sl: float, tps: list[float],
    entry_time: datetime, exit_time: datetime, exit_price: float,
    *, outcome: str, tp_idx: Optional[int], bars: int, risk: float,
    mae: float, mfe: float, note: Optional[str] = None,
) -> TradeResult:
    if side == Side.LONG:
        r = (exit_price - entry) / risk
    else:
        r = (entry - exit_price) / risk
    return TradeResult(
        post_id=trade.post_id, symbol=trade.symbol, side=side,
        posted_at=trade.posted_at, entry_price=entry, stop_loss=sl, targets=tps,
        outcome=outcome, entry_time=entry_time, exit_time=exit_time, exit_price=exit_price,
        tp_hit_index=tp_idx, r_multiple=round(r, 3), bars_to_exit=bars,
        mae=round(mae, 3), mfe=round(mfe, 3), note=note,
    )
