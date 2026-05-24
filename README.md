# Mmxm

X (Twitter) üzerinde takip edilen trader'ların paylaşımlarından **trading stratejilerini çıkarıp backtest eden** araştırma boru hattı.

> Amaç tweet'leri taklit etmek değil; altta yatan setup'ları, indikatör kullanımını ve risk yönetimini öğrenmek ve geçmiş fiyat datasıyla doğrulamak.

## Pipeline

```
   X tweet/thread arşivi
            │
            ▼
   ┌──────────────────┐
   │  1. Scrape       │   src/mmxm/scraping/
   └────────┬─────────┘
            ▼   raw_posts.jsonl
   ┌──────────────────┐
   │  2. LLM parse    │   src/mmxm/parsing/
   │  trade postları  │   -> Trade pydantic model
   └────────┬─────────┘
            ▼   trades.jsonl
   ┌──────────────────┐
   │  3. Pattern mine │   src/mmxm/patterns/
   │  setup örüntüleri│
   └────────┬─────────┘
            ▼   rules.yaml
   ┌──────────────────┐
   │  4. Backtest     │   src/mmxm/backtest/
   │  Binance/CCXT    │
   └────────┬─────────┘
            ▼   reports/
```

## Hızlı kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # değerleri doldur
```

## CLI

```bash
# 1. Scrape — belirli trader'ların son N tweet'i
python -m mmxm scrape --traders config/traders.yaml --since 2024-01-01

# 2. Parse — ham postlardan structured trade çıkar
python -m mmxm parse data/raw/*.jsonl --out data/processed/trades.jsonl

# 3. Pattern — tekrarlanan setup'ları bul
python -m mmxm patterns data/processed/trades.jsonl --out config/rules.yaml

# 4. Backtest — kuralları geçmiş fiyatla doğrula
python -m mmxm backtest config/rules.yaml --symbol BTC/USDT --tf 1h
```

## Klasör yapısı

```
src/mmxm/
  scraping/      # X veri kaynağı (API veya scraping, henüz seçilmedi)
  parsing/       # LLM ile tweet -> Trade çıkarımı
  patterns/      # Trade kümeleri üstünden setup mining
  backtest/      # CCXT ile OHLCV indirme + kural simülasyonu
  data/          # Fiyat datası fetch/cache
  models.py      # Trade, Setup, BacktestResult pydantic modelleri
  cli.py         # Typer CLI giriş noktası

config/
  traders.example.yaml   # takip edilecek X handle listesi
tests/
data/                    # gitignore (raw / processed / cache)
```

## Açık kararlar (sonraki session)

- [ ] Takip edilecek trader listesi (config/traders.yaml)
- [ ] X veri kaynağı: resmi API v2 (paid tier) mi, snscrape benzeri unofficial scrape mı?
- [ ] LLM parse şemasının final hali (TP1/TP2/TP3, leverage, invalidation vs.)

## Lisans

Kişisel araştırma. Üçüncü taraf tweet içeriklerini yeniden yayınlamak için kullanma.
