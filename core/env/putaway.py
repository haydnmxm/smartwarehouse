from typing import Callable
from .models import WorldState, Zone, SKU

_AGENT_CB: Callable | None = None

def register_agent(cb: Callable):           # остаётся
    global _AGENT_CB
    _AGENT_CB = cb

def _default_zone(sku: SKU, qty: int, state: WorldState) -> Zone:
    """
    Very simple put‑away:
    1) пробуем candidate_zones, но оставляем только те, что реально
       существуют и являются storage;
    2) если список пуст – берём все storage зоны;
    3) возвращаем зону с минимальной заполненностью,
       но у которой ещё осталось место для qty.
    """
    # ← 1. фильтруем только валидные storage‑ID
    cand = [
        zid for zid in (sku.candidate_zones or [])
        if zid in state.zones and state.zones[zid].type == "storage"
    ]

    # ← 2. если после фильтрации ничего не осталось — берём все storage
    if not cand:
        cand = [zid for zid, z in state.zones.items() if z.type == "storage"]

    # ← 3. ищем свободные, потом минимально заполнённую
    free = [
        state.zones[zid] for zid in cand
        if state.zones[zid].current_qty + qty <= state.zones[zid].capacity
    ]
    pool = free or [state.zones[zid] for zid in cand]
    return min(pool, key=lambda z: z.current_qty / z.capacity)

def choose_zone(sku: SKU, qty: int, state: WorldState) -> Zone:
    # 0) попробуем «явную» зону, если она существует
    if getattr(sku, "zone", None) in state.zones:
        return state.zones[sku.zone]

    # 1) агент‑оптимизатор
    if _AGENT_CB:
        z = _AGENT_CB(sku, qty, state)
        if z:
            return z

    # 2) дефолт
    return _default_zone(sku, qty, state)
