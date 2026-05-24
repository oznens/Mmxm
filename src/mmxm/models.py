"""Pipeline boyunca dolaşan veri modelleri."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"
    UNKNOWN = "unknown"


class RawPost(BaseModel):
    """Scraper'dan çıkan ham X postu. Henüz parse edilmemiş."""

    post_id: str
    handle: str
    text: str
    created_at: datetime
    url: Optional[str] = None
    is_reply: bool = False
    in_reply_to: Optional[str] = None
    thread_id: Optional[str] = None
    media_urls: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class Trade(BaseModel):
    """LLM'in bir trade postundan çıkardığı yapılandırılmış kayıt."""

    source_post_id: str
    handle: str
    posted_at: datetime

    symbol: str  # ör. "BTC/USDT", "ETH"
    side: Side
    entry: Optional[float] = None
    entry_range: Optional[tuple[float, float]] = None
    stop_loss: Optional[float] = None
    targets: list[float] = Field(default_factory=list)
    leverage: Optional[float] = None
    timeframe: Optional[str] = None  # "15m", "1h", "1d", ...

    indicators: list[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    invalidation: Optional[str] = None

    confidence: float = 0.0  # LLM'in çıkarımına güven skoru [0,1]


class Setup(BaseModel):
    """Birden fazla trade'de tekrarlayan örüntü (pattern mining çıktısı)."""

    name: str
    description: str
    side: Side
    indicators: list[str]
    timeframe: Optional[str] = None
    rules: dict = Field(default_factory=dict)  # entry/stop/target hesaplama mantığı
    sample_trade_ids: list[str] = Field(default_factory=list)


class BacktestResult(BaseModel):
    setup_name: str
    symbol: str
    timeframe: str
    n_trades: int
    win_rate: float
    avg_r: float  # ortalama R-multiple
    profit_factor: float
    max_drawdown: float
    equity_curve_path: Optional[str] = None
