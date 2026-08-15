from __future__ import annotations

from dataclasses import dataclass, field
import time

import pandas as pd
import requests
from pybit.unified_trading import HTTP


@dataclass(slots=True)
class BybitMarket:
    """Bybit-first public futures market adapter with OKX fallback.

    GitHub-hosted runners can originate from US IP space, where Bybit returns 403.
    In that case the adapter automatically switches to OKX USDT perpetual SWAP data
    while preserving normalized symbols such as BTCUSDT for the ICT engine.
    """

    testnet: bool = False
    http: HTTP = field(init=False, repr=False)
    backend: str = field(init=False, default="bybit")
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.http = HTTP(testnet=self.testnet)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ict-paper-scanner/1.0"})

    def perpetual_symbols(self) -> set[str]:
        out: set[str] = set()
        cursor = None
        while True:
            params = {"category": "linear", "status": "Trading", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            r = self.http.get_instruments_info(**params)
            result = r["result"]
            for x in result["list"]:
                if (
                    x.get("contractType") == "LinearPerpetual"
                    and x.get("quoteCoin") == "USDT"
                    and x.get("status") == "Trading"
                ):
                    out.add(x["symbol"])
            cursor = result.get("nextPageCursor") or ""
            if not cursor:
                break
        return out

    @staticmethod
    def _okx_id(symbol: str) -> str:
        if not symbol.endswith("USDT"):
            raise ValueError(f"Unsupported normalized symbol: {symbol}")
        return f"{symbol[:-4]}-USDT-SWAP"

    @staticmethod
    def _norm_okx(inst_id: str) -> str:
        return inst_id.replace("-USDT-SWAP", "USDT")

    def _okx_get(self, path: str, params: dict) -> list:
        r = self.session.get(f"https://www.okx.com{path}", params=params, timeout=20)
        r.raise_for_status()
        body = r.json()
        if body.get("code") != "0":
            raise RuntimeError(f"OKX {body.get('code')}: {body.get('msg')}")
        return body.get("data", [])

    def _okx_top_symbols(self, n: int) -> list[str]:
        instruments = self._okx_get("/api/v5/public/instruments", {"instType": "SWAP"})
        allowed = {
            x.get("instId")
            for x in instruments
            if x.get("settleCcy") == "USDT" and x.get("state") == "live" and x.get("instId", "").endswith("-USDT-SWAP")
        }
        tickers = self._okx_get("/api/v5/market/tickers", {"instType": "SWAP"})
        ranked = []
        for t in tickers:
            inst = t.get("instId", "")
            if inst not in allowed:
                continue
            try:
                last = float(t.get("last") or 0)
                base_vol = float(t.get("volCcy24h") or 0)
                turnover = last * base_vol
            except (TypeError, ValueError):
                turnover = 0.0
            ranked.append((turnover, self._norm_okx(inst)))
        ranked.sort(reverse=True)
        return [s for _, s in ranked[:n]]

    def top_symbols(self, n: int = 50) -> list[str]:
        if self.backend == "okx":
            return self._okx_top_symbols(n)
        try:
            allowed = self.perpetual_symbols()
            tickers = self.http.get_tickers(category="linear")["result"]["list"]
            ranked = []
            for t in tickers:
                symbol = t.get("symbol", "")
                if symbol not in allowed:
                    continue
                try:
                    turnover = float(t.get("turnover24h") or 0)
                except (TypeError, ValueError):
                    turnover = 0.0
                ranked.append((turnover, symbol))
            ranked.sort(reverse=True)
            return [s for _, s in ranked[:n]]
        except Exception:
            self.backend = "okx"
            return self._okx_top_symbols(n)

    def _okx_klines(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        bar_map = {"5": "5m", "15": "15m", "60": "1H", "240": "4H"}
        bar = bar_map.get(str(interval))
        if not bar:
            raise ValueError(f"Unsupported interval for OKX fallback: {interval}")
        inst = self._okx_id(symbol)
        rows: list[list[str]] = []
        after = None
        while len(rows) < limit:
            params = {"instId": inst, "bar": bar, "limit": str(min(300, limit - len(rows)))}
            if after:
                params["after"] = after
            page = self._okx_get("/api/v5/market/history-candles", params)
            if not page:
                break
            rows.extend(page)
            oldest = page[-1][0]
            if oldest == after:
                break
            after = oldest
            if len(rows) < limit:
                time.sleep(0.08)
        rows = rows[:limit]
        rows.reverse()
        data = []
        for r in rows:
            if len(r) < 6:
                continue
            data.append([r[0], r[1], r[2], r[3], r[4], r[5], r[7] if len(r) > 7 else 0])
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
        for c in ["open", "high", "low", "close", "volume", "turnover"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="ms", utc=True)
        return df.dropna().drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)

    def klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        if self.backend == "okx":
            return self._okx_klines(symbol, interval, limit)
        try:
            rows = self.http.get_kline(category="linear", symbol=symbol, interval=interval, limit=limit)["result"]["list"]
            rows = list(reversed(rows))
            df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
            for c in ["open", "high", "low", "close", "volume", "turnover"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="ms", utc=True)
            return df.dropna().reset_index(drop=True)
        except Exception:
            self.backend = "okx"
            return self._okx_klines(symbol, interval, limit)
