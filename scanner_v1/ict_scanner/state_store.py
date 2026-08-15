from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class SetupStore:
    def __init__(self, path: str = "data/setups.db") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS setup_state (
                symbol TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                state TEXT NOT NULL,
                score INTEGER NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS setup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                state TEXT NOT NULL,
                score INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self.db.commit()

    def upsert(self, signal: dict) -> bool:
        symbol = signal["symbol"]
        direction = signal.get("direction", "NONE")
        state = signal.get("state", "UNKNOWN")
        score = int(signal.get("score", 0))
        payload = json.dumps(signal, separators=(",", ":"), default=str)
        now = datetime.now(timezone.utc).isoformat()
        row = self.db.execute(
            "SELECT direction, state FROM setup_state WHERE symbol = ?", (symbol,)
        ).fetchone()
        changed = row is None or row[0] != direction or row[1] != state
        self.db.execute(
            """
            INSERT INTO setup_state(symbol, direction, state, score, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
              direction=excluded.direction,
              state=excluded.state,
              score=excluded.score,
              payload=excluded.payload,
              updated_at=excluded.updated_at
            """,
            (symbol, direction, state, score, payload, now),
        )
        if changed:
            self.db.execute(
                "INSERT INTO setup_history(symbol, direction, state, score, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (symbol, direction, state, score, payload, now),
            )
        self.db.commit()
        return changed

    def close(self) -> None:
        self.db.close()
