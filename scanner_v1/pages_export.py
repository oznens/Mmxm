from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = os.getenv("STATE_DB", "data/setups.db")
SITE = Path(os.getenv("PAGES_DIR", "site"))
SITE.mkdir(parents=True, exist_ok=True)


def rows(db, sql, args=()):
    cur = db.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main():
    db = sqlite3.connect(DB)
    try:
        starting = float((db.execute("SELECT value FROM paper_meta WHERE key='starting_balance'").fetchone() or [1000])[0])
        risk_pct = float((db.execute("SELECT value FROM paper_meta WHERE key='risk_pct'").fetchone() or [0.01])[0])
        realized = float((db.execute("SELECT COALESCE(SUM(pnl_usdt),0) FROM paper_trades WHERE status='CLOSED'").fetchone() or [0])[0])
        equity = starting + realized
        closed = int((db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED'").fetchone() or [0])[0])
        wins = int((db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED' AND pnl_usdt>0").fetchone() or [0])[0])
        losses = int((db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='CLOSED' AND pnl_usdt<0").fetchone() or [0])[0])
        open_count = int((db.execute("SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'").fetchone() or [0])[0])
        portfolio = {
            "starting_balance": starting,
            "equity": round(equity, 8),
            "pnl_usdt": round(realized, 8),
            "return_pct": round(realized / starting * 100, 4) if starting else 0,
            "risk_pct": risk_pct * 100,
            "next_risk_usdt": round(equity * risk_pct, 8),
            "open_trades": open_count,
            "closed_trades": closed,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / closed * 100, 2) if closed else None,
        }
        trades = rows(db, "SELECT id,symbol,direction,grade,score,opened_at,closed_at,entry,stop,tp1,tp2,tp3,qty,risk_usdt,status,close_reason,exit_price,pnl_usdt,r_multiple FROM paper_trades ORDER BY id DESC LIMIT 200")
        curve = rows(db, "SELECT ts,equity,event,trade_id FROM equity_history ORDER BY id ASC LIMIT 500")
        setups_raw = rows(db, "SELECT symbol,direction,state,score,payload,updated_at FROM setup_state ORDER BY score DESC LIMIT 50")
        setups = []
        for r in setups_raw:
            try:
                p = json.loads(r.pop("payload"))
                r.update({k: p.get(k) for k in ["grade","htf_bias","mmxm","raid_name","raid_level","entry_low","entry_high","stop","tp1","tp2","tp3","draw_name","smt","pd_zone"]})
            except Exception:
                pass
            setups.append(r)
        out = {"updated_at": datetime.now(timezone.utc).isoformat(), "portfolio": portfolio, "trades": trades, "curve": curve, "setups": setups}
        (SITE / "data.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        db.close()


if __name__ == "__main__":
    main()
