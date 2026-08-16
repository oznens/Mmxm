from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from ict_scanner.bybit import BybitMarket

DB = os.getenv("STATE_DB", "data/setups.db")
SITE = Path(os.getenv("PAGES_DIR", "site"))
DETAILS = SITE / "details"
DETAILS.mkdir(parents=True, exist_ok=True)


def candles(df, limit: int):
    d = df.tail(limit)
    return [
        {
            "t": x.timestamp.isoformat(),
            "o": float(x.open),
            "h": float(x.high),
            "l": float(x.low),
            "c": float(x.close),
        }
        for x in d.itertuples(index=False)
    ]


def main():
    db = sqlite3.connect(DB)
    market = BybitMarket(testnet=False)
    try:
        rows = db.execute(
            "SELECT symbol,payload FROM setup_state WHERE direction!='NONE' ORDER BY score DESC LIMIT 50"
        ).fetchall()
        manifest = []
        for symbol, raw in rows:
            try:
                p = json.loads(raw)
                f15 = market.klines(symbol, "15", 160)
                f5 = market.klines(symbol, "5", 200)
                levels = {
                    k: p.get(k)
                    for k in [
                        "raid_name","raid_level","entry_low","entry_high","stop","tp1","tp2","tp3",
                        "draw_name","pd_zone","ote_low","ote_high","htf_bias","mmxm","direction","grade",
                        "score","state","smt","mss","cisd","displacement","fvg","ifvg","order_block"
                    ]
                }
                data = {
                    "symbol": symbol,
                    "signal": levels,
                    "m15": candles(f15, 120),
                    "m5": candles(f5, 150),
                }
                name = f"{symbol}.json"
                (DETAILS / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                manifest.append(symbol)
            except Exception as exc:
                (DETAILS / f"{symbol}.error.txt").write_text(str(exc), encoding="utf-8")
        (DETAILS / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    finally:
        db.close()


if __name__ == "__main__":
    main()
