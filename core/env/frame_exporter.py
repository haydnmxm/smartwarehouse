import json, gzip
from .models import WorldState

def snapshot(state: WorldState) -> dict:
    return {
        "t": state.sim_time,
        "zones": {z.id: z.current_qty for z in state.zones.values()},
        "workers": [
            {"id": w.id, "zone_id": w.current_zone_id, "state": w.state}
            for w in state.workers.values()
        ],
        "metrics": state.metrics.snapshots[-1] if state.metrics.snapshots else {}
    }

def dump_run(layout_cfg: dict, frames: list[dict],
             path: str = "visualizer/web/run_dump.json.gz") -> None:
    payload = {"layout": layout_cfg, "frames": frames}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False,
                  separators=(",", ":"))   # компактная запись