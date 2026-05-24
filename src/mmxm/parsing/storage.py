"""ParsedPost'ları diske JSONL olarak yaz / oku."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from mmxm.models import RawPost
from mmxm.parsing.schema import ParsedPost


def write_parsed_jsonl(
    path: Path | str,
    records: Iterable[tuple[RawPost, ParsedPost]],
) -> int:
    """(RawPost, ParsedPost) ikililerini JSONL'e yaz. Kaynak post id'sini koru."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for raw, parsed in records:
            row = {
                "source_post_id": raw.post_id,
                "handle": raw.handle,
                "posted_at": raw.created_at.isoformat(),
                "source_url": raw.url,
                "parsed": parsed.model_dump(mode="json"),
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_parsed_jsonl(path: Path | str) -> Iterator[dict]:
    """Dict yield et — pattern mining/backtest aşaması bunları kullanır."""
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)
