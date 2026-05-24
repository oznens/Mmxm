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
# 1. Scrape — belirli trader'ların son N tweet'i (Nitter RSS, ücretsiz)
python -m mmxm scrape \
    --traders config/traders.yaml \
    --nitter https://nitter.net,https://nitter.privacydev.net \
    --since 2024-01-01

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

## Veri kaynağı kararı

Şu an **ücretsiz Nitter RSS** backend'i aktif (`src/mmxm/scraping/x_scrape.py`).

- Auth gerekmiyor. `NITTER_INSTANCES` env'i veya `--nitter` flag'iyle bir veya
  daha fazla instance veriyorsun; ilki başarısız olursa sıradakine geçiliyor.
- RSS feed her trader için **yalnızca son ~20 tweet'i** veriyor — tarihsel arşiv
  bu yolla mümkün değil. Derin geçmiş gerekirse `twscrape` benzeri bir backend
  eklenmesi gerekecek (cookie tabanlı, throwaway hesap).
- Public Nitter instance'larının çalışırlık durumu sık değişiyor; canlı liste:
  https://github.com/zedeus/nitter/wiki/Instances

`XApiBackend` stub olarak duruyor — resmi API'ye geçilirse `--source api`.

## Açık kararlar (sonraki session)

- [ ] Takip edilecek trader listesi (`config/traders.yaml`)
- [ ] LLM parse şemasının final hali (TP1/TP2/TP3, leverage, invalidation vs.)
- [ ] Tarihsel veri ihtiyacı doğrulanırsa twscrape backend'i

## Lisans

Kişisel araştırma. Üçüncü taraf tweet içeriklerini yeniden yayınlamak için kullanma.
