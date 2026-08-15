from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pybit.unified_trading import HTTP


@dataclass(slots=True)
class BybitMarket:
    testnet: bool = False
    http: HTTP = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.http = HTTP(testnet=self.testnet)

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

    def top_symbols(self, n: int = 50) -> list[str]:
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

    def klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        rows = self.http.get_kline(
            category="linear", symbol=symbol, interval=interval, limit=limit
        )["result"]["list"]
        rows = list(reversed(rows))
        df = pd.DataFrame(
            rows,
            columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],
        )
        for c in ["open", "high", "low", "close", "volume", "turnover"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="ms", utc=True)
        return df.dropna().reset_index(drop=True)
