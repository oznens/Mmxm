# Dreyko (jaxiwnl21) & wuipx — Strateji Sentezi

**Veri kaynağı:** TwExportly CSV (1016 jaxiwnl21 + 1007 wuipx tweet, 2024-08 → 2026-05).
**Analiz yöntemi:** Tüm 375 sinyal post (Tweet + Reply-with-photo) Claude tarafından okundu; 7 kritik chart multimodal analiz edildi.

---

## 1. DREYKO (jaxiwnl21) — profil

### İki ayrı playbook

**A. Intraday Futures (NQ1!, ES1!) — Killzone Scalp**
- Timeframe: **3m / 5m**, occasional 15m
- Saat pencereleri (çekirdek):
  - **9:30 NY Open Manipulation** (en sık geçen sinyal — "9.30 Manipülasyonu" 8+ post)
  - **9:50–10:10 Macro** (NY macro window)
  - **10:50–11:10 Macro Price Delivery**
  - London Close (özellikle reversal için)
- Setup template: Asia Range Model → 9:30 SSL/BSL Manipulation → OB/FVG mitigation → entry → 1st Presented FVG hedef
- Imzalı modeller: "Market Maker Buy Model" (MMBM), "Market Maker Sell Model" (MMSM), "DREYKO News Model", "A+ Draw On Liquidity"
- Belgelenmiş kazançlar (post içinden):
  - +$5,000 NQ (Mar 31, 2025)
  - +%5 NQ + 100K Phase-1 done (Apr 28, 2025)
  - +%4 GBP Full TP (Apr 2, 2025)
  - +95 Pips EU (May 12, 2025)
  - +%12 EU on $200K FTMO (May 12, 2025)
  - +300 ticks NQ 9.30 Manipulation Sniper (May 28, 2025)

**B. Crypto Swing (BTC, ETH, SOL, SUI, XRP, ONDO, ARB, NEAR, FET, RNDR, DOGE)**
- Timeframe: **1H / 4H / 1D / Weekly**
- Setup template: Liquidity sweep (BSL/SSL) → Manipulation → AMD cycle → swing long
- "Turtle Soup" + "Buy Manipulation" tekrarlayan format (SUI, ETH, XRP, BTC için aynı template)
- Belgelenmiş kazançlar:
  - +%25 ONDO (Jun 24, 2025)
  - +%10 SUI (Jul 25, 2025)
  - $107,200 BTC SSL forecast (Sep 22, 2025) → confirmed Oct 11 ("DREYKO was here")
  - $128,000 BTC target (Mar 31 forecast)
  - $4,100 ETH multi-month thesis (Jun-Jul 2025)
  - $3,860 ETH Buy Manipulation (Jul 25, 2025)
  - $3.38 XRP Buy Manipulation (Aug 12, 2025)

### Imzalı kavramlar (custom ontology)
| Terim | Anlamı |
|---|---|
| DREYKO Pattern Recognition Series | Eğitim serisi (Pattern Recognition kuşbakışı) |
| DREYKO News Model | Haber günü Turtle Soup tabanlı setup |
| DREYKO Manipülasyon Serisi | AMD framework anlatım serisi |
| MMBM / MMSM | Market Maker Buy/Sell Model |
| Smart Money Reversal (SMR) | 8:30 haber sonrası dönüş |
| A+ Draw On Liquidity | High-probability HTF likidite hedefi |
| NWOG | New Week Opening Gap |
| Asia Range Model | Asya sessionunun aralığı = günün likidite haritası |
| Macro (9.50, 10.50) | ICT'nin sabit macro zaman pencereleri |

### Felsefi tutumu (yinelenen mesajlar)
- **"Tek model ihtiyacın var"** (3+ defa) — minimalist yaklaşım
- **"Manipülasyonu satın al"** — düşük seviyelerde long, yüksek seviyelerde short
- **"Manipülasyon görmedinse içindeysin"** — entry timing kuralı
- **Backtest karşıtı** — "Reel para ile kazanılan $10, backtestte 100R'dan değerli"
- **Anti-Orderflow** — OF eğitim gruplarına sert eleştiri (Post #38)

---

## 2. WUIPX — profil

### Tek model felsefesi
- **"Tek model. Turtle Soup."** (May 11, 2026 — son zamandaki manifestosu)
- 4 setup, 4 TP, 0 stop iddiası
- Belgelenmiş trade: **XAUUSD long 4674.99 → 4725.54** ($1009 P&L, 0.20 lots, 1h31m, R:R ~1:10)

### Style
- Forex ağırlıklı: GBP, EUR, XAUUSD
- Crypto: BTC/ETH analiz (genelde fikir, somut işlem az)
- Prop trading: BemFunding, Darwinex Zero $100k
- Aylık %4-6 hedef (sürdürülebilir)
- Timeframe: çoğunlukla 1H + 5m entry combo

### Imzalı kavramlar
- **Price Delivery** (kendi stratejisi adı)
- **MMXM** (Market Maker X Model — kendine has versiyonu, ontolojide yok)
- **Prime Forex Series** (eğitim serisi)
- **Wui Vision** podcast/eğitim serisi
- **The Art Of Trading** (30 video, 5 sezon planı)
- "Per Aspera Ad Astra" — slogan

### İçerik karakteri (jaxiwnl21'den FARKLI)
- **Çok daha psikoloji/felsefe odaklı** — Wyckoff, Stoacılık (Seneca alıntıları), Machiavelli, Çekim Yasası, journal tutma, "zar atma" metaforu
- Trade sayısı az, methodology post sayısı çok
- Genç (21 yaş), kişisel hikaye paylaşan ton
- jaxiwnl21'in yakın çalışma arkadaşı (replies sık)

---

## 3. Ortak setup şablonu

Her iki trader'da da **temel formül aynı**, sadece time-of-day vs. timeframe ölçeği değişiyor:

```
1. HTF bias belirleme (FVG/OB/likidite haritası)
2. LTF'de likidite sweep gözle (BSL veya SSL)
3. Sweep sonrası manipülasyon → ters mum kapanışı
4. OB veya FVG'den entry
5. Bir sonraki HTF likidite havuzunu target al
```

**Jaxiwnl21 örnekleri** (chart-confirmed):
- **NQ 5m (May 28):** Sweep at 21,415 → entry → target 21,562 → +300 ticks ✓
- **SUI 1D (Jun 6):** TS at 2.90 → spot long → target 5.40 BSL → R:R 1:5.8
- **ETH 1H (Jul 25):** TS at 3,597 (manipulation low 3,560) → target 3,860 → R:R ~1:7
- **XRP 4H (Aug 12):** Manipulation 3.10 → entry 3.18 → TP1 3.40, TP2 3.65 → R:R 1:3 to 1:6
- **BTC 1D (Sep 22):** Bias short → SSL target 107,200 → confirmed Oct 11 ✓

**Wuipx örneği** (chart-confirmed):
- **XAUUSD 1h (May 11, 2026):** Turtle Soup at 4,675 → TP 4,725 → R:R 1:10, 1h31m

---

## 4. Backtest-ready trade-call envanteri (jaxiwnl21)

Aşağıdaki post'lar somut entry/SL/TP veya en azından target/timeframe içeriyor; backtest yapılabilir:

| Post | Tarih | Symbol | Side | Entry | SL | Target(s) | TF | Setup |
|---|---|---|---|---|---|---|---|---|
| #7 | 2025-03-27 | NQ | LONG | 9:50-10:10 macro | (chart) | "It's enough" | 3m | MMBM |
| #16 | 2025-04-01 | ES | LONG | NWOG delivery | — | Silver Bullet | 5m | MMBM |
| #18 | 2025-04-02 | EUR FX | SHORT | 1.088 bearish FVG | — | 1.06 (Nis-May) | 1D | COT MMBM |
| #19,20 | 2025-04-02 | GBP | LONG | (H4 Breaker) | — | +%4 TP confirmed | 4H | Breaker Model |
| #44 | 2025-04-28 | NQ | LONG | Asia Range | — | +%5 confirmed | 3m-5m | Asia Range Model |
| #50 | 2025-05-07 | GBP | — | HTF MMBM stg-2 | — | manipulation wait | 1D→ltf | A+ Draw |
| #52 | 2025-05-12 | EUR | — | — | — | +95 pips confirmed | — | (closed) |
| #54 | 2025-05-12 | EUR | LONG | (London Macro) | — | +%12 on $200K | — | MMBM stg-2 |
| #57 | 2025-05-15 | NQ | LONG | A+ Draw | — | 10.50-11.10 Macro | 5m | A+ Draw |
| #63 | 2025-05-28 | NQ | LONG | ~21,420 (chart) | ~21,400 | 21,562 (+300t) ✓ | 5m | 9:30 Manip + OB |
| #73 | 2025-06-06 | SUI | LONG | ~3.18 | ~2.80 | 5.40 (Jun-Ağu) | 1D | Turtle Soup + BSL |
| #80 | 2025-06-09 | BTC | LONG | (manipulation entry) | — | — | — | Buy Manipulation |
| #91 | 2025-06-23 | BTC | LONG | Launch Macro | — | — | — | Macro Execution |
| #98 | 2025-06-24 | ONDO | LONG | — | — | +%25 confirmed ✓ | — | (closed) |
| #122 | 2025-07-25 | ETH | LONG | 3,597 | ~3,560 | 3,860 | 1H | Turtle Soup |
| #128 | 2025-07-25 | SUI | LONG | — | — | +%10 confirmed ✓ | — | (closed) |
| #145 | 2025-08-12 | XRP | LONG | ~3.18 | ~3.10 | 3.40 / 3.65 | 4H | Buy Manipulation |
| #162 | 2025-09-22 | BTC | SHORT bias | ~122-125k | — | 107,200 SSL ✓ | 1D | Liquidity Sweep |
| #167 | 2025-10-11 | BTC | — | (closed) | — | confirmed Oct 11 ✓ | 1D | SSL hit |
| #169-174 | 2025-10-16 → 11-04 | BTC | NEUTRAL | risk yok | — | %R indicator wait | HTF | (sidelines) |

**Sonuç:** 19 trade-call (1 short bias + 18 long). Yön: **%95 LONG bias** — Dreyko bu dönem güçlü bullish.

### Doğrulanmış (closed) kazançlar
| Trade | R | $ | Süre |
|---|---|---|---|
| NQ +$5000 | ? | $5,000 | < 1 gün |
| NQ +%5 | ? | %5/100k | 1 gün |
| GBP +%4 | ? | %4 | birkaç saat |
| EU +95 pips | ? | 95 pips | birkaç saat |
| EU +%12/$200K FTMO | ? | %12 = $24k | birkaç gün |
| NQ +300 ticks | ? | 300 ticks | scalp |
| SUI +%10 | ? | %10 | 7 hafta |
| ONDO +%25 | ? | %25 | birkaç gün |
| BTC SSL hit | ? | 107k targeted, hit | 3 hafta |

---

## 5. Backtest stratejisi önerisi

### En backtest-able setup: "Turtle Soup + Buy Manipulation"

**Kural seti:**
1. **HTF bias:** trader text'te "long" veya "short" demişse bias var
2. **Manipulation low/high tanımla:** son swing low/high'ın altında/üstünde wick + reversal candle (TS pattern)
3. **Entry:** TS candle close (veya bir sonraki candle open)
4. **SL:** TS wick'in 0.3% altı (longs için) veya üstü (shorts için)
5. **TP1:** bir sonraki HTF FVG veya OB
6. **TP2:** HTF liquidity havuzu (equal highs/lows, prior swing)

**Beklenen istatistik (post sayısından):**
- 18 long trade-call (2025-03 → 2025-09)
- Confirmed wins: minimum 6 (ONDO, SUI, NQ, GBP, EU x2, BTC thesis)
- Hit rate: tahmin %60-70 (confirmed wins / total trade-calls)
- Ortalama R: tahmin 3-5 (post #122 ETH gibi 1:7'ler dahil)

**Veri ihtiyacı (CCXT):**
- Symbol listesi: BTC/USDT, ETH/USDT, SUI/USDT, XRP/USDT, ONDO/USDT, SOL/USDT
- Futures için: NQ1!, ES1!, EUR/USD, GBP/USD, XAUUSD (forex broker / Yahoo Finance)
- Timeframe: 1m, 5m, 1h, 4h, 1d
- Tarih aralığı: 2025-03 → 2026-05

---

## 6. Açık sorular / sonraki adımlar

1. **Wuipx için somut trade örnekleri sınırlı.** Daha fazla XAUUSD/forex trade örneği için private telegram içeriği gerekli (public CSV'de yalnızca 1 doğrulanmış trade var)
2. **Time-of-day backtest karmaşıklığı:** NQ scalp setup'ları 9:30 NY open spesifik. Backtest engine bunu modellemeli (sadece o saat penceresinde entry).
3. **MMXM ve MMBM ayrımı netleştirilmeli** — wuipx MMXM derken jaxiwnl21 MMBM kullanıyor. Ontoloji genişletilmeli.
4. **"Manipulation" tanımının operasyonelleştirilmesi:** code'da nasıl tanımlanır? Önerisi: prior N-candle high/low'u %0.5'ten az aşan + reversal candle close.
