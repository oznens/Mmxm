"""Trade kümeleri üzerinde örüntü çıkarma (iskelet)."""

from __future__ import annotations

from collections.abc import Iterable

from mmxm.models import Setup, Trade


def extract_setups(trades: Iterable[Trade]) -> list[Setup]:
    raise NotImplementedError("Pattern mining sonraki adımda eklenecek.")
