"""Turtle Soup detector — Dreyko / wuipx tarzı.

Mantık (klasik Turtle Soup'tan adapte):
1. Son `lookback` bar içinde swing low (ya da high) belirle.
2. Mevcut bar swing low'u aşağı kırarsa (low < swing_low - sweep_min_pct)
3. AYNI bar'ın close'u swing low'un üstüne reclaim ederse (close > swing_low + reclaim_min_pct)
4. → BULLISH TURTLE SOUP: long entry o bar'ın close'unda
   - SL: o bar'ın low'u - sl_buffer_pct
   - TP: entry + target_r * risk (sabit R) — opsiyonel: swing_high target
5. BEARISH için aynı mantık aynalanır (swing high kırılıp reclaim'lenir).

Debounce: ardışık sinyaller yaratmamak için son sinyalden sonra
`debounce_bars` kadar bekleriz.

Parametre defaultları crypto/forex için ılımlı; her enstrümana göre tuning gerekebilir.
"""

from __future__ import annotations

import pandas as pd

from mmxm.parsing.schema import KeyLevel, LevelSource, Side
from mmxm.patterns.schema import TradeCallRecord
from mmxm.strategies.base import Strategy


class TurtleSoupStrategy(Strategy):
    name = "turtle_soup"

    def __init__(
        self,
        lookback: int = 20,
        sweep_min_pct: float = 0.001,        # %0.1 — likidite süpürme min mesafe
        reclaim_min_pct: float = 0.0005,     # %0.05 — close'un swing seviyesinin üstüne dönmesi
        sl_buffer_pct: float = 0.002,        # %0.2 — wick'in dışına SL koy
        target_r: float = 3.0,               # sabit R çoklayıcı (TP = entry + R*risk)
        debounce_bars: int = 10,
        confidence: float = 0.65,
    ):
        self.lookback = lookback
        self.sweep_min_pct = sweep_min_pct
        self.reclaim_min_pct = reclaim_min_pct
        self.sl_buffer_pct = sl_buffer_pct
        self.target_r = target_r
        self.debounce_bars = debounce_bars
        self.confidence = confidence

    def scan(self, symbol: str, ohlcv: pd.DataFrame) -> list[TradeCallRecord]:
        if len(ohlcv) <= self.lookback + 1:
            return []

        # Önceki N bar'ın min/max (current bar dahil değil)
        swing_low = ohlcv["low"].shift(1).rolling(self.lookback).min()
        swing_high = ohlcv["high"].shift(1).rolling(self.lookback).max()

        results: list[TradeCallRecord] = []
        last_signal_idx = -self.debounce_bars

        for i in range(self.lookback, len(ohlcv)):
            if i - last_signal_idx < self.debounce_bars:
                continue

            bar = ohlcv.iloc[i]
            slo = float(swing_low.iloc[i])
            shi = float(swing_high.iloc[i])
            o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])

            if pd.isna(slo) or pd.isna(shi):
                continue

            # BULLISH TS
            broke_below = l < slo * (1 - self.sweep_min_pct)
            reclaimed_up = c > slo * (1 + self.reclaim_min_pct)
            if broke_below and reclaimed_up:
                entry = c
                sl = l * (1 - self.sl_buffer_pct)
                risk = entry - sl
                if risk > 0:
                    tp = entry + risk * self.target_r
                    results.append(self._make_record(
                        symbol=symbol, side=Side.LONG, ts=bar.name,
                        entry=entry, sl=sl, tps=[tp],
                        swept_level=slo, wick=l,
                        rationale=f"Bullish TS: low {l:.6g} swing_low {slo:.6g} altına süpürdü, close {c:.6g} reclaim",
                    ))
                    last_signal_idx = i
                    continue

            # BEARISH TS
            broke_above = h > shi * (1 + self.sweep_min_pct)
            reclaimed_down = c < shi * (1 - self.reclaim_min_pct)
            if broke_above and reclaimed_down:
                entry = c
                sl = h * (1 + self.sl_buffer_pct)
                risk = sl - entry
                if risk > 0:
                    tp = entry - risk * self.target_r
                    results.append(self._make_record(
                        symbol=symbol, side=Side.SHORT, ts=bar.name,
                        entry=entry, sl=sl, tps=[tp],
                        swept_level=shi, wick=h,
                        rationale=f"Bearish TS: high {h:.6g} swing_high {shi:.6g} üstüne süpürdü, close {c:.6g} reclaim",
                    ))
                    last_signal_idx = i

        return results

    def _make_record(
        self,
        symbol: str,
        side: Side,
        ts,
        entry: float,
        sl: float,
        tps: list[float],
        swept_level: float,
        wick: float,
        rationale: str,
    ) -> TradeCallRecord:
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        return TradeCallRecord(
            post_id=f"strat_ts_{symbol.replace('/', '_')}_{ts_iso}",
            handle="STRATEGY_TURTLE_SOUP",
            posted_at=ts,
            symbol=symbol,
            side=side,
            entry=entry,
            stop_loss=sl,
            targets=tps,
            timeframes=[],
            concepts=["turtle_soup", "liquidity_sweep"],
            matched_setups=["turtle_soup", "liquidity_sweep_reversal"],
            key_levels=[
                KeyLevel(price=swept_level, label="swept_level", source=LevelSource.INFERRED),
                KeyLevel(price=wick, label="ts_wick", source=LevelSource.INFERRED),
                KeyLevel(price=entry, label="entry", source=LevelSource.INFERRED),
                KeyLevel(price=sl, label="stop_loss", source=LevelSource.INFERRED),
                *[KeyLevel(price=t, label=f"tp{i+1}", source=LevelSource.INFERRED) for i, t in enumerate(tps)],
            ],
            confidence=self.confidence,
            rationale=rationale,
        )
