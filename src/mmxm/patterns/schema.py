"""Pattern mining çıktısının veri modelleri."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from mmxm.parsing.schema import Bias, KeyLevel, Side


class TraderProfile(BaseModel):
    """Tek bir trader'ın özet profili — kaç post, hangi konseptler/semboller, hangi tip."""

    handle: str
    n_posts: int

    post_type_dist: dict[str, int] = Field(default_factory=dict)
    bias_dist: dict[str, int] = Field(default_factory=dict)
    language_dist: dict[str, int] = Field(default_factory=dict)

    n_trade_calls: int = 0
    avg_confidence: float = 0.0

    top_concepts: list[tuple[str, int]] = Field(default_factory=list)
    top_symbols: list[tuple[str, int]] = Field(default_factory=list)
    top_timeframes: list[tuple[str, int]] = Field(default_factory=list)


class SetupMatch(BaseModel):
    """Bir post belirli bir named setup'a uyduğunda oluşur."""

    setup_name: str
    post_id: str
    handle: str
    posted_at: datetime
    confidence: float
    matched_concepts: list[str]  # setup tanımındaki kavramlardan postta bulunanlar
    timeframes: list[str]
    symbols: list[str]
    bias: Optional[Bias] = None


class SetupSummary(BaseModel):
    """Bir named setup'ın toplu istatistiği."""

    setup_name: str
    description: str
    n_matches: int
    handles: dict[str, int] = Field(default_factory=dict)
    timeframe_dist: dict[str, int] = Field(default_factory=dict)
    symbol_dist: dict[str, int] = Field(default_factory=dict)
    bias_dist: dict[str, int] = Field(default_factory=dict)
    avg_confidence: float = 0.0
    sample_post_ids: list[str] = Field(default_factory=list)


class TradeCallRecord(BaseModel):
    """Backtest aşaması için flatten edilmiş trade-call kaydı."""

    post_id: str
    handle: str
    posted_at: datetime

    symbol: str
    side: Side
    entry: Optional[float] = None
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: list[float] = Field(default_factory=list)
    leverage: Optional[float] = None
    risk_reward: Optional[float] = None

    timeframes: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    matched_setups: list[str] = Field(default_factory=list)
    key_levels: list[KeyLevel] = Field(default_factory=list)

    confidence: float
    rationale: str
    source_url: Optional[str] = None


class PatternsReport(BaseModel):
    """Tam pattern mining raporu — JSON olarak yazılır."""

    n_parsed_posts: int
    n_trade_calls: int
    trader_profiles: list[TraderProfile]
    setup_summaries: list[SetupSummary]
    top_concepts_overall: list[tuple[str, int]]
    concept_cooccurrence_top: list[tuple[tuple[str, str], int]]
