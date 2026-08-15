import pandas as pd

from ict_scanner.ict import latest_fvg, turtle_soup


def df(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).astype(float)


def test_short_turtle_soup_rejects_previous_high():
    rows = [[100, 101 + i * 0.1, 99, 100] for i in range(20)]
    prior = max(r[1] for r in rows)
    rows.append([prior - 0.2, prior + 1.0, prior - 1.0, prior - 0.1])
    ok, level = turtle_soup(df(rows), "SHORT", lookback=20)
    assert ok
    assert level == prior


def test_bullish_fvg():
    x = df([
        [100, 101, 99, 100],
        [100, 103, 100, 102],
        [103, 104, 102, 103],
    ])
    ok, lo, hi = latest_fvg(x, "LONG")
    assert ok
    assert lo == 101
    assert hi == 102
