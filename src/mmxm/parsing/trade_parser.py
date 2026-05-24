"""LLM ile RawPost -> Trade çevirimi (iskelet)."""

from __future__ import annotations

from typing import Optional

from mmxm.models import RawPost, Trade


def parse_post(post: RawPost) -> Optional[Trade]:
    """Tek bir postu Trade'e çevir. Henüz implement edilmedi."""
    raise NotImplementedError("LLM parser sonraki adımda eklenecek.")
