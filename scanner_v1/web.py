from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ict_scanner.paper import PaperPortfolio
from ict_scanner.scanner import scan

load_dotenv()
DB = os.getenv("STATE_DB", "data/setups.db")
START = float(os.getenv("PAPER_START_BALANCE", "1000"))
RISK = float(os.getenv("PAPER_RISK_PCT", "0.01"))
INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", "300"))
CHART_DIR = Path(os.getenv("CHART_DIR", "data/charts"))
CHART_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ICT MMXM Paper Dashboard")
app.mount("/charts", StaticFiles(directory=str(CHART_DIR)), name="charts")
_lock = threading.Lock()
_last_scan = {"running": False, "started": None, "finished": None, "error": None}


def _paper() -> PaperPortfolio:
    return PaperPortfolio(DB, START, RISK)


def _setups() -> list[dict]:
    if not Path(DB).exists():
        return []
    db = sqlite3.connect(DB)
    try:
        rows = db.execute("SELECT payload FROM setup_state ORDER BY score DESC").fetchall()
        return [json.loads(r[0]) for r in rows]
    finally:
        db.close()


def run_scan_once() -> None:
    if not _lock.acquire(blocking=False):
        return
    _last_scan.update(running=True, started=time.time(), error=None)
    try:
        scan()
    except Exception as exc:
        _last_scan["error"] = str(exc)
    finally:
        _last_scan.update(running=False, finished=time.time())
        _lock.release()


def loop() -> None:
    time.sleep(2)
    while True:
        run_scan_once()
        time.sleep(max(60, INTERVAL))


@app.on_event("startup")
def startup() -> None:
    threading.Thread(target=loop, daemon=True).start()


@app.get("/api/portfolio")
def portfolio():
    p = _paper()
    try:
        return {"summary": p.snapshot(), "trades": p.trades(), "curve": p.curve(), "scan": _last_scan}
    finally:
        p.close()


@app.get("/api/setups")
def setups():
    return _setups()


@app.post("/api/scan")
def trigger_scan():
    threading.Thread(target=run_scan_once, daemon=True).start()
    return JSONResponse({"ok": True, "message": "scan triggered"})


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(INDEX)


INDEX = r'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ICT MMXM Paper</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,Arial;background:#081018;color:#e7eef7}.wrap{max-width:1500px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:16px;align-items:center}.muted{color:#8ca0b5}.cards{display:grid;grid-template-columns:repeat(6,minmax(140px,1fr));gap:12px;margin:18px 0}.card,.panel{background:#0f1a25;border:1px solid #203142;border-radius:14px;padding:16px}.big{font-size:28px;font-weight:750;margin-top:6px}.good{color:#43d17d}.bad{color:#ff6b6b}.pill{display:inline-block;padding:4px 8px;border-radius:999px;background:#182838;font-size:12px}button{background:#e7eef7;color:#081018;border:0;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}.grid{display:grid;grid-template-columns:1.25fr .75fr;gap:14px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:10px;border-bottom:1px solid #203142;text-align:left;white-space:nowrap}.scroll{overflow:auto;max-height:520px}svg{width:100%;height:260px;background:#0b151f;border-radius:10px}.setup{padding:10px 0;border-bottom:1px solid #203142}.setup:last-child{border:0}@media(max-width:1000px){.cards{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap"><div class="top"><div><h1>ICT · MMXM · Turtle Soup</h1><div class="muted">Bybit Futures Top 50 · Paper Trading · %1 risk</div></div><button onclick="trigger()">Şimdi Tara</button></div>
<div class="cards"><div class="card"><div class="muted">Equity</div><div class="big" id="equity">-</div></div><div class="card"><div class="muted">Toplam PnL</div><div class="big" id="pnl">-</div></div><div class="card"><div class="muted">Sonraki Risk</div><div class="big" id="risk">-</div></div><div class="card"><div class="muted">Win Rate</div><div class="big" id="wr">-</div></div><div class="card"><div class="muted">Açık İşlem</div><div class="big" id="open">-</div></div><div class="card"><div class="muted">Kapalı İşlem</div><div class="big" id="closed">-</div></div></div>
<div class="grid"><div><div class="panel"><h3>Equity Curve</h3><svg id="curve" viewBox="0 0 1000 260" preserveAspectRatio="none"></svg></div><div class="panel" style="margin-top:14px"><h3>Paper Trades</h3><div class="scroll"><table><thead><tr><th>Parite</th><th>Yön</th><th>Grade</th><th>Entry</th><th>SL</th><th>TP3</th><th>Qty</th><th>Risk</th><th>Durum</th><th>PnL</th><th>R</th></tr></thead><tbody id="trades"></tbody></table></div></div></div><div><div class="panel"><h3>Canlı Setup Sıralaması</h3><div id="setups"></div></div></div></div>
</div><script>
const fmt=(n,d=2)=>n==null?'-':Number(n).toFixed(d);function curve(points){const s=document.getElementById('curve');if(!points.length){s.innerHTML='';return}const ys=points.map(x=>x.equity),min=Math.min(...ys),max=Math.max(...ys),span=Math.max(max-min,1);const pts=points.map((p,i)=>`${i/(Math.max(points.length-1,1))*1000},${240-(p.equity-min)/span*220}`).join(' ');s.innerHTML=`<polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="3"/><line x1="0" y1="240" x2="1000" y2="240" stroke="#203142"/>`}
async function load(){const p=await fetch('/api/portfolio').then(r=>r.json()),s=p.summary;equity.textContent=fmt(s.equity)+' USDT';pnl.textContent=(s.pnl_usdt>=0?'+':'')+fmt(s.pnl_usdt)+' USDT';pnl.className='big '+(s.pnl_usdt>=0?'good':'bad');risk.textContent=fmt(s.next_risk_usdt)+' USDT';wr.textContent=s.win_rate==null?'-':fmt(s.win_rate)+'%';open.textContent=s.open_trades;closed.textContent=s.closed_trades;curve(p.curve);trades.innerHTML=p.trades.map(t=>`<tr><td>${t.symbol}</td><td>${t.direction}</td><td>${t.grade||'-'}</td><td>${fmt(t.entry,6)}</td><td>${fmt(t.stop,6)}</td><td>${fmt(t.tp3,6)}</td><td>${fmt(t.qty,5)}</td><td>${fmt(t.risk_usdt)}</td><td><span class="pill">${t.status}${t.close_reason?' · '+t.close_reason:''}</span></td><td class="${t.pnl_usdt>0?'good':t.pnl_usdt<0?'bad':''}">${fmt(t.pnl_usdt)}</td><td>${fmt(t.r_multiple,2)}</td></tr>`).join('');const setupsData=await fetch('/api/setups').then(r=>r.json());setups.innerHTML=setupsData.slice(0,20).map(x=>`<div class="setup"><b>${x.symbol}</b> · ${x.direction} <span class="pill">${x.grade} ${x.score}/100</span><div class="muted">${x.state} · ${x.mmxm} · Raid: ${x.raid_name||'-'} · SMT: ${x.smt?'✓':'-'}</div><div>${fmt(x.entry_low,6)}–${fmt(x.entry_high,6)} · SL ${fmt(x.stop,6)} · TP3 ${fmt(x.tp3,6)}</div></div>`).join('')}
async function trigger(){await fetch('/api/scan',{method:'POST'});setTimeout(load,1500)}load();setInterval(load,15000);
</script></body></html>'''

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web:app", host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8000")), reload=False)
