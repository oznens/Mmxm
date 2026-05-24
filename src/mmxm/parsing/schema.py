"""Parser çıktısının pydantic şeması — Claude `messages.parse` için kullanılır.

Tasarım kararı: tek bir `Trade` modeli yetmiyor. Bizim trader'larımız (jaxiwnl21,
wuipx) postlarının çoğu somut trade-call değil, ICT/SMC metodolojisi anlatımı.
Bu yüzden `ParsedPost` umbrella'sı:
  - Her postun tipini sınıflandırıyor (trade_call / methodology / commentary / noise)
  - Daima ICT konseptlerini ve seviyeleri çıkarıyor
  - trade_call ise sub-field olarak TradeCall dolduruyor
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PostType(str, Enum):
    TRADE_CALL = "trade_call"  # somut entry/SL/TP veya "burada açtım" beyanı
    METHODOLOGY = "methodology"  # bir konsepti/setup'ı anlatan eğitici post
    COMMENTARY = "commentary"  # piyasa yorumu, makro fikir — somut setup yok
    NOISE = "noise"  # off-topic, alıntı, kişisel paylaşım


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"
    UNKNOWN = "unknown"


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class LevelSource(str, Enum):
    TEXT = "text"  # seviye metinde geçti
    CHART = "chart"  # seviye görselden okundu
    INFERRED = "inferred"  # parser çıkarımı


class KeyLevel(BaseModel):
    """Fiyat seviyesi — text'ten veya grafikten çıkarılmış."""

    price: float
    label: str  # ör. "FVG_upper", "support", "TP1", "swing_high", "OB_bottom"
    source: LevelSource


class TradeCall(BaseModel):
    """Somut bir trade çağrısı. Yalnızca post_type == TRADE_CALL ise dolu."""

    symbol: str  # "BTC/USDT", "ETH/USDT", "SOL" gibi standardize edilmiş
    side: Side
    entry: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: list[float] = Field(default_factory=list)
    leverage: Optional[float] = None
    risk_reward: Optional[float] = None  # R:R oranı


class ParsedPost(BaseModel):
    """Bir X postunun yapılandırılmış çıktısı.

    Her alanın boş/None gelmesi geçerli — sadece tweet'ten çıkarılabilen veriler.
    Aşırı çıkarım yapma; emin değilsen confidence düşür.
    """

    post_type: PostType
    language: str  # "tr", "en", "tr_en"

    # Daima çıkarılır (varsa)
    bias: Optional[Bias] = None
    timeframes: list[str] = Field(default_factory=list)  # ör. ["4h", "1h"]
    symbols_mentioned: list[str] = Field(default_factory=list)  # tüm geçen semboller
    concepts: list[str] = Field(default_factory=list)  # ICT/SMC konseptleri (lowercase snake_case)

    # post_type == TRADE_CALL ise
    trade: Optional[TradeCall] = None

    # post_type == METHODOLOGY ise
    methodology_summary: Optional[str] = None

    # Daima
    rationale: str  # postun "neden"i — 1-3 cümle, kaynak dilinde kalabilir
    key_levels: list[KeyLevel] = Field(default_factory=list)

    confidence: float  # [0,1] — parserin çıkarımına olan güveni
    parser_notes: Optional[str] = None  # parserın kendi notu (grafik bulanık, çelişki vs.)
