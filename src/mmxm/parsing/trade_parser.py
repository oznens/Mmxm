"""LLM ile RawPost -> Trade çevirimi.

Kritik nokta: trader'ların çoğu setup'larını **grafik ekran görüntüsü** olarak
paylaşıyor (TradingView snapshot, fiyat seviyeleri ekran görüntüsü vs.). Metni
parse etmek tek başına yetersiz — `RawPost.media_urls`'deki görselleri de Claude
API'ye multimodal mesaj olarak göndereceğiz (image_url block'ları).

Bu modül şimdilik şema/imza tanımıyor; somut Anthropic çağrısı sonraki adımda
eklenecek.
"""

from __future__ import annotations

from typing import Optional

from mmxm.models import RawPost, Trade


def parse_post(post: RawPost, *, fetch_images: bool = True) -> Optional[Trade]:
    """Tek bir postu Trade'e çevir.

    Args:
        post: Scraper'dan gelen ham X postu.
        fetch_images: True ise `post.media_urls` görselleri Claude'a multimodal
            input olarak gönderilir (grafik üzerindeki seviye/indikatör çıkarımı için).

    Şu an iskelet — Anthropic SDK çağrısı + structured output prompt sonraki
    adımda eklenecek.
    """
    raise NotImplementedError("LLM parser sonraki adımda eklenecek.")
