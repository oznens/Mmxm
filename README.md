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
# 1. Scrape — belirli trader'ların timeline'ı (Scweet, cookie tabanlı)
#    X_AUTH_TOKEN env'ini doldur veya --auth-token ver.
python -m mmxm scrape \
    --traders config/traders.yaml \
    --since 2024-01-01 \
    --limit 500

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

## Veri kaynağı

[**Scweet**](https://github.com/Altimis/Scweet) (`src/mmxm/scraping/x_scrape.py:ScweetBackend`).

- Auth: bir X hesabına login olup DevTools > Cookies > `auth_token` değerini
  `X_AUTH_TOKEN` env'ine koy. Throwaway hesap önerilir (banlanma riski var).
- Scweet GraphQL endpoint'lerini kullandığı için tarihsel arşiv erişimi var —
  `--since` ile aylar/yıllar geriye gidilebilir.
- Reply filtresi GraphQL düzeyinde (`tweet_type="exclude_replies"`); `include_replies`
  flag'i ile dahil edilebilir.
- Günlük kota: `--limit` set etmek şart, yoksa hesap kotası tükenir.

`XApiBackend` stub olarak duruyor — resmi API'ye geçilirse `--source api`.

## Grafik (chart) okuma

Trader'ların büyük çoğunluğu setup'ı **TradingView ekran görüntüsü** olarak
paylaşıyor. Scweet `media.image_links`'i veriyor, biz `RawPost.media_urls` olarak
saklıyoruz. LLM parse aşamasında bu görseller Claude API'ye multimodal input
olarak (image block) gönderilecek; metin + grafik birlikte değerlendirilince
entry/stop/target seviyeleri ve indikatörler chart'tan da çıkarılabilir.

## Açık kararlar (sonraki session)

- [x] Takip edilecek trader listesi → `jaxiwnl21`, `wuipx` (`config/traders.yaml`)
- [ ] LLM parse şemasının final hali (TP1/TP2/TP3, leverage, invalidation vs.)
- [ ] Görsel + metin için Claude prompt tasarımı

## Lisans

Kişisel araştırma. Üçüncü taraf tweet içeriklerini yeniden yayınlamak için kullanma.
