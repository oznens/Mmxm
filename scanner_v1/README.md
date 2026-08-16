# ICT MMXM Turtle Scanner + Paper Dashboard

Bybit USDT perpetual piyasasında 24 saatlik turnover'a göre top-50 pariteyi tarayan deterministik ICT/MMXM/Turtle Soup scanner ve canlı paper-trading dashboard.

## Ana özellikler

- 4H HTF bias, 1H MMXM, 15M Turtle Soup / named liquidity, 5M MSS-CISD-displacement
- PDH/PDL, PWH/PWL, Asia/London/NY high-low
- FVG, IFVG, order block, premium/discount, OTE, SMT
- Entry / SL / TP1 / TP2 / TP3 + R:R + invalidation
- Setup state machine: `WAITING_FOR_RAID -> LIQUIDITY_SWEPT -> MSS_CONFIRMED -> ENTRY_READY`
- Annotated 15M + 5M PNG ve Telegram alarmı
- MFE/MAE outcome tracking
- **1.000 USDT paper başlangıç hesabı**
- **Her işlemde güncel equity'nin %1'i risk**
- Canlı web dashboard: equity, PnL, win-rate, açık/kapalı işlemler, equity curve, setup sıralaması
- Gerçek emir göndermez

## Paper risk modeli

Varsayılanlar:

```env
PAPER_START_BALANCE=1000
PAPER_RISK_PCT=0.01
```

İlk işlemde hedeflenen maksimum stop zararı `1000 x 0.01 = 10 USDT` olur. Pozisyon miktarı:

```text
qty = risk_usdt / abs(entry - stop)
```

Equity 1.080 USDT olursa sonraki risk 10,80 USDT; 940 USDT olursa 9,40 USDT olur. Böylece risk sabit dolar değil, sürekli equity'nin %1'idir.

Paper işlem yalnız `ENTRY_READY` sinyalinde açılır. Aynı paritede açık paper işlem varken ikinci işlem açılmaz. TP3 veya SL ile kapanır. Aynı 5M mum hem SL hem TP3'e dokunursa muhafazakâr olarak SL önce kabul edilir.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Scanner'ı tek sefer çalıştırmak için:

```bash
python main.py
```

Canlı siteyi açmak için:

```bash
python web.py
```

Sonra tarayıcıda:

```text
http://SUNUCU_IP:8000
```

Dashboard scanner'ı varsayılan olarak 300 saniyede bir otomatik çalıştırır; `Şimdi Tara` düğmesi manuel tarama başlatır. `WEB_PORT` ve `SCAN_INTERVAL_SECONDS` `.env` üzerinden değiştirilebilir.

## .env

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TOP_N=50
MIN_SCORE=75
ALERT_ON_CHANGE_ONLY=true
STATE_DB=data/setups.db
CHARTS_ENABLED=true
CHART_DIR=data/charts
PAPER_START_BALANCE=1000
PAPER_RISK_PCT=0.01
SCAN_INTERVAL_SECONDS=300
WEB_PORT=8000
```

Public Bybit market-data endpointleri için API key gerekmez.

## Zaman dilimleri

- 4H: 220 mum
- 1H: 300 mum
- 15M: 1000 mum
- 5M: 500 mum

## Test

```bash
python -m compileall -q ict_scanner tests
python -m pytest -q
```

GitHub Actions her scanner değişikliğinde bu kontrolleri çalıştırır. Testler ICT/confluence kuralları, session timezone, SMT, structure/displacement, MFE/MAE ve paper hesabın %1 risk/position sizing davranışını kapsar.
