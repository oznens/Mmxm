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


@app.command()
def backtest(
    rules: Path = typer.Argument(..., help="rules.yaml"),
    symbol: str = typer.Option("BTC/USDT", "--symbol"),
    tf: str = typer.Option("1h", "--tf"),
) -> None:
    """Kuralları geçmiş fiyat datasıyla simüle et. (TODO)"""
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
