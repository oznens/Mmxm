"""MMXM (Market Maker X Model) detector.

Wuipx'in tanımı: "MMXM = Market Maker Buy/Sell modellerine geçerdim"
Jaxiwnl21'in kullanımı: HTF yapısı, MMBM/MMSM evreleri.

5-evre yapısı:
1. **Original Consolidation** — son N bar düşük volatilite, range içinde
2. **Manipulation** — range low'un aşağı (BSL için yukarı) kırılması (Judas Swing)
3. **Smart Money Reversal** — manipülasyon sonrası ters yön candle close
4. **(opsiyonel) FVG retest** — re-accumulation bölgesi
5. **Distribution / Markup** — range opposite extreme'e markup

TurtleSoup'tan farkı: TP = range high/low (DİNAMİK, smart money hedefi),
sabit R çoklayıcı değil. Bu MMXM'in özü: piyasa o seviyeyi süpürmeye gider.

Entry: SMR candle close
SL: manipulation wick + buffer
TP: range opposite extreme (smart money'nin hedeflediği likidite)
"""

from __future__ import annotations

import pandas as pd

from mmxm.parsing.schema import KeyLevel, LevelSource, Side
from mmxm.patterns.schema import TradeCallRecord
from mmxm.strategies.base import Strategy


class MMXMStrategy(Strategy):
    name = "mmxm"

    def __init__(
        self,
        consolidation_bars: int = 30,           # Faz 1 — kac bar konsolidasyon
        max_range_pct: float = 0.05,            # Range high-low'ın max %5 olması (sideways)
        sweep_min_pct: float = 0.001,           # Manipülasyon mesafesi
        reclaim_min_pct: float = 0.0005,        # SMR candle reclaim
        sl_buffer_pct: float = 0.002,
        tp_buffer_pct: float = -0.001,          # Range opposite biraz öncesinde TP (likidite altı)
        min_target_r: float = 1.0,              # Minimum R:R için filtre
        debounce_bars: int = 20,
        confidence: float = 0.7,
    ):
        self.consolidation_bars = consolidation_bars
        self.max_range_pct = max_range_pct
        self.sweep_min_pct = sweep_min_pct
        self.reclaim_min_pct = reclaim_min_pct
        self.sl_buffer_pct = sl_buffer_pct
        self.tp_buffer_pct = tp_buffer_pct
        self.min_target_r = min_target_r
        self.debounce_bars = debounce_bars
        self.confidence = confidence

    def scan(self, symbol: str, ohlcv: pd.DataFrame) -> list[TradeCallRecord]:
        if len(ohlcv) <= self.consolidation_bars + 2:
            return []

        # Konsolidasyon: önceki N bar (current hariç) high/low
        cons_high = ohlcv["high"].shift(1).rolling(self.consolidation_bars).max()
        cons_low = ohlcv["low"].shift(1).rolling(self.consolidation_bars).min()
        cons_mid = (cons_high + cons_low) / 2

        results: list[TradeCallRecord] = []
        last_signal_idx = -self.debounce_bars

        for i in range(self.consolidation_bars, len(ohlcv)):
            if i - last_signal_idx < self.debounce_bars:
                continue

            ch, cl = float(cons_high.iloc[i]), float(cons_low.iloc[i])
            if pd.isna(ch) or pd.isna(cl) or cl == 0:
                continue
            range_pct = (ch - cl) / cl
            if range_pct > self.max_range_pct or range_pct < 0.005:
                continue  # ya çok geniş ya çok dar — range değil

            bar = ohlcv.iloc[i]
            o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])

            # BULLISH MMBM (long): range low'un altına manipülasyon + SMR up
            broke_below = l < cl * (1 - self.sweep_min_pct)
            reclaimed_up = c > cl * (1 + self.reclaim_min_pct)
            close_in_lower_half = c < cons_mid.iloc[i]  # SMR fazı henüz baştan
            if broke_below and reclaimed_up and close_in_lower_half:
                entry = c
                sl = l * (1 - self.sl_buffer_pct)
                # TP = range high (smart money'nin hedefi: BSL üstünde)
                tp = ch * (1 + self.tp_buffer_pct)  # range high'ın biraz altı (TP'yi garanti)
                risk = entry - sl
                if risk > 0 and (tp - entry) / risk >= self.min_target_r:
                    results.append(self._make_record(
                        symbol=symbol, side=Side.LONG, ts=bar.name,
                        entry=entry, sl=sl, tp=tp,
                        range_low=cl, range_high=ch,
                        rationale=(
                            f"Bullish MMBM: range [{cl:.4g},{ch:.4g}] alt manip → SMR close {c:.4g}. "
                            f"TP=range high {ch:.4g} (BSL hedef)."
                        ),
                    ))
                    last_signal_idx = i
                    continue

            # BEARISH MMSM (short): range high üstüne manip + SMR down
            broke_above = h > ch * (1 + self.sweep_min_pct)
            reclaimed_down = c < ch * (1 - self.reclaim_min_pct)
            close_in_upper_half = c > cons_mid.iloc[i]
            if broke_above and reclaimed_down and close_in_upper_half:
                entry = c
                sl = h * (1 + self.sl_buffer_pct)
                tp = cl * (1 - self.tp_buffer_pct)  # range low'un biraz üstü (TP)
                risk = sl - entry
                if risk > 0 and (entry - tp) / risk >= self.min_target_r:
                    results.append(self._make_record(
                        symbol=symbol, side=Side.SHORT, ts=bar.name,
                        entry=entry, sl=sl, tp=tp,
                        range_low=cl, range_high=ch,
                        rationale=(
                            f"Bearish MMSM: range [{cl:.4g},{ch:.4g}] üst manip → SMR close {c:.4g}. "
                            f"TP=range low {cl:.4g} (SSL hedef)."
                        ),
                    ))
                    last_signal_idx = i
        return results

    def _make_record(
        self, symbol: str, side: Side, ts,
        entry: float, sl: float, tp: float,
        range_low: float, range_high: float, rationale: str,
    ) -> TradeCallRecord:
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        return TradeCallRecord(
            post_id=f"strat_mmxm_{symbol.replace('/', '_')}_{ts_iso}",
            handle="STRATEGY_MMXM",
            posted_at=ts,
            symbol=symbol,
            side=side,
            entry=entry,
            stop_loss=sl,
            targets=[tp],
            timeframes=[],
            concepts=["mmxm", "mmbm" if side == Side.LONG else "mmsm",
                      "liquidity_sweep", "manipulation", "smart_money_reversal"],
            matched_setups=["mmxm", "liquidity_sweep_reversal"],
            key_levels=[
                KeyLevel(price=range_low, label="range_low_ssl", source=LevelSource.INFERRED),
                KeyLevel(price=range_high, label="range_high_bsl", source=LevelSource.INFERRED),
                KeyLevel(price=entry, label="smr_entry", source=LevelSource.INFERRED),
                KeyLevel(price=sl, label="manipulation_sl", source=LevelSource.INFERRED),
                KeyLevel(price=tp, label="distribution_tp", source=LevelSource.INFERRED),
            ],
            confidence=self.confidence,
            rationale=rationale,
        )
