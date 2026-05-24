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


def _build_backend(source: str, nitter_instances: Optional[str] = None):
    """Seçilen backend'i import et ve instantiate et."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if source == "api":
        from mmxm.scraping.x_api import XApiBackend

        token = os.environ.get("X_BEARER_TOKEN", "")
        return XApiBackend(bearer_token=token)
    elif source in ("scrape", "nitter"):
        from mmxm.scraping.x_scrape import NitterScrapeBackend

        raw = nitter_instances or os.environ.get("NITTER_INSTANCES", "")
        instances = [u.strip() for u in raw.split(",") if u.strip()]
        return NitterScrapeBackend(instances=instances)
    else:
        raise typer.BadParameter(f"bilinmeyen source: {source} (api | scrape)")


@app.command()
def scrape(
    traders: Path = typer.Option(..., "--traders", help="traders.yaml yolu"),
    out_dir: Path = typer.Option(Path("data/raw"), "--out", help="JSONL çıkış klasörü"),
    source: str = typer.Option("scrape", "--source", help="scrape (Nitter RSS) | api"),
    nitter: Optional[str] = typer.Option(
        None,
        "--nitter",
        help="Virgülle ayrılmış Nitter instance URL'leri. Boşsa NITTER_INSTANCES env kullanılır.",
    ),
    since: Optional[datetime] = typer.Option(None, "--since", help="ISO tarih"),
    limit: Optional[int] = typer.Option(None, "--limit", help="kullanıcı başı tweet limiti"),
) -> None:
    """Trader listesini X üzerinden çek, JSONL'e yaz."""
    from mmxm.scraping.runner import scrape_all

    backend = _build_backend(source, nitter_instances=nitter)
    summary = asyncio.run(scrape_all(backend, traders, out_dir, since=since, limit=limit))
    for handle, n in summary.items():
        logger.info("özet handle={} n={}", handle, n)


@app.command()
def parse(
    inputs: list[Path] = typer.Argument(..., help="raw JSONL dosyaları"),
    out: Path = typer.Option(Path("data/processed/trades.jsonl"), "--out"),
) -> None:
    """Ham postları LLM ile parse edip Trade JSONL'e yaz. (TODO)"""
    raise typer.Exit(code=2)  # henüz implement edilmedi


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
