# ICT MMXM Turtle Scanner v2

Bybit USDT perpetual piyasasında 24 saatlik turnover'a göre top-50 pariteyi tarayan deterministik ICT/MMXM/Turtle Soup araştırma scanner'ı.

## V2 kapsamı

- Bybit V5 `linear` / `LinearPerpetual` evreni
- Top-N seçiminde 24h `turnover24h`
- 4H HTF bias / dealing-range bağlamı
- 1H Market Maker Buy Model / Sell Model aday tespiti
- PDH/PDL ve PWH/PWL
- New York saatine göre Asia / London / NY session high-low
- 15M named-liquidity Turtle Soup raid/reclaim
- 5M swing tabanlı BOS/MSS adayı, CISD ve ATR displacement
- FVG / IFVG / basit order block
- Premium/discount ve OTE bandı
- BTC benchmark'lı SMT divergence; BTC için ETH benchmark
- Entry / SL / TP1 / TP2 / TP3 ve R:R
- Draw-on-liquidity ve invalidation
- Setup state machine + SQLite state/history
- MFE/MAE ve outcome tracking
- Annotated 15M + 5M chart PNG
- Telegram'a setup metni + chart gönderimi
- JSON scan arşivi ve outcome özeti
- **Emir göndermez**

Bu motor araştırma amaçlıdır. ICT/MMXM kavramları yoruma açık olduğundan kurallar deterministik olarak kodlanmıştır; forward-test/backtest sonrası eşikler ayarlanmalıdır.

## Setup state machine

```text
WAITING_FOR_RAID
      ↓
LIQUIDITY_SWEPT
      ↓
MSS_CONFIRMED
      ↓
ENTRY_READY
```

SQLite `setup_state` son durumu, `setup_history` yalnız state/direction değişimlerini saklar. `outcomes` tablosu ENTRY_READY setup'ları izler ve MFE/MAE değerlerini R cinsinden günceller.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

`.env`:

```env
TOP_N=50
MIN_SCORE=75
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_ON_CHANGE_ONLY=true
STATE_DB=data/setups.db
CHARTS_ENABLED=true
CHART_DIR=data/charts
```

Public market-data endpointleri için Bybit API key gerekmez.

## Zaman dilimleri

- 4H: 220 mum
- 1H: 300 mum
- 15M: 1000 mum — PDH/PDL, PWH/PWL ve session map
- 5M: 500 mum — execution ve outcome güncelleme

## Skor

V2 skoru maksimum 100'e clamp edilir:

- HTF bias uyumu: 15
- MMXM modeli: 15
- named-liquidity Turtle Soup: 20
- MSS: 15; yalnız BOS varsa 8
- CISD: 10
- displacement: 10
- FVG: 8
- IFVG: 5
- doğru premium/discount tarafı: 4
- SMT: 5

Grade: `A+` 85+, `A` 75-84, `B` 65-74, `NO_TRADE` <65.

## Chart çıktısı

Alarm oluştuğunda `data/charts/` altında 15M ve 5M'i tek PNG'de gösteren chart üretilir. Chart üzerinde named liquidity seviyeleri, raid, entry bandı, OTE bandı, SL, TP1/TP2/TP3 ve structure/confluence özeti bulunur. `ALERT_ON_CHANGE_ONLY=true` ile grafik yalnız setup state/direction değiştiğinde üretilir.

## Outcome tracking

`ENTRY_READY` oluştuğunda entry midpoint, stop ve hedeflerle bir outcome kaydı açılır. Her sonraki taramada son 5M mumla:

- MFE (maximum favorable excursion) R
- MAE (maximum adverse excursion) R
- TP1 / TP2 ilerlemesi
- TP3 kapanışı
- SL kapanışı

izlenir. Aynı mum hem SL hem hedefe dokunuyorsa muhafazakâr olarak SL önce kabul edilir. Scan JSON dosyasının üst kısmında `closed`, `wins`, `losses`, `win_rate`, `avg_mfe_r`, `avg_mae_r` özeti de bulunur.

## Trade plan

Sinyal çıktısı `symbol/direction/score/grade/state`, HTF/MMXM/PD, raid, MSS/CISD/displacement, FVG/IFVG/OB/SMT, OTE, entry, stop, TP1-3, R:R, draw, invalidation ve tam liquidity map içerir.

Entry bölgesi FVG/IFVG/OB ile bulunur; OTE ile kesişim varsa kesişim tercih edilir. Stop son 15M raid ekstremine yerleştirilir. Hedefler internal 1H liquidity, en yakın named draw ve external 1H extreme arasından yönsel sıralanır.

## Test

```bash
pytest -q
```

V2 testleri bir shell/CI checkout'unda çalıştırılmalıdır. Bu branch GitHub connector üzerinden yazıldığı için bu oturumda test sonucu doğrulanmış sayılmamalıdır.

## Sonraki geliştirmeler

1. Breaker block / mitigation block modellerini ayrı objeler olarak eklemek
2. MMXM'i daha ayrıntılı liquidity-engineering phase modeliyle genişletmek
3. Killzone ve day-of-week scoring
4. Outcome tracker'a expectancy, partial TP ve setup-tag bazlı istatistikler
5. Forward-test sonrası opsiyonel ve varsayılan-kapalı execution modülü
