# core/env/travel.py
from __future__ import annotations
from .putaway import choose_zone

def manhattan(z1, z2) -> int:
    return abs(z1.x - z2.x) + abs(z1.y - z2.y)

def compute_travel_seconds(state, from_id, to_id, per_cell=1.5, *, sku=None, qty=1):
    if to_id not in state.zones and sku is not None:
        to_id = choose_zone(sku, qty, state).id
    z1, z2 = state.zones[from_id], state.zones[to_id]
    dx = abs(z1.x - z2.x); dy = abs(z1.y - z2.y)
    return (dx + dy) * per_cell