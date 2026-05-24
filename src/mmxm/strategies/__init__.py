"""Kurallaştırılmış stratejiler — Dreyko/wuipx setup'larından çıkarılmış
operasyonel detektörler. OHLCV taranır, TradeCallRecord listesi üretilir,
backtest engine'i tarafından tüketilir.
"""

from mmxm.strategies.base import Strategy
from mmxm.strategies.fvg_retest import FVGRetestStrategy
from mmxm.strategies.turtle_soup import TurtleSoupStrategy

# İsim → sınıf registry
REGISTRY: dict[str, type[Strategy]] = {
    "turtle_soup": TurtleSoupStrategy,
    "fvg_retest": FVGRetestStrategy,
}


def get_strategy(name: str, **kwargs) -> Strategy:
    if name not in REGISTRY:
        raise ValueError(f"bilinmeyen strateji: {name}. Mevcut: {list(REGISTRY)}")
    return REGISTRY[name](**kwargs)


__all__ = ["FVGRetestStrategy", "REGISTRY", "Strategy", "TurtleSoupStrategy", "get_strategy"]
