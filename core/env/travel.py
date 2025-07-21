# core/env/travel.py
from __future__ import annotations

def manhattan(z1, z2) -> int:
    return abs(z1.x - z2.x) + abs(z1.y - z2.y)

def compute_travel_seconds(state, from_zone_id: str | None, to_zone_id: str, per_cell: float = 1.5) -> float:
    if from_zone_id is None:
        from_zone_id = "DOCK_OUT"
    z1 = state.zones[from_zone_id]
    z2 = state.zones[to_zone_id]
    return manhattan(z1, z2) * per_cell
