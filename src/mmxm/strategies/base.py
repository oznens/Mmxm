"""Strateji arayüzü.

Bir strateji = OHLCV DataFrame tarayıp TradeCallRecord listesi üretir.
Bu kayıtlar backtest engine'inin tüketmek için zaten kullandığı şema.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from mmxm.patterns.schema import TradeCallRecord


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def scan(self, symbol: str, ohlcv: pd.DataFrame) -> list[TradeCallRecord]:
        """OHLCV üzerinde tarayıp sinyalleri TradeCallRecord olarak döndür."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
