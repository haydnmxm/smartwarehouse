# core/visualizer/web/layout_loader.py
from pathlib import Path
import yaml
from dataclasses import dataclass

@dataclass
class ZoneShape:
    id: str
    x: int
    y: int
    w: int
    h: int
    type: str       # storage / inbound / outbound / buffer

def load_layout(path: Path) -> list[ZoneShape]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    zones = []
    for z in raw["zones"]:
        zones.append(
            ZoneShape(
                id=z["id"],
                x=z.get("x", 0),
                y=z.get("y", 0),
                w=z.get("w", 1),
                h=z.get("h", 1),
                type=z["type"],
            )
        )
    return zones
