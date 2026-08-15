from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from .bybit import BybitMarket
from .ict import analyze_symbol

TIMEFRAMES = {"240": 220, "60": 300, "15": 300, "5": 500}


def telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    ).raise_for_status()


def scan() -> list[dict]:
    load_dotenv()
    top_n = int(os.getenv("TOP_N", "50"))
    min_score = int(os.getenv("MIN_SCORE", "75"))
    market = BybitMarket(testnet=False)
    symbols = market.top_symbols(top_n)
    results = []
    for symbol in symbols:
        try:
            frames = {tf: market.klines(symbol, tf, lim) for tf, lim in TIMEFRAMES.items()}
            signal = analyze_symbol(symbol, frames)
            results.append(signal.to_dict())
            if signal.score >= min_score and signal.direction != "NONE":
                telegram(
                    f"ICT {signal.direction} | {symbol}\n"
                    f"Score: {signal.score}/100 | 4H: {signal.htf_bias} | MMXM: {signal.mmxm}\n"
                    f"Turtle: {signal.turtle_soup} | MSS: {signal.mss} | FVG: {signal.fvg}\n"
                    f"Entry: {signal.entry_low} - {signal.entry_high}\n"
                    f"SL: {signal.stop} | Target: {signal.target}"
                )
        except Exception as exc:
            results.append({"symbol": symbol, "error": str(exc)})
    results.sort(key=lambda x: x.get("score", -1), reverse=True)
    Path("data").mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    Path(f"data/scan_{stamp}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results
