import sqlite3

import pandas as pd

from ict_scanner.outcomes import OutcomeTracker


def _signal(direction='LONG'):
    return {
        'symbol': 'TESTUSDT', 'direction': direction, 'state': 'ENTRY_READY',
        'entry_low': 99.0, 'entry_high': 101.0, 'stop': 95.0,
        'tp1': 105.0, 'tp2': 110.0, 'tp3': 115.0,
    }


def test_register_entry_ready_once(tmp_path):
    db = tmp_path / 'setups.db'
    t = OutcomeTracker(str(db))
    s = _signal()
    t.register(s, opened_at='2026-01-01T00:00:00+00:00')
    t.register(s, opened_at='2026-01-01T00:05:00+00:00')
    count = t.db.execute("SELECT COUNT(*) FROM outcomes WHERE status='OPEN'").fetchone()[0]
    assert count == 1
    t.close()


def test_long_tp3_closes_and_tracks_mfe(tmp_path):
    db = tmp_path / 'setups.db'
    t = OutcomeTracker(str(db))
    t.register(_signal(), opened_at='2026-01-01T00:00:00+00:00')
    candles = pd.DataFrame([{'open': 100, 'high': 116, 'low': 99, 'close': 115}])
    t.update_symbol('TESTUSDT', candles)
    row = t.db.execute("SELECT status, close_reason, mfe_r FROM outcomes").fetchone()
    assert row[0] == 'CLOSED'
    assert row[1] == 'TP3'
    assert row[2] >= 3.0
    t.close()


def test_same_candle_stop_wins_conservatively(tmp_path):
    db = tmp_path / 'setups.db'
    t = OutcomeTracker(str(db))
    t.register(_signal(), opened_at='2026-01-01T00:00:00+00:00')
    candles = pd.DataFrame([{'open': 100, 'high': 116, 'low': 94, 'close': 100}])
    t.update_symbol('TESTUSDT', candles)
    reason = t.db.execute("SELECT close_reason FROM outcomes").fetchone()[0]
    assert reason == 'SL'
    t.close()
