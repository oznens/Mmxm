"""FVG (Fair Value Gap) Retest detector.

Wuipx'in "FVG mıknatıs etkisi" tezini ve Dreyko'nun "FVG geri test entry"
yaklaşımını koda çeviren strateji.

FVG tanımı (3-mum imbalance):
- BULLISH FVG: bar[i-2].high < bar[i].low → bar[i-1] hızlı aşağıdan yukarı
  gitti, ortada bir "gap" bıraktı. Gap zonu: [bar[i-2].high, bar[i].low].
- BEARISH FVG: bar[i-2].low > bar[i].high → tersi.

Entry mantığı:
- FVG oluşumu sonrası fiyat gap'e geri çekilirse → entry o yöne.
- Bullish FVG retest: price low FVG zone'una değdiğinde long.
- Bearish FVG retest: price high FVG zone'una değdiğinde short.
- SL: FVG'nin karşı kenarı + buffer.
- TP: sabit R çoklayıcı.

Parametreler:
- min_fvg_size_pct: çok küçük gap'leri ele (gürültü filtresi)
- max_age_bars: FVG kaç bar sonra "expire" olur (test edilmediyse)
- target_r: TP için R çoklayıcı
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from mmxm.parsing.schema import KeyLevel, LevelSource, Side
from mmxm.patterns.schema import TradeCallRecord
from mmxm.strategies.base import Strategy


@dataclass
class _PendingFVG:
    type: str  # "bullish" | "bearish"
    upper: float
    lower: float
    created_idx: int
    created_ts: any


class FVGRetestStrategy(Strategy):
    name = "fvg_retest"

    def __init__(
        self,
        min_fvg_size_pct: float = 0.002,    # %0.2 — min imbalance büyüklüğü
        max_age_bars: int = 50,             # FVG kaç bar sonra expire
        target_r: float = 2.0,
        sl_buffer_pct: float = 0.001,
        debounce_bars: int = 5,
        confidence: float = 0.6,
    ):
        self.min_fvg_size_pct = min_fvg_size_pct
        self.max_age_bars = max_age_bars
        self.target_r = target_r
        self.sl_buffer_pct = sl_buffer_pct
        self.debounce_bars = debounce_bars
        self.confidence = confidence

    def scan(self, symbol: str, ohlcv: pd.DataFrame) -> list[TradeCallRecord]:
        if len(ohlcv) < 3:
            return []

        results: list[TradeCallRecord] = []
        active: list[_PendingFVG] = []
        last_signal_idx = -self.debounce_bars

        for i in range(2, len(ohlcv)):
            c0 = ohlcv.iloc[i - 2]
            c2 = ohlcv.iloc[i]
            ts_i = ohlcv.index[i]

            # FVG tespit (current bar i ile c0'a göre)
            c0_high, c0_low = float(c0["high"]), float(c0["low"])
            c2_high, c2_low = float(c2["high"]), float(c2["low"])

            # BULLISH FVG: c0.high < c2.low → gap [c0.high, c2.low]
            if c0_high < c2_low:
                size = c2_low - c0_high
                ref = c2_low
                if size / ref >= self.min_fvg_size_pct:
                    active.append(_PendingFVG(
                        type="bullish", upper=c2_low, lower=c0_high,
                        created_idx=i, created_ts=ts_i,
                    ))

            # BEARISH FVG: c0.low > c2.high → gap [c2.high, c0.low]
            if c0_low > c2_high:
                size = c0_low - c2_high
                ref = c2_high
                if size / ref >= self.min_fvg_size_pct:
                    active.append(_PendingFVG(
                        type="bearish", upper=c0_low, lower=c2_high,
                        created_idx=i, created_ts=ts_i,
                    ))

            # Retest check (aynı bar'da yeni oluşan FVG hariç)
            if i - last_signal_idx < self.debounce_bars:
                continue

            bar = ohlcv.iloc[i]
            bar_low, bar_high = float(bar["low"]), float(bar["high"])
            bar_close = float(bar["close"])

            # Expire eski FVG'leri
            active = [f for f in active if (i - f.created_idx) <= self.max_age_bars]

            for fvg in list(active):
                if i - fvg.created_idx == 0:
                    continue  # oluştuğu bar'da retest yok

                if fvg.type == "bullish":
                    # Bullish FVG retest: bar low FVG zone'una değdi (lower <= low <= upper)
                    if fvg.lower <= bar_low <= fvg.upper:
                        entry = bar_close
                        sl = fvg.lower * (1 - self.sl_buffer_pct)
                        risk = entry - sl
                        if risk > 0:
                            tp = entry + risk * self.target_r
                            results.append(self._make_record(
                                symbol=symbol, side=Side.LONG, ts=ts_i,
                                entry=entry, sl=sl, tp=tp,
                                fvg_upper=fvg.upper, fvg_lower=fvg.lower,
                                rationale=f"Bullish FVG retest: low {bar_low:.6g} → FVG zone [{fvg.lower:.6g}, {fvg.upper:.6g}]",
                            ))
                            last_signal_idx = i
                            active.remove(fvg)
                            break
                else:  # bearish
                    if fvg.lower <= bar_high <= fvg.upper:
                        entry = bar_close
                        sl = fvg.upper * (1 + self.sl_buffer_pct)
                        risk = sl - entry
                        if risk > 0:
                            tp = entry - risk * self.target_r
                            results.append(self._make_record(
                                symbol=symbol, side=Side.SHORT, ts=ts_i,
                                entry=entry, sl=sl, tp=tp,
                                fvg_upper=fvg.upper, fvg_lower=fvg.lower,
                                rationale=f"Bearish FVG retest: high {bar_high:.6g} → FVG zone [{fvg.lower:.6g}, {fvg.upper:.6g}]",
                            ))
                            last_signal_idx = i
                            active.remove(fvg)
                            break

        return results

    def _make_record(
        self, symbol: str, side: Side, ts,
        entry: float, sl: float, tp: float,
        fvg_upper: float, fvg_lower: float, rationale: str,
    ) -> TradeCallRecord:
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        return TradeCallRecord(
            post_id=f"strat_fvg_{symbol.replace('/', '_')}_{ts_iso}",
            handle="STRATEGY_FVG_RETEST",
            posted_at=ts,
            symbol=symbol,
            side=side,
            entry=entry,
            stop_loss=sl,
            targets=[tp],
            timeframes=[],
            concepts=["fvg", "imbalance"],
            matched_setups=["fvg_retest_entry"],
            key_levels=[
                KeyLevel(price=fvg_upper, label="fvg_upper", source=LevelSource.INFERRED),
                KeyLevel(price=fvg_lower, label="fvg_lower", source=LevelSource.INFERRED),
                KeyLevel(price=entry, label="entry", source=LevelSource.INFERRED),
                KeyLevel(price=sl, label="stop_loss", source=LevelSource.INFERRED),
                KeyLevel(price=tp, label="tp", source=LevelSource.INFERRED),
            ],
            confidence=self.confidence,
            rationale=rationale,
        )
