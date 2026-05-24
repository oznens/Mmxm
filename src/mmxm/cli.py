"""Mmxm CLI giriş noktası.

`python -m mmxm <komut>` ile çalışır. Komutlar şimdilik scrape için
hazır; parse/patterns/backtest aşamaları stub.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

app = typer.Typer(add_completion=False, help="Mmxm pipeline CLI")


def _build_backend(source: str, auth_token: Optional[str] = None):
    """Seçilen backend'i import et ve instantiate et."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if source == "api":
        from mmxm.scraping.x_api import XApiBackend

        token = os.environ.get("X_BEARER_TOKEN", "")
        return XApiBackend(bearer_token=token)
    elif source in ("scrape", "scweet"):
        from mmxm.scraping.x_scrape import ScweetBackend

        token = auth_token or os.environ.get("X_AUTH_TOKEN", "")
        return ScweetBackend(auth_token=token)
    else:
        raise typer.BadParameter(f"bilinmeyen source: {source} (scrape | api)")


@app.command()
def scrape(
    traders: Path = typer.Option(..., "--traders", help="traders.yaml yolu"),
    out_dir: Path = typer.Option(Path("data/raw"), "--out", help="JSONL çıkış klasörü"),
    source: str = typer.Option("scrape", "--source", help="scrape (Scweet) | api"),
    auth_token: Optional[str] = typer.Option(
        None,
        "--auth-token",
        help="X auth_token cookie. Boşsa X_AUTH_TOKEN env kullanılır.",
    ),
    since: Optional[datetime] = typer.Option(None, "--since", help="ISO tarih"),
    limit: Optional[int] = typer.Option(None, "--limit", help="kullanıcı başı tweet limiti"),
) -> None:
    """Trader listesini X üzerinden çek, JSONL'e yaz."""
    from mmxm.scraping.runner import scrape_all

    backend = _build_backend(source, auth_token=auth_token)
    summary = asyncio.run(scrape_all(backend, traders, out_dir, since=since, limit=limit))
    for handle, n in summary.items():
        logger.info("özet handle={} n={}", handle, n)


@app.command("import-csv")
def import_csv(
    csv_file: Path = typer.Argument(..., help="TwExportly CSV dump"),
    handle: str = typer.Option(..., "--handle", help="trader handle (örn. jaxiwnl21)"),
    out: Path = typer.Option(..., "--out", help="hedef JSONL (örn. data/raw/jaxiwnl21.jsonl)"),
    include_text_only_replies: bool = typer.Option(
        False,
        "--include-text-replies",
        help="görselsiz reply'leri de dahil et (default: yalnızca media'lı reply)",
    ),
    include_retweets: bool = typer.Option(False, "--include-retweets"),
    merge: bool = typer.Option(
        True,
        "--merge/--overwrite",
        help="mevcut JSONL ile birleştir (dedup), yoksa üzerine yaz",
    ),
) -> None:
    """TwExportly CSV'sini RawPost JSONL'e dönüştür."""
    from mmxm.scraping.csv_import import iter_csv_posts
    from mmxm.scraping.storage import read_jsonl, write_jsonl

    new_posts = list(
        iter_csv_posts(
            csv_file,
            handle=handle,
            include_text_only_replies=include_text_only_replies,
            include_retweets=include_retweets,
        )
    )
    logger.info("CSV'den çıkan post: {} adet", len(new_posts))

    if merge and out.exists():
        existing = list(read_jsonl(out))
        existing_ids = {p.post_id for p in existing}
        added = [p for p in new_posts if p.post_id not in existing_ids]
        merged = existing + added
        n = write_jsonl(out, merged)
        logger.info(
            "merge: mevcut={} CSV'den yeni={} toplam={} → {}",
            len(existing),
            len(added),
            n,
            out,
        )
    else:
        n = write_jsonl(out, new_posts)
        logger.info("overwrite: {} post → {}", n, out)


@app.command()
def parse(
    inputs: list[Path] = typer.Argument(..., help="raw JSONL dosyaları"),
    out: Path = typer.Option(Path("data/processed/parsed.jsonl"), "--out"),
    model: str = typer.Option("gemini-2.5-flash-lite", "--model"),
    concurrency: int = typer.Option(2, "--concurrency", help="paralel parse sayısı"),
    rpm: int = typer.Option(10, "--rpm", help="dakika başına istek üst sınırı (Flash-Lite free tier 15)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="ilk N posta sınırla"),
    no_images: bool = typer.Option(False, "--no-images", help="grafikleri yollama"),
    resume: bool = typer.Option(
        True, "--resume/--no-resume", help="çıktı dosyasında olan post_id'leri atla"
    ),
) -> None:
    """Ham X postlarını LLM ile parse edip ParsedPost JSONL'e yaz."""
    import os

    from dotenv import load_dotenv
    from google import genai

    from mmxm.parsing import parse_batch
    from mmxm.parsing.storage import already_parsed_ids, append_parsed
    from mmxm.scraping.storage import read_jsonl

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise typer.BadParameter("GEMINI_API_KEY env değişkeni gerekli.")

    posts = []
    for inp in inputs:
        posts.extend(list(read_jsonl(inp)))

    skip_ids = already_parsed_ids(out) if resume else set()
    if skip_ids:
        before = len(posts)
        posts = [p for p in posts if p.post_id not in skip_ids]
        logger.info("resume: {} post zaten parsed, {} yeni", before - len(posts), len(posts))

    # --limit resume filter SONRASI uygulanır (yoksa zaten parse edilmiş ilk N
    # post'la dolu chunk gelir, grinder boş iter yapar).
    if limit:
        posts = posts[:limit]

    if not posts:
        logger.info("parse edilecek post yok.")
        return

    logger.info(
        "parse başlıyor n_posts={} model={} concurrency={} rpm={} out={}",
        len(posts),
        model,
        concurrency,
        rpm,
        out,
    )

    client = genai.Client(api_key=api_key)

    async def _run():
        return await parse_batch(
            posts,
            client,
            model=model,
            include_images=not no_images,
            concurrency=concurrency,
            requests_per_minute=rpm,
            on_success=lambda raw, parsed: append_parsed(out, raw, parsed),
        )

    results = asyncio.run(_run())
    ok = sum(1 for _, p, _ in results if p is not None)
    fail = [(raw, err) for raw, p, err in results if p is None]
    logger.info("parse bitti yazılan={} başarısız={} path={}", ok, len(fail), out)
    if fail:
        for raw, err in fail[:5]:
            logger.warning("  fail id={} err={}", raw.post_id, err)


@app.command()
def patterns(
    parsed_file: Path = typer.Argument(..., help="parse aşamasının çıktısı parsed.jsonl"),
    out_report: Path = typer.Option(Path("reports/patterns.json"), "--report"),
    out_trades: Path = typer.Option(Path("data/processed/trade_calls.jsonl"), "--trades"),
) -> None:
    """Parsed postlardan setup örüntülerini ve trade-call'ları çıkar."""
    from mmxm.parsing.storage import read_parsed_jsonl
    from mmxm.patterns import build_report
    from mmxm.patterns.storage import write_report, write_trade_calls

    records = list(read_parsed_jsonl(parsed_file))
    if not records:
        raise typer.BadParameter(f"{parsed_file} boş ya da bulunamadı")
    logger.info("pattern mining n_records={}", len(records))

    report, trade_calls = build_report(records)
    write_report(out_report, report)
    n_trades = write_trade_calls(out_trades, trade_calls)

    logger.info(
        "pattern mining bitti report={} trade_calls={} (n_trades={})",
        out_report,
        out_trades,
        n_trades,
    )
    # Hızlı özet
    logger.info("  trader profilleri ({}):", len(report.trader_profiles))
    for prof in report.trader_profiles:
        logger.info(
            "    @{} posts={} trade_calls={} top_setups={}",
            prof.handle,
            prof.n_posts,
            prof.n_trade_calls,
            [s for s, _ in prof.top_concepts[:5]],
        )
    logger.info("  setup özetleri (top {}):", min(8, len(report.setup_summaries)))
    for s in report.setup_summaries[:8]:
        logger.info(
            "    {} n={} avg_conf={:.2f} handles={}",
            s.setup_name,
            s.n_matches,
            s.avg_confidence,
            dict(s.handles),
        )


@app.command("scan-strategy")
def scan_strategy(
    strategy_name: str = typer.Argument(..., help="strateji adı (turtle_soup, ...)"),
    symbol: str = typer.Option(..., "--symbol", help="ör. BTC/USDT"),
    out: Path = typer.Option(..., "--out", help="çıkış JSONL"),
    timeframe: str = typer.Option("1h", "--tf"),
    since: Optional[datetime] = typer.Option(None, "--since"),
    until: Optional[datetime] = typer.Option(None, "--until"),
    exchange: str = typer.Option("yahoo", "--exchange"),
    target_r: float = typer.Option(3.0, "--target-r"),
    lookback: int = typer.Option(20, "--lookback"),
    htf_tf: Optional[str] = typer.Option(None, "--htf-tf", help="HTF bias filtresi için TF (ör. 1d). Boşsa HTF filtre yok."),
    htf_method: str = typer.Option("ma_cross", "--htf-method", help="ma_cross | ma_slope | close_above_ma"),
    htf_fast: int = typer.Option(9, "--htf-fast"),
    htf_slow: int = typer.Option(21, "--htf-slow"),
) -> None:
    """OHLCV indir, strateji ile tara, sinyalleri TradeCallRecord JSONL'e yaz."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from mmxm.backtest.data import fetch_ohlcv
    from mmxm.strategies import get_strategy

    if since is None:
        since = _dt(2024, 1, 1, tzinfo=_tz.utc)
    if until is None:
        until = _dt.now(_tz.utc)

    logger.info("strateji taraması {} {} {} {} → {}", strategy_name, symbol, timeframe, since.date(), until.date())
    ohlcv = fetch_ohlcv(symbol, timeframe, since=since, until=until, exchange_id=exchange)
    if ohlcv.empty:
        raise typer.BadParameter(f"OHLCV boş: {symbol} {timeframe}")
    logger.info("OHLCV {} bar", len(ohlcv))

    # Sadece strategy'nin __init__'inde olan parametreleri geç
    import inspect

    from mmxm.strategies import REGISTRY
    strat_class = REGISTRY[strategy_name]
    init_params = set(inspect.signature(strat_class.__init__).parameters)
    kwargs = {}
    if "lookback" in init_params:
        kwargs["lookback"] = lookback
    if "target_r" in init_params:
        kwargs["target_r"] = target_r
    strategy = get_strategy(strategy_name, **kwargs)
    signals = strategy.scan(symbol, ohlcv)
    logger.info("ham sinyal sayısı: {}", len(signals))

    # HTF bias filtresi (opsiyonel)
    if htf_tf:
        from mmxm.strategies.htf_filter import filter_signals_by_htf_bias
        # HTF data — daha geniş aralık çek (slow MA için yeterli geçmiş)
        from datetime import timedelta as _td
        htf_since = since - _td(days=90)  # 90 gün ekstra pad
        htf_ohlcv = fetch_ohlcv(symbol, htf_tf, since=htf_since, until=until, exchange_id=exchange)
        if htf_ohlcv.empty:
            logger.warning("HTF data boş, filtre atlanıyor")
        else:
            before = len(signals)
            signals = filter_signals_by_htf_bias(
                signals, htf_ohlcv, method=htf_method,
                fast=htf_fast, slow=htf_slow,
            )
            logger.info(
                "HTF filtre ({} {}, fast={}, slow={}): {} → {} sinyal",
                htf_tf, htf_method, htf_fast, htf_slow, before, len(signals),
            )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for s in signals:
            fh.write(s.model_dump_json() + "\n")
    logger.info("yazıldı → {}", out)

    # Hızlı özet
    if signals:
        longs = sum(1 for s in signals if s.side.value == "long")
        shorts = sum(1 for s in signals if s.side.value == "short")
        logger.info("  long: {} | short: {}", longs, shorts)


@app.command()
def backtest(
    trades_file: Path = typer.Argument(..., help="trade_calls.jsonl"),
    out_results: Path = typer.Option(Path("reports/backtest_results.jsonl"), "--results"),
    out_summary: Path = typer.Option(Path("reports/backtest_summary.json"), "--summary"),
    exchange: str = typer.Option("binance", "--exchange"),
    default_tf: str = typer.Option("1h", "--tf", help="trade'de TF belirtilmezse fallback"),
    max_hold_days: int = typer.Option(90, "--max-hold-days"),
    entry_mode: str = typer.Option(
        "at_market", "--entry-mode",
        help="at_market: post sonrası ilk bar open / limit: declared entry'ye gel bekle",
    ),
) -> None:
    """Trade-call JSONL'ini geçmiş fiyat datasıyla simüle et."""
    from mmxm.backtest import load_trade_calls, run_backtest, write_results, write_summary

    trades = load_trade_calls(trades_file)
    if not trades:
        raise typer.BadParameter(f"{trades_file} boş")
    logger.info("backtest başlıyor n_trades={} exchange={} entry_mode={}", len(trades), exchange, entry_mode)

    results, summary = run_backtest(
        trades,
        exchange_id=exchange,
        default_timeframe=default_tf,
        max_hold_days=max_hold_days,
        entry_mode=entry_mode,
    )
    write_results(out_results, results)
    write_summary(out_summary, summary)

    logger.info("=" * 50)
    logger.info("BACKTEST ÖZETİ")
    logger.info("=" * 50)
    logger.info("Toplam trade:    {}", summary.n_trades_total)
    logger.info("  TP:            {}", summary.n_tp)
    logger.info("  SL:            {}", summary.n_sl)
    logger.info("  Açık (window): {}", summary.n_open)
    logger.info("  No entry:      {}", summary.n_no_entry)
    logger.info("  Skipped:       {}", summary.n_skipped)
    logger.info("Win rate:        {:.1%} ({}/{})", summary.win_rate, summary.n_tp, summary.n_closed)
    logger.info("Total R:         {:+.2f}", summary.total_r)
    logger.info("Avg R:           {:+.2f}", summary.avg_r)
    logger.info("Avg winner R:    {:+.2f}", summary.avg_winner_r)
    logger.info("Avg loser R:     {:+.2f}", summary.avg_loser_r)
    logger.info("Profit factor:   {:.2f}", summary.profit_factor)
    logger.info("Max DD (R):      {:.2f}", summary.max_drawdown_r)
    logger.info("--- per sembol ---")
    for sym, stats in summary.per_symbol.items():
        logger.info("  {} n={} closed={} wr={:.0%} totalR={:+.2f}",
                    sym, stats["n"], stats["n_closed"], stats["win_rate"], stats["total_r"])
    if summary.per_setup:
        logger.info("--- per setup ---")
        for s, stats in summary.per_setup.items():
            logger.info("  {} n={} closed={} wr={:.0%} totalR={:+.2f}",
                        s, stats["n"], stats["n_closed"], stats["win_rate"], stats["total_r"])
    logger.info("Detay → {}", out_results)
    logger.info("Özet  → {}", out_summary)


@app.command("combine-strategies")
def combine_strategies(
    signal_files: list[Path] = typer.Argument(..., help="strateji JSONL'leri"),
    out: Path = typer.Option(..., "--out"),
    rule: str = typer.Option("and", "--rule", help="and | or"),
    time_window_hours: float = typer.Option(4.0, "--window", help="confluence zaman penceresi"),
) -> None:
    """Birden fazla strateji sinyalini birleştir (AND/OR)."""
    from mmxm.comparison import load_jsonl_as_trade_calls
    from mmxm.strategies.combine import combine

    sets = []
    for p in signal_files:
        sigs = load_jsonl_as_trade_calls(p)
        logger.info("yüklenen: {} sinyal ← {}", len(sigs), p)
        sets.append(sigs)

    merged = combine(sets, rule=rule, time_window_hours=time_window_hours)
    logger.info("birleşim ({}): {} → {} confluence sinyali", rule, [len(s) for s in sets], len(merged))

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for s in merged:
            fh.write(s.model_dump_json() + "\n")
    logger.info("yazıldı → {}", out)


@app.command("tune-strategy")
def tune_strategy(
    strategy_name: str = typer.Argument(..., help="turtle_soup | fvg_retest"),
    symbol: str = typer.Option(..., "--symbol"),
    timeframe: str = typer.Option("1h", "--tf"),
    since: Optional[datetime] = typer.Option(None, "--since"),
    until: Optional[datetime] = typer.Option(None, "--until"),
    exchange: str = typer.Option("yahoo", "--exchange"),
    rank_by: str = typer.Option("total_r", "--rank", help="total_r | profit_factor | win_rate"),
    top_n: int = typer.Option(10, "--top", help="rapor: en iyi N kombinasyon"),
    out: Path = typer.Option(Path("reports/tuning.json"), "--out"),
    max_hold_days: int = typer.Option(30, "--max-hold-days"),
    min_signals: int = typer.Option(20, "--min-signals", help="bu sayının altındaki konfigürasyonları ele"),
) -> None:
    """Strateji parametre grid search."""
    import json as _json
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from mmxm.backtest.data import fetch_ohlcv
    from mmxm.strategies import REGISTRY
    from mmxm.strategies.tuning import grid_search

    if since is None:
        since = _dt(2024, 1, 1, tzinfo=_tz.utc)
    if until is None:
        until = _dt.now(_tz.utc)
    if strategy_name not in REGISTRY:
        raise typer.BadParameter(f"strateji bilinmiyor: {strategy_name}")

    logger.info("OHLCV yükleniyor {} {} ...", symbol, timeframe)
    ohlcv = fetch_ohlcv(symbol, timeframe, since=since, until=until, exchange_id=exchange)
    if ohlcv.empty:
        raise typer.BadParameter(f"OHLCV boş: {symbol} {timeframe}")

    # Strategy-spesifik grid
    grids = {
        "turtle_soup": {
            "lookback": [10, 15, 20, 30, 50],
            "sweep_min_pct": [0.0005, 0.001, 0.002, 0.005, 0.01],
            "target_r": [1.5, 2.0, 3.0, 5.0],
            "debounce_bars": [5, 10, 20],
        },
        "fvg_retest": {
            "min_fvg_size_pct": [0.002, 0.005, 0.01, 0.02],
            "max_age_bars": [20, 50, 100],
            "target_r": [1.5, 2.0, 3.0, 5.0],
            "debounce_bars": [5, 10, 20],
        },
    }
    grid = grids[strategy_name]
    strat_class = REGISTRY[strategy_name]

    results = grid_search(
        strat_class, grid, symbol, ohlcv,
        max_hold_days=max_hold_days, rank_by=rank_by, min_signals=min_signals,
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        _json.dumps(
            [{"params": g.params, "n_signals": g.n_signals,
              "summary": g.summary.model_dump(mode="json")} for g in results[:top_n]],
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("=" * 60)
    logger.info("GRID SEARCH SONUÇ (rank: {})", rank_by)
    logger.info("=" * 60)
    logger.info("Toplam değerlendirilen: {} / {} (min_signals filtresi sonrası)",
                len(results), len(list(__import__('itertools').product(*grid.values()))))
    logger.info("")
    logger.info("{:<3} {:<48} {:>6}  {:>5}  {:>7}  {:>5}  {:>5}",
                "#", "PARAMS", "N", "WR%", "TOTAL", "PF", "MDD")
    logger.info("-" * 90)
    for i, g in enumerate(results[:top_n], 1):
        params_str = ", ".join(f"{k}={v}" for k, v in g.params.items())[:47]
        logger.info("{:<3} {:<48} {:>6}  {:>4.0%}  {:>+7.2f}  {:>5.2f}  {:>5.1f}",
                    i, params_str, g.n_signals,
                    g.summary.win_rate, g.summary.total_r,
                    g.summary.profit_factor, g.summary.max_drawdown_r)
    logger.info("Detay → {}", out)


@app.command()
def compare(
    trader_trades: Path = typer.Argument(..., help="trader JSONL (Dreyko/wuipx)"),
    strategy_signals: list[Path] = typer.Argument(..., help="strateji JSONL(ler)"),
    max_hours: float = typer.Option(48.0, "--max-hours", help="eşleşme penceresi"),
    out: Path = typer.Option(Path("reports/comparison.json"), "--out"),
) -> None:
    """Trader çağrıları vs strateji sinyalleri overlap analizi."""
    import json

    from mmxm.comparison import find_matches, load_jsonl_as_trade_calls, overlap_stats

    trader = load_jsonl_as_trade_calls(trader_trades)
    sigs: list = []
    for p in strategy_signals:
        sigs.extend(load_jsonl_as_trade_calls(p))
    logger.info("trader trades: {} | strategy signals: {}", len(trader), len(sigs))

    summaries = find_matches(trader, sigs, max_hours=max_hours)
    stats = overlap_stats(summaries)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({
            "stats": stats,
            "summaries": [s.model_dump(mode="json") for s in summaries],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("=" * 50)
    logger.info("OVERLAP")
    logger.info("=" * 50)
    logger.info("Coverage: {} / {} trader trade'i ({:.0%}) en az 1 strateji eşleşmesine sahip",
                stats["n_with_at_least_one_match"], stats["n_trader_trades"], stats["coverage"])
    logger.info("Ort. eşleşme/trade: {}", stats["avg_matches_per_trade"])
    logger.info("")
    for s in summaries:
        if s.best_match:
            bm = s.best_match
            entry_diff = f"{bm.entry_diff_pct:+.2f}%" if bm.entry_diff_pct is not None else "—"
            target_diff = f"{bm.target_diff_pct:+.2f}%" if bm.target_diff_pct is not None else "—"
            logger.info(
                "✓ [{}] {} {} ({}) → strateji {:+.1f}h, entry∆ {}, target∆ {}",
                s.trader_posted_at.strftime("%m-%d %H:%M"),
                s.trader_symbol, s.trader_side.upper(), s.trader_handle,
                bm.hours_diff, entry_diff, target_diff,
            )
        else:
            logger.info("✗ [{}] {} {} ({}) → eşleşme yok",
                        s.trader_posted_at.strftime("%m-%d %H:%M"),
                        s.trader_symbol, s.trader_side.upper(), s.trader_handle)


if __name__ == "__main__":
    app()
