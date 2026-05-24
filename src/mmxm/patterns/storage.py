"""Pattern mining çıktısını diske yaz."""

from __future__ import annotations

import json
from pathlib import Path

from mmxm.patterns.schema import PatternsReport, TradeCallRecord


def write_report(path: Path | str, report: PatternsReport) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def write_trade_calls(path: Path | str, calls: list[TradeCallRecord]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for c in calls:
            fh.write(c.model_dump_json() + "\n")
    return len(calls)
