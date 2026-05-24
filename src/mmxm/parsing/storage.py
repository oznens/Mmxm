"""ParsedPost'ları diske JSONL olarak yaz / oku."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path

from mmxm.models import RawPost
from mmxm.parsing.schema import ParsedPost


def _row(raw: RawPost, parsed: ParsedPost) -> dict:
    return {
        "source_post_id": raw.post_id,
        "handle": raw.handle,
        "posted_at": raw.created_at.isoformat(),
        "source_url": raw.url,
        "parsed": parsed.model_dump(mode="json"),
    }


def write_parsed_jsonl(
    path: Path | str,
    records: Iterable[tuple[RawPost, ParsedPost]],
) -> int:
    """(RawPost, ParsedPost) ikililerini JSONL'e baştan yaz."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for raw, parsed in records:
            fh.write(json.dumps(_row(raw, parsed), ensure_ascii=False) + "\n")
            n += 1
    return n


def append_parsed(path: Path | str, raw: RawPost, parsed: ParsedPost) -> None:
    """Tek satır JSONL append. Long-running batch'lerde checkpoint için."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_row(raw, parsed), ensure_ascii=False) + "\n")


def read_parsed_jsonl(path: Path | str) -> Iterator[dict]:
    """Dict yield et — pattern mining/backtest aşaması bunları kullanır."""
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def already_parsed_ids(path: Path | str) -> set[str]:
    """Mevcut output JSONL'deki post_id'leri set olarak döndür. Resume için."""
    p = Path(path)
    if not p.exists():
        return set()
    ids: set[str] = set()
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["source_post_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids
