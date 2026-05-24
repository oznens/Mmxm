from datetime import datetime, timezone
from pathlib import Path

from mmxm.models import RawPost
from mmxm.scraping.storage import read_jsonl, write_jsonl


def test_jsonl_round_trip(tmp_path: Path):
    posts = [
        RawPost(
            post_id=str(i),
            handle="h",
            text=f"post {i}",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    out = tmp_path / "p.jsonl"
    n = write_jsonl(out, posts)
    assert n == 3
    loaded = list(read_jsonl(out))
    assert [p.post_id for p in loaded] == ["0", "1", "2"]
