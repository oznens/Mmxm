"""ParsedPost schema serialization testleri."""

from mmxm.parsing.schema import (
    Bias,
    KeyLevel,
    LevelSource,
    ParsedPost,
    PostType,
    Side,
    TradeCall,
)


def test_minimal_commentary_post():
    p = ParsedPost(
        post_type=PostType.COMMENTARY,
        language="tr",
        rationale="Piyasa hakkında genel bir yorum.",
        confidence=0.6,
    )
    assert p.trade is None
    assert p.concepts == []
    j = p.model_dump_json()
    restored = ParsedPost.model_validate_json(j)
    assert restored.post_type == PostType.COMMENTARY


def test_full_trade_call():
    p = ParsedPost(
        post_type=PostType.TRADE_CALL,
        language="tr",
        bias=Bias.BULLISH,
        timeframes=["4h", "1h"],
        symbols_mentioned=["BTC/USDT"],
        concepts=["fvg", "liquidity_sweep", "bullish_ob"],
        trade=TradeCall(
            symbol="BTC/USDT",
            side=Side.LONG,
            entry=60000.0,
            stop_loss=58500.0,
            targets=[62000.0, 64000.0],
            leverage=10.0,
            risk_reward=2.6,
        ),
        rationale="4h FVG geri test, SSL sweep sonrası bullish OB'den giriş.",
        key_levels=[
            KeyLevel(price=60000.0, label="entry", source=LevelSource.TEXT),
            KeyLevel(price=58500.0, label="stop_loss", source=LevelSource.CHART),
        ],
        confidence=0.9,
    )
    assert p.trade is not None
    assert p.trade.side == Side.LONG
    assert len(p.key_levels) == 2
    # roundtrip
    restored = ParsedPost.model_validate_json(p.model_dump_json())
    assert restored.trade.targets == [62000.0, 64000.0]


def test_methodology_post_has_summary():
    p = ParsedPost(
        post_type=PostType.METHODOLOGY,
        language="tr",
        concepts=["turtle_soup", "false_breakout"],
        methodology_summary="Turtle Soup, sahte kırılım sonrası tersine giriş modeli.",
        rationale="Fiyat üst likiditeyi alıp geri dönerse turtle soup setup'ı oluşur.",
        confidence=0.8,
    )
    assert p.methodology_summary is not None
    assert p.trade is None
