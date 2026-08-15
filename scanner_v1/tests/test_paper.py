import pandas as pd

from ict_scanner.paper import PaperPortfolio


def sig(direction='LONG'):
    return {
        'symbol':'ETHUSDT','direction':direction,'grade':'A+','score':90,'state':'ENTRY_READY',
        'entry_low':100.0,'entry_high':100.0,'stop':98.0 if direction=='LONG' else 102.0,
        'tp1':102.0 if direction=='LONG' else 98.0,
        'tp2':104.0 if direction=='LONG' else 96.0,
        'tp3':106.0 if direction=='LONG' else 94.0,
    }


def test_starting_balance_and_one_percent_risk(tmp_path):
    p = PaperPortfolio(str(tmp_path/'p.db'), 1000, 0.01)
    try:
        assert p.equity() == 1000
        assert p.risk_amount() == 10
        tid = p.register(sig(), '2026-01-01T00:00:00+00:00')
        assert tid is not None
        t = p.trades()[0]
        assert t['qty'] == 5.0
        assert t['risk_usdt'] == 10.0
    finally:
        p.close()


def test_tp3_updates_equity_and_next_risk(tmp_path):
    p = PaperPortfolio(str(tmp_path/'p.db'), 1000, 0.01)
    try:
        p.register(sig(), '2026-01-01T00:00:00+00:00')
        candles = pd.DataFrame([{'open':100,'high':106.5,'low':99.5,'close':106}])
        p.update_symbol('ETHUSDT', candles)
        s = p.snapshot()
        assert s['equity'] == 1030.0
        assert s['next_risk_usdt'] == 10.3
        assert s['wins'] == 1
    finally:
        p.close()


def test_same_candle_stop_wins_conservatively(tmp_path):
    p = PaperPortfolio(str(tmp_path/'p.db'), 1000, 0.01)
    try:
        p.register(sig(), '2026-01-01T00:00:00+00:00')
        candles = pd.DataFrame([{'open':100,'high':107,'low':97,'close':104}])
        p.update_symbol('ETHUSDT', candles)
        t = p.trades()[0]
        assert t['close_reason'] == 'SL'
        assert t['pnl_usdt'] == -10.0
        assert p.equity() == 990.0
        assert p.risk_amount() == 9.9
    finally:
        p.close()
