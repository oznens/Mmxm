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


@app.command()
def parse(
    inputs: list[Path] = typer.Argument(..., help="raw JSONL dosyaları"),
    out: Path = typer.Option(Path("data/processed/parsed.jsonl"), "--out"),
    model: str = typer.Option("gemini-2.5-flash", "--model"),
    concurrency: int = typer.Option(2, "--concurrency", help="paralel parse sayısı"),
    rpm: int = typer.Option(4, "--rpm", help="dakika başına istek üst sınırı (Gemini 2.5 Flash free tier 5)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="ilk N posta sınırla"),
    no_images: bool = typer.Option(False, "--no-images", help="grafikleri yollama"),
) -> None:
    """Ham X postlarını LLM ile parse edip ParsedPost JSONL'e yaz."""
    import os

    from dotenv import load_dotenv
    from google import genai

    from mmxm.parsing import parse_batch
    from mmxm.parsing.storage import write_parsed_jsonl
    from mmxm.scraping.storage import read_jsonl

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise typer.BadParameter("GEMINI_API_KEY env değişkeni gerekli.")

    posts = []
    for inp in inputs:
        posts.extend(list(read_jsonl(inp)))
    if limit:
        posts = posts[:limit]
    logger.info(
        "parse başlıyor n_posts={} model={} concurrency={} rpm={}",
        len(posts),
        model,
        concurrency,
        rpm,
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
        )

    results = asyncio.run(_run())
    ok = [(raw, parsed) for raw, parsed, err in results if parsed is not None]
    fail = [(raw, err) for raw, _, err in results if err is not None]
    n_written = write_parsed_jsonl(out, ok)
    logger.info("parse bitti yazılan={} başarısız={} path={}", n_written, len(fail), out)
    if fail:
        for raw, err in fail[:5]:
            logger.warning("  fail id={} err={}", raw.post_id, err)


@app.command()
def patterns(
    trades: Path = typer.Argument(..., help="trades.jsonl"),
    out: Path = typer.Option(Path("config/rules.yaml"), "--out"),
) -> None:
    """Setup örüntülerini çıkar. (TODO)"""
    raise typer.Exit(code=2)


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
