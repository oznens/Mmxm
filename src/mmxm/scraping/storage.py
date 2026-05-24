"""Ham postları JSONL olarak diske yaz / oku."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from mmxm.models import RawPost


def write_jsonl(path: Path | str, posts: Iterable[RawPost]) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for post in posts:
            fh.write(post.model_dump_json() + "\n")
            n += 1
    return n


def read_jsonl(path: Path | str) -> Iterator[RawPost]:
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield RawPost.model_validate(json.loads(line))
