from typing import Callable
from .models import WorldState, Zone

_AGENT_CB: Callable | None = None

def register_agent(cb: Callable):
    """Optimiser agent will call this later."""
    global _AGENT_CB
    _AGENT_CB = cb

def choose_zone(sku, qty: int, state: WorldState) -> Zone:
    # 1) Спросим агента‑оптимизатора
    if _AGENT_CB:
        z = _AGENT_CB(sku, qty, state)
        if z:
            return z

    # 2) Дефолтная эвристика: candidate_zones → все storage
    cand = sku.candidate_zones or state.zones.keys()
    for zid in cand:
        zone = state.zones[zid]
        if zone.current_qty + qty <= zone.capacity:
            return zone
    for zone in state.zones.values():
        if zone.type == "storage" and zone.current_qty + qty <= zone.capacity:
            return zone

    # 3) Склад полон: просто вернём первую storage-зону (overflow)
    return next(z for z in state.zones.values() if z.type == "storage")
