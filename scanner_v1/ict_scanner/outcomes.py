from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _mid(lo: float | None, hi: float | None) -> float | None:
    if lo is None or hi is None:
        return None
    return (float(lo) + float(hi)) / 2


class OutcomeTracker:
    def __init__(self, path: str = 'data/setups.db') -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            '''
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                entry REAL NOT NULL,
                stop REAL NOT NULL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                status TEXT NOT NULL,
                mfe_r REAL NOT NULL DEFAULT 0,
                mae_r REAL NOT NULL DEFAULT 0,
                best_price REAL,
                worst_price REAL,
                closed_at TEXT,
                close_reason TEXT,
                UNIQUE(symbol, direction, opened_at)
            )
            '''
        )
        self.db.commit()

    def register(self, signal: dict, opened_at: str | None = None) -> None:
        if signal.get('state') != 'ENTRY_READY':
            return
        entry = _mid(signal.get('entry_low'), signal.get('entry_high'))
        stop = signal.get('stop')
        if entry is None or stop is None or entry == stop:
            return
        now = opened_at or datetime.now(timezone.utc).isoformat()
        active = self.db.execute(
            "SELECT 1 FROM outcomes WHERE symbol=? AND direction=? AND status='OPEN' LIMIT 1",
            (signal['symbol'], signal['direction']),
        ).fetchone()
        if active:
            return
        self.db.execute(
            '''INSERT OR IGNORE INTO outcomes
            (symbol,direction,opened_at,entry,stop,tp1,tp2,tp3,status)
            VALUES (?,?,?,?,?,?,?,?, 'OPEN')''',
            (signal['symbol'], signal['direction'], now, entry, float(stop), signal.get('tp1'), signal.get('tp2'), signal.get('tp3')),
        )
        self.db.commit()

    def update_symbol(self, symbol: str, df5: pd.DataFrame) -> None:
        if df5.empty:
            return
        rows = self.db.execute(
            "SELECT id,direction,entry,stop,tp1,tp2,tp3,mfe_r,mae_r FROM outcomes WHERE symbol=? AND status='OPEN'",
            (symbol,),
        ).fetchall()
        if not rows:
            return
        high = float(df5.high.iloc[-1])
        low = float(df5.low.iloc[-1])
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            oid, direction, entry, stop, tp1, tp2, tp3, mfe_r, mae_r = row
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            if direction == 'LONG':
                best, worst = high, low
                cur_mfe = (best - entry) / risk
                cur_mae = max(0.0, (entry - worst) / risk)
                stop_hit = low <= stop
                tp3_hit = tp3 is not None and high >= tp3
                tp2_hit = tp2 is not None and high >= tp2
                tp1_hit = tp1 is not None and high >= tp1
            else:
                best, worst = low, high
                cur_mfe = (entry - best) / risk
                cur_mae = max(0.0, (worst - entry) / risk)
                stop_hit = high >= stop
                tp3_hit = tp3 is not None and low <= tp3
                tp2_hit = tp2 is not None and low <= tp2
                tp1_hit = tp1 is not None and low <= tp1

            new_mfe = max(float(mfe_r or 0), float(cur_mfe))
            new_mae = max(float(mae_r or 0), float(cur_mae))
            status = 'OPEN'
            reason = None
            if stop_hit:
                status, reason = 'CLOSED', 'SL'
            elif tp3_hit:
                status, reason = 'CLOSED', 'TP3'
            elif tp2_hit:
                reason = 'TP2'
            elif tp1_hit:
                reason = 'TP1'

            self.db.execute(
                '''UPDATE outcomes SET mfe_r=?, mae_r=?, best_price=?, worst_price=?, status=?,
                   closed_at=CASE WHEN ?='CLOSED' THEN ? ELSE closed_at END,
                   close_reason=COALESCE(?, close_reason) WHERE id=?''',
                (new_mfe, new_mae, best, worst, status, status, now, reason, oid),
            )
        self.db.commit()

    def summary(self) -> dict:
        total, wins, losses = self.db.execute(
            '''SELECT COUNT(*),
               SUM(CASE WHEN close_reason IN ('TP3','TP2','TP1') THEN 1 ELSE 0 END),
               SUM(CASE WHEN close_reason='SL' THEN 1 ELSE 0 END)
               FROM outcomes WHERE status='CLOSED' '''
        ).fetchone()
        avg_mfe, avg_mae = self.db.execute(
            'SELECT AVG(mfe_r), AVG(mae_r) FROM outcomes WHERE status=\'CLOSED\''
        ).fetchone()
        return {
            'closed': int(total or 0), 'wins': int(wins or 0), 'losses': int(losses or 0),
            'win_rate': round((wins or 0) / total * 100, 2) if total else None,
            'avg_mfe_r': round(avg_mfe, 3) if avg_mfe is not None else None,
            'avg_mae_r': round(avg_mae, 3) if avg_mae is not None else None,
        }

    def close(self) -> None:
        self.db.close()
