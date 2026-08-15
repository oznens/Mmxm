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
- 5M swing tabanlı BOS/MSS adayı
- CISD
- ATR tabanlı displacement kalite filtresi
- FVG ve IFVG
- Basit order-block bölgesi
- Premium/discount ve OTE bandı
- BTC benchmark'lı SMT divergence; BTC için ETH benchmark
- Entry / SL / TP1 / TP2 / TP3 ve R:R hesapları
- Draw-on-liquidity etiketi ve invalidation metni
- Setup state machine ve SQLite state/history kaydı
- Durum değişiminde opsiyonel Telegram alarmı
- JSON scan arşivi
- **Emir göndermez**

Bu motor araştırma amaçlıdır. ICT/MMXM kavramları yoruma açık olduğundan burada kullanılan kurallar deterministik yaklaşım olarak açıkça kodlanmıştır; forward-test/backtest sonrası eşikler ayarlanmalıdır.

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

SQLite `setup_state` tablosu son durumu, `setup_history` ise yalnız state/direction değişimlerini saklar. Böylece aynı setup Telegram'a her taramada tekrar gönderilmez.

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
```

Public market-data endpointleri için Bybit API key gerekmez.

## Zaman dilimleri

- 4H: 220 mum
- 1H: 300 mum
- 15M: 1000 mum — PDH/PDL, PWH/PWL ve session map için
- 5M: 500 mum — execution yapısı için

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

Grade:

- `A+`: 85+
- `A`: 75-84
- `B`: 65-74
- `NO_TRADE`: <65

## Trade plan

Sinyal çıktısı aşağıdakileri içerir:

```text
symbol / direction / score / grade / state
HTF bias / MMXM / PD zone
raid_name / raid_level
MSS / CISD / displacement
FVG / IFVG / order block / SMT
OTE low-high
entry low-high
stop
tp1 / tp2 / tp3
RR TP1 / TP2 / TP3
draw_name
invalidation
full liquidity map
```

Entry bölgesi önce FVG/IFVG/OB ile bulunur; OTE ile kesişim varsa kesişim tercih edilir. Stop son 15M raid ekstremine yerleştirilir. Hedefler internal 1H liquidity, en yakın named draw ve external 1H extreme arasından yönsel olarak sıralanır.

## Test

```bash
pytest -q
```

Testler FVG, named liquidity raid, premium/discount + OTE, SMT divergence, timezone-aware session hesaplama ve displacement/structure mantığını kapsar.

## Sonraki geliştirmeler

1. Breaker block / mitigation block modellerini ayrı objeler olarak eklemek
2. MMXM'i daha ayrıntılı liquidity-engineering phase modeliyle genişletmek
3. Killzone ve day-of-week scoring
4. MFE/MAE, win-rate ve expectancy outcome tracker
5. Otomatik chart PNG üretimi
6. Forward-test sonrası opsiyonel ve varsayılan-kapalı execution modülü
