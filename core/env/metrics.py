from __future__ import annotations
from .models import WorldState
import csv, os, copy

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
    total_w = len(state.workers) or 1
    util = round((total_w - idle) / total_w, 3)

    on_time = [l for l in done_lines if l.done_time <= l.deadline_time]
    otif_pct = 1.0 if not done_lines else round(len(on_time) / len(done_lines), 3)

    capacity_total = sum(z.capacity for z in state.zones.values()) or 1   # защитили 0
    load_pct = sum(z.current_qty for z in state.zones.values()) / capacity_total
    
    waiting_total = sum(1 for l in lines if l.status == "waiting")   # <= ДОБАВИЛИ

    dock_queue = sum(len(d.queue) for d in state.docks.values())
    dock_busy_sec = sum(
        max(0, d.busy_until - state.sim_time)          # сколько ещё заняты
        for d in state.docks.values() if d.status == "busy")
    # ──▲───────────────────────────────────────────────────────────────────

    snap = {
        "t": state.sim_time,
        "load_pct": round(load_pct, 3),
        "otif_pct": otif_pct,
        "util_workers": util,
        "stockouts": getattr(state.metrics, "stockouts", 0),
        "dock_queue": dock_queue,          # сколько фур ждут у доков
        "dock_busy_sec": dock_busy_sec     # суммарно доки заняты, сек
        # ──▲──────────────────────────────────────────────────────────────
    }

    state.metrics.snapshots.append(copy.deepcopy(snap))

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
    } # можно потом использовать чтобы в csv row записи делать

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
