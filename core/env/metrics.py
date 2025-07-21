from __future__ import annotations
from .models import WorldState
import csv, os

def collect_periodic(state: WorldState, cfg: dict):
    interval = cfg["metrics"].get("sample_interval_seconds", 60)
    if state.sim_time % interval != 0:
        return

    lines = state.order_lines.values()
    done_lines = [l for l in lines if l.status == "done"]
    throughput = 0.0
    if state.sim_time > 0:
        throughput = len(done_lines) / (state.sim_time / 3600)

    avg_latency = 0.0
    if done_lines:
        total = sum((l.done_time - l.created_time) for l in done_lines if l.done_time)
        avg_latency = total / len(done_lines)

    idle = sum(1 for w in state.workers.values() if w.state == "idle")
    total_w = len(state.workers)
    waiting_total = sum(1 for l in lines if l.status == "waiting")

    row = {
        "sim_time": state.sim_time,
        "throughput_lph": round(throughput, 2),
        "done_lines": len(done_lines),
        "avg_line_latency_sec": round(avg_latency, 1),
        "workers_idle": idle,
        "workers_total": total_w,
        "waiting_lines": waiting_total,
        "waves_active": sum(1 for w in state.waves.values() if w.status == "active"),
        "building_wave_size": next((len(w.line_ids) for w in state.waves.values() if w.status=="building"), 0)
    }
    state.metrics.snapshots.append(row)

def flush_metrics(state: WorldState, out_path: str = "metrics_run.csv"):
    if not state.metrics.snapshots:
        return
    write_header = not os.path.exists(out_path)
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=state.metrics.snapshots[0].keys())
        if write_header:
            w.writeheader()
        for r in state.metrics.snapshots:
            w.writerow(r)
