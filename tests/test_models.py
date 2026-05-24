"""models.py için temel sanity testleri."""

from datetime import datetime, timezone

from mmxm.models import RawPost, Side, Trade


def test_raw_post_round_trip():
    post = RawPost(
        post_id="123",
        handle="example",
        text="long BTC entry 60000 sl 58000 tp 65000",
        created_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )
    j = post.model_dump_json()
    restored = RawPost.model_validate_json(j)
    assert restored.post_id == "123"
    assert restored.handle == "example"


def test_trade_defaults():
    t = Trade(
        source_post_id="123",
        handle="example",
        posted_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
        symbol="BTC/USDT",
        side=Side.LONG,
    )
    assert t.targets == []
    assert t.indicators == []
    assert t.confidence == 0.0
