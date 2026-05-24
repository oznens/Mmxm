"""Named setup library — concept set'leri üzerinde predicate'ler.

Her setup bir predicate: bir post'un `concepts` set'i verildiğinde True/False döner.
İlk versiyon kalibrasyon verisindeki gözlemlere dayalı (jaxiwnl21 + wuipx
postlarında öne çıkan motifler). Yeni trader eklenirse genişletilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SetupDefinition:
    name: str
    description: str
    matcher: Callable[[set[str]], bool]
    # Kullanıcıya hangi kavramlar tetikledi diye gösterebilmek için seed seti:
    seed_concepts: frozenset[str]


def _all(s: set[str], *required: str) -> bool:
    return all(c in s for c in required)


def _any(s: set[str], *options: str) -> bool:
    return any(c in s for c in options)


# Setup tanımları — sıralama önemli değil, post birden fazla setup'a uyabilir.
SETUPS: list[SetupDefinition] = [
    SetupDefinition(
        name="amd_cycle",
        description=(
            "Wyckoff/AMD üçlemesi: birikim → manipülasyon → dağıtım döngüsünün "
            "açıkça referans verildiği post"
        ),
        matcher=lambda c: "amd" in c
        or _all(c, "accumulation", "manipulation", "distribution"),
        seed_concepts=frozenset(["amd", "accumulation", "manipulation", "distribution", "wyckoff"]),
    ),
    SetupDefinition(
        name="fvg_retest_entry",
        description="HTF FVG'ye geri test sonrası LTF entry — MTF FVG yaklaşımı",
        matcher=lambda c: "fvg" in c and _any(c, "htf_bias", "ltf_entry"),
        seed_concepts=frozenset(["fvg", "ifvg", "htf_bias", "ltf_entry"]),
    ),
    SetupDefinition(
        name="liquidity_sweep_reversal",
        description="Likidite süpürüldükten sonra ters yön — BSL/SSL alımı + dönüş",
        matcher=lambda c: _any(c, "liquidity_sweep", "bsl", "ssl")
        and _any(c, "choch", "mss", "bos", "ob", "fvg", "manipulation"),
        seed_concepts=frozenset([
            "liquidity_sweep", "bsl", "ssl", "equal_highs", "equal_lows",
            "choch", "mss", "bos",
        ]),
    ),
    SetupDefinition(
        name="turtle_soup",
        description="False breakout entry — Turtle Soup setup",
        matcher=lambda c: "turtle_soup" in c,
        seed_concepts=frozenset(["turtle_soup"]),
    ),
    SetupDefinition(
        name="ob_mitigation",
        description="Order Block veya mitigation block bölgesinden giriş",
        matcher=lambda c: _any(c, "ob", "bullish_ob", "bearish_ob", "mitigation_block"),
        seed_concepts=frozenset([
            "ob", "bullish_ob", "bearish_ob", "mitigation_block",
        ]),
    ),
    SetupDefinition(
        name="breaker_block_play",
        description="Breaker block bölgesinden giriş",
        matcher=lambda c: "breaker_block" in c,
        seed_concepts=frozenset(["breaker_block"]),
    ),
    SetupDefinition(
        name="pd_array_play",
        description="Premium/Discount array referansı — equilibrium etrafı işlemler",
        matcher=lambda c: _any(c, "premium", "discount", "equilibrium", "pd_array"),
        seed_concepts=frozenset(["premium", "discount", "equilibrium", "pd_array"]),
    ),
    SetupDefinition(
        name="killzone_play",
        description="NY/London/Asia killzone zaman pencerelerine referans",
        matcher=lambda c: _any(c, "killzone", "ny_open", "london_open", "asian_session"),
        seed_concepts=frozenset(["killzone", "ny_open", "london_open", "asian_session"]),
    ),
    SetupDefinition(
        name="structure_shift_entry",
        description="BOS / CHoCH / MSS — yapı kırılımı veya değişimi sonrası entry",
        matcher=lambda c: _any(c, "bos", "choch", "mss"),
        seed_concepts=frozenset(["bos", "choch", "mss"]),
    ),
    SetupDefinition(
        name="imbalance_play",
        description="Genel imbalans / inverse FVG / SIBI / BISI",
        matcher=lambda c: _any(c, "imbalance", "ifvg", "sibi", "bisi"),
        seed_concepts=frozenset(["imbalance", "ifvg", "sibi", "bisi"]),
    ),
]


def match_setups(concepts: set[str]) -> list[tuple[SetupDefinition, list[str]]]:
    """Post'un concept set'inden eşleşen tüm setup'ları + tetikleyen kavramları döndür."""
    matches = []
    for setup in SETUPS:
        if setup.matcher(concepts):
            triggered = sorted(concepts & setup.seed_concepts)
            matches.append((setup, triggered))
    return matches


def setup_names() -> list[str]:
    return [s.name for s in SETUPS]
