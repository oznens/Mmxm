from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


class PaperPortfolio:
    def __init__(self, path: str = "data/setups.db", starting_balance: float = 1000.0, risk_pct: float = 0.01) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.starting_balance = float(starting_balance)
        self.risk_pct = float(risk_pct)
        self.db.execute("CREATE TABLE IF NOT EXISTS paper_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.db.execute('''CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            grade TEXT,
            score INTEGER,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            entry REAL NOT NULL,
            stop REAL NOT NULL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            qty REAL NOT NULL,
            risk_usdt REAL NOT NULL,
            status TEXT NOT NULL,
            close_reason TEXT,
            exit_price REAL,
            pnl_usdt REAL NOT NULL DEFAULT 0,
            r_multiple REAL NOT NULL DEFAULT 0,
            signal_json TEXT,
            UNIQUE(symbol, direction, opened_at)
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS equity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            equity REAL NOT NULL,
            event TEXT NOT NULL,
            trade_id INTEGER
        )''')
        self._set_default("starting_balance", self.starting_balance)
        self._set_default("risk_pct", self.risk_pct)
        if self.db.execute("SELECT COUNT(*) FROM equity_history").fetchone()[0] == 0:
            self.db.execute("INSERT INTO equity_history(ts,equity,event) VALUES (?,?,?)", (self._now(), self.starting_balance, "INIT"))
        self.db.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _set_default(self, key: str, value: float) -> None:
        self.db.execute("INSERT OR IGNORE INTO paper_meta(key,value) VALUES (?,?)", (key, str(value)))

    def equity(self) -> float:
        realized = self.db.execute("SELECT COALESCE(SUM(pnl_usdt),0) FROM paper_trades WHERE status='CLOSED'").fetchone()[0]
        return round(self.starting_balance + float(realized or 0), 8)

    def risk_amount(self) -> float:
        return round(self.equity() * self.risk_pct, 8)

    def register(self, signal: dict, opened_at: str | None = None) -> int | None:
        if signal.get("state") != "ENTRY_READY" or signal.get("direction") not in {"LONG", "SHORT"}:
            return None
        lo, hi, stop = signal.get("entry_low"), signal.get("entry_high"), signal.get("stop")
        if lo is None or hi is None or stop is None:
            return None
        entry = (float(lo) + float(hi)) / 2
        stop = float(stop)
        per_unit_risk = abs(entry - stop)
        if per_unit_risk <= 0:
            return None
        active = self.db.execute("SELECT id FROM paper_trades WHERE symbol=? AND status='OPEN' LIMIT 1", (signal["symbol"],)).fetchone()
        if active:
            return None
        risk_usdt = self.risk_amount()
        qty = risk_usdt / per_unit_risk
        now = opened_at or self._now()
        cur = self.db.execute('''INSERT OR IGNORE INTO paper_trades
            (symbol,direction,grade,score,opened_at,entry,stop,tp1,tp2,tp3,qty,risk_usdt,status,signal_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'OPEN',?)''',
            (signal["symbol"], signal["direction"], signal.get("grade"), int(signal.get("score",0)), now,
             entry, stop, signal.get("tp1"), signal.get("tp2"), signal.get("tp3"), qty, risk_usdt,
             json.dumps(signal, default=str, separators=(",", ":"))))
        self.db.commit()
        return cur.lastrowid if cur.rowcount else None

    def update_symbol(self, symbol: str, df5: pd.DataFrame) -> None:
        if df5.empty:
            return
        rows = self.db.execute("SELECT id,direction,entry,stop,tp1,tp2,tp3,qty,risk_usdt FROM paper_trades WHERE symbol=? AND status='OPEN'", (symbol,)).fetchall()
        if not rows:
            return
        high, low = float(df5.high.iloc[-1]), float(df5.low.iloc[-1])
        for tid, direction, entry, stop, tp1, tp2, tp3, qty, risk_usdt in rows:
            exit_price = reason = None
            if direction == "LONG":
                if low <= stop:
                    exit_price, reason = stop, "SL"
                elif tp3 is not None and high >= tp3:
                    exit_price, reason = float(tp3), "TP3"
            else:
                if high >= stop:
                    exit_price, reason = stop, "SL"
                elif tp3 is not None and low <= tp3:
                    exit_price, reason = float(tp3), "TP3"
            if exit_price is None:
                continue
            pnl = (exit_price - entry) * qty if direction == "LONG" else (entry - exit_price) * qty
            r_mult = pnl / risk_usdt if risk_usdt else 0.0
            now = self._now()
            self.db.execute("UPDATE paper_trades SET status='CLOSED',closed_at=?,close_reason=?,exit_price=?,pnl_usdt=?,r_multiple=? WHERE id=?",
                            (now, reason, exit_price, pnl, r_mult, tid))
            self.db.commit()
            self.db.execute("INSERT INTO equity_history(ts,equity,event,trade_id) VALUES (?,?,?,?)", (now, self.equity(), reason, tid))
            self.db.commit()

    def snapshot(self) -> dict:
        equity = self.equity()
        open_count = self.db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'").fetchone()[0]
        closed = self.db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED'").fetchone()[0]
        wins = self.db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED' AND pnl_usdt>0").fetchone()[0]
        losses = self.db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED' AND pnl_usdt<0").fetchone()[0]
        pnl = equity - self.starting_balance
        return {"starting_balance": self.starting_balance, "equity": equity, "pnl_usdt": round(pnl,8),
                "return_pct": round(pnl/self.starting_balance*100,4), "risk_pct": self.risk_pct*100,
                "next_risk_usdt": self.risk_amount(), "open_trades": int(open_count), "closed_trades": int(closed),
                "wins": int(wins), "losses": int(losses), "win_rate": round(wins/closed*100,2) if closed else None}

    def trades(self, limit: int = 200) -> list[dict]:
        cur = self.db.execute("SELECT id,symbol,direction,grade,score,opened_at,closed_at,entry,stop,tp1,tp2,tp3,qty,risk_usdt,status,close_reason,exit_price,pnl_usdt,r_multiple FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def curve(self, limit: int = 500) -> list[dict]:
        cur = self.db.execute("SELECT ts,equity,event,trade_id FROM equity_history ORDER BY id ASC LIMIT ?", (limit,))
        return [{"ts":r[0],"equity":r[1],"event":r[2],"trade_id":r[3]} for r in cur.fetchall()]

    def close(self) -> None:
        self.db.close()
