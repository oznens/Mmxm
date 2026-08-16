from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _line(ax, y, label, linestyle='--'):
    if y is None:
        return
    ax.axhline(float(y), linestyle=linestyle, linewidth=1)
    ax.text(0.995, float(y), f' {label} {float(y):.8g}', transform=ax.get_yaxis_transform(), va='center', ha='right', fontsize=8)


def _candles(ax, df: pd.DataFrame, limit: int = 120) -> None:
    x = df.iloc[-limit:].reset_index(drop=True)
    for i, row in x.iterrows():
        up = row.close >= row.open
        ax.vlines(i, row.low, row.high, linewidth=0.8)
        bottom = min(row.open, row.close)
        height = max(abs(row.close - row.open), 1e-12)
        rect = plt.Rectangle((i - 0.3, bottom), 0.6, height, fill=up, linewidth=0.8)
        ax.add_patch(rect)
    ax.set_xlim(-1, len(x))
    if 'timestamp' in x.columns and len(x) > 1:
        step = max(len(x) // 6, 1)
        ticks = list(range(0, len(x), step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(x.timestamp.iloc[i]).strftime('%m-%d\n%H:%M') for i in ticks], fontsize=8)


def render_setup_chart(symbol: str, frames: dict[str, pd.DataFrame], signal, out_dir: str = 'data/charts') -> Path:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    safe_state = str(signal.state).lower()
    path = Path(out_dir) / f'{symbol}_{signal.direction}_{safe_state}.png'

    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.15])
    ax15 = fig.add_subplot(gs[0])
    ax5 = fig.add_subplot(gs[1])

    _candles(ax15, frames['15'], 100)
    ax15.set_title(f'{symbol} 15M | {signal.grade} {signal.direction} | {signal.state} | Score {signal.score}/100')
    _line(ax15, signal.raid_level, signal.raid_name or 'RAID')
    for name, level in (signal.liquidity or {}).items():
        if level is not None:
            _line(ax15, level, name.upper(), ':')

    _candles(ax5, frames['5'], 140)
    ax5.set_title(f'5M execution | MMXM {signal.mmxm} | PD {signal.pd_zone} | SMT {signal.smt}')
    if signal.entry_low is not None and signal.entry_high is not None:
        ax5.axhspan(float(signal.entry_low), float(signal.entry_high), alpha=0.15)
        _line(ax5, signal.entry_low, 'ENTRY LOW')
        _line(ax5, signal.entry_high, 'ENTRY HIGH')
    _line(ax5, signal.stop, 'SL')
    _line(ax5, signal.tp1, 'TP1')
    _line(ax5, signal.tp2, 'TP2')
    _line(ax5, signal.tp3, 'TP3')
    if signal.ote_low is not None and signal.ote_high is not None:
        ax5.axhspan(float(signal.ote_low), float(signal.ote_high), alpha=0.08)

    info = (
        f'MSS={signal.mss}  CISD={signal.cisd}  DISP={signal.displacement} '
        f'FVG={signal.fvg}  IFVG={signal.ifvg}  OB={signal.order_block}\n'
        f'Draw={signal.draw_name or "-"}  Invalidation={signal.invalidation or "-"}'
    )
    fig.text(0.01, 0.01, info, fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return path
