# ICT MMXM Turtle Scanner v1

Bybit USDT perpetual piyasasında 24 saatlik turnover'a göre top-50 pariteyi tarayan deterministik araştırma/scanner prototipi.

## V1 kapsamı

- Bybit V5 `linear` / `LinearPerpetual` evreni
- Top-N seçiminde 24h `turnover24h`
- 4H HTF dealing-range bias
- 1H basit Market Maker Buy/Sell Model aday tespiti
- 15M Turtle Soup liquidity raid + reclaim/rejection
- 5M market structure shift ve FVG
- 0-100 setup skoru
- JSON scan arşivi
- Opsiyonel Telegram alarmı
- **Emir göndermez**

> Bu V1, ICT/MMXM kavramlarını tamamen objektifleştirme denemesidir. Özellikle MMXM/CISD, session liquidity, PDH/PDL, SMT ve displacement kalite filtresi sonraki sürümlerde genişletilecektir.

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
```

Public market-data endpointleri için Bybit API key gerekmez.

## Skor

- HTF uyumu: 20
- MMXM model adayı: 20
- Turtle Soup raid/rejection: 25
- 5M MSS: 20
- 5M FVG: 15

V1'de `MIN_SCORE=75` önerilir. Önce birkaç hafta sinyal günlüğü toplanıp threshold backtest/forward-test ile ayarlanmalıdır.

## Sonraki sürüm

1. PDH/PDL, PWH/PWL, Asia/London/NY session high-low
2. Gerçek swing tabanlı BOS/MSS + CISD
3. Displacement/ATR kalite filtresi
4. BTC/ETH ve korelasyon sepeti SMT
5. Premium/discount + OTE
6. IFVG / breaker / order block
7. Setup state machine (`WAITING_RAID -> MSS -> FVG_RETEST -> READY`)
8. SQLite sonuç takibi, MFE/MAE, win-rate ve R dağılımı
9. Grafik üretimi
10. En son aşamada, ayrı ve varsayılan-kapalı execution modülü
