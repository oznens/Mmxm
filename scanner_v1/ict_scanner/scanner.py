from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from .bybit import BybitMarket
from .charting import render_setup_chart
from .ict import analyze_symbol
from .outcomes import OutcomeTracker
from .state_store import SetupStore

TIMEFRAMES = {"240": 220, "60": 300, "15": 1000, "5": 500}


def telegram(text: str, photo: Path | None = None) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return
    if photo is not None and photo.exists():
        with photo.open("rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": chat_id, "caption": text[:1024]},
                files={"photo": f},
                timeout=30,
            ).raise_for_status()
        if len(text) > 1024:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text[1024:]},
                timeout=15,
            ).raise_for_status()
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    ).raise_for_status()


def _fmt(x: float | None) -> str:
    return "-" if x is None else f"{x:.8g}"


def _alert(signal) -> str:
    return (
        f"{signal.grade} ICT {signal.direction} | {signal.symbol}\n"
        f"State: {signal.state} | Score: {signal.score}/100\n"
        f"4H: {signal.htf_bias} | MMXM: {signal.mmxm} | PD: {signal.pd_zone}\n"
        f"Raid: {signal.raid_name or '-'} @{_fmt(signal.raid_level)} | SMT: {signal.smt}\n"
        f"MSS: {signal.mss} | CISD: {signal.cisd} | DISP: {signal.displacement} ({signal.displacement_ratio})\n"
        f"FVG: {signal.fvg} | IFVG: {signal.ifvg} | OB: {signal.order_block}\n"
        f"Entry: {_fmt(signal.entry_low)} - {_fmt(signal.entry_high)}\n"
        f"SL: {_fmt(signal.stop)}\n"
        f"TP1: {_fmt(signal.tp1)} ({signal.rr_tp1}R)\n"
        f"TP2: {_fmt(signal.tp2)} ({signal.rr_tp2}R)\n"
        f"TP3: {_fmt(signal.tp3)} ({signal.rr_tp3}R)\n"
        f"Draw: {signal.draw_name or '-'} | Invalidation: {signal.invalidation or '-'}"
    )


def scan() -> list[dict]:
    load_dotenv()
    top_n = int(os.getenv("TOP_N", "50"))
    min_score = int(os.getenv("MIN_SCORE", "75"))
    alert_on_change_only = os.getenv("ALERT_ON_CHANGE_ONLY", "true").lower() in {"1", "true", "yes"}
    charts_enabled = os.getenv("CHARTS_ENABLED", "true").lower() in {"1", "true", "yes"}
    state_db = os.getenv("STATE_DB", "data/setups.db")
    chart_dir = os.getenv("CHART_DIR", "data/charts")

    market = BybitMarket(testnet=False)
    symbols = market.top_symbols(top_n)

    btc15 = market.klines("BTCUSDT", "15", TIMEFRAMES["15"])
    eth15 = market.klines("ETHUSDT", "15", TIMEFRAMES["15"])

    store = SetupStore(state_db)
    outcomes = OutcomeTracker(state_db)
    results = []
    try:
        for symbol in symbols:
            try:
                frames = {tf: market.klines(symbol, tf, lim) for tf, lim in TIMEFRAMES.items()}
                outcomes.update_symbol(symbol, frames["5"])

                benchmark = {"15": eth15 if symbol == "BTCUSDT" else btc15}
                signal = analyze_symbol(symbol, frames, benchmark)
                payload = signal.to_dict()
                results.append(payload)
                changed = store.upsert(payload)
                outcomes.register(payload)

                should_alert = signal.score >= min_score and signal.direction != "NONE"
                if alert_on_change_only:
                    should_alert = should_alert and changed
                if should_alert:
                    photo = render_setup_chart(symbol, frames, signal, chart_dir) if charts_enabled else None
                    telegram(_alert(signal), photo)
            except Exception as exc:
                results.append({"symbol": symbol, "error": str(exc)})
    finally:
        summary = outcomes.summary()
        outcomes.close()
        store.close()

    results.sort(key=lambda x: x.get("score", -1), reverse=True)
    Path("data").mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    Path(f"data/scan_{stamp}.json").write_text(json.dumps({"outcomes": summary, "setups": results}, indent=2), encoding="utf-8")
    return results
