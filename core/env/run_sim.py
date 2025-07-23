from __future__ import annotations
import argparse
from .state_builder import load_yaml, build_initial_state
from .simulation_engine import SimulationEngine
from .metrics import flush_metrics
from .frame_exporter import snapshot, dump_run
from core.optimizer.client import propose_patch
import random, csv, json, datetime, pathlib, shutil
from dotenv import load_dotenv, find_dotenv
from core.optimizer.schema import ALLOWED_PATCH

load_dotenv(find_dotenv())
frames: list[dict] = []


def _apply_patch(cfg: dict, patch: dict) -> dict:
    """
    Apply only keys declared in core.optimizer.schema.ALLOWED_PATCH.
    Supports вложенные пути через точку.
    """
    applied = {}
    for path, val in (patch or {}).items():
        if path not in ALLOWED_PATCH:
            print(f"Skip unknown key: {path}")
            continue
        spec = ALLOWED_PATCH[path]
        try:
            v = spec["type"](val)
        except Exception:
            print(f"Type mismatch for {path}")
            continue
        # clamp
        v = max(spec["min"], min(v, spec["max"]))
        # пройти по словарю
        target = cfg
        parts = path.split(".")
        for p in parts[:-1]:
            target = target[p]
        target[parts[-1]] = v
        applied[path] = v
    return applied


def _window_metrics(state, window_s: int) -> dict:
    start = max(0, state.sim_time - window_s)
    done = [l for l in state.order_lines.values()
            if l.status == "done" and (l.done_time or 0) > start]
    lead = 0.0
    if done:
        lead = sum((l.done_time - l.created_time) for l in done) / len(done)
    docks_total = len(state.docks) or 1
    busy = sum(1 for d in state.docks.values() if d.status == "busy")
    idle = sum(1 for w in state.workers.values() if w.state == "idle")
    util = (len(state.workers) - idle) / max(1, len(state.workers))
    return {
        "order_lines_done": len(done),
        "dock_util": round(busy / docks_total, 2),
        "avg_lead_time_min": round(lead / 60, 1),
        "worker_util": round(util, 2),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", default="config/layout.yaml")  # не нужен для build_initial_state напрямую, но оставим
    parser.add_argument("--params", default="config/sim_params.yaml")
    parser.add_argument("--shift-seconds", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    sim_cfg = load_yaml(args.params)
    dump_cfg   = sim_cfg.setdefault("dump", {"snap_every_sec": 10,
                                         "keep_snapshots_days": 30})
    snap_every = dump_cfg["snap_every_sec"]
    max_frames = dump_cfg["keep_snapshots_days"] * 86400 // snap_every
    if args.shift_seconds:
        sim_cfg.setdefault("time", {})
        sim_cfg["time"]["shift_seconds"] = args.shift_seconds

    if "files" not in sim_cfg:
        raise ValueError("sim_params.yaml должен содержать секцию files: layout/skus/clients")

    state = build_initial_state({}, sim_cfg, seed=args.seed)
    engine = SimulationEngine(state, sim_cfg)

    shift_end = sim_cfg["time"]["shift_seconds"]
    opt_cfg = sim_cfg.get("optimizer", {})
    period_sec = int(opt_cfg.get("period_min", 1) * 60)
    kpi_targets = opt_cfg.get("kpi_targets", {})

    history: list[dict] = []
    last_summary: str | None = None
    window_start = state.sim_time

    while state.sim_time < shift_end:
        window_end = min(shift_end, window_start + period_sec)
        while state.sim_time < window_end:
            engine.step()
            if state.sim_time % snap_every == 0:
                frames.append(snapshot(state))
                if len(frames) > max_frames:
                    frames.pop(0)

    metrics_win = _window_metrics(state, window_end - window_start)
    patch = propose_patch(metrics_win, kpi_targets, last_summary)
    applied = _apply_patch(sim_cfg, patch)
    if applied:
        print(f"Applied patch: {applied}")
    util = metrics_win.get("worker_util", 0)
    last_summary = f"t={state.sim_time}, changed={len(applied)}, util={util:.0%}"
    history.append({
        "sim_time": state.sim_time,
        "metrics": metrics_win,
        "patch": applied,
    })

    window_start = state.sim_time

    # --- выгрузка ---
    from dataclasses import asdict
    layout_dict = {"zones": [asdict(z) for z in state.zones.values()]}
    dump_run(layout_dict, frames)            # <= сохраняем JSON

    flush_metrics(state)
    reports_dir = pathlib.Path("results/optimizer")
    reports_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.date.today().isoformat()
    csv_path = reports_dir / f"history_{date_tag}.csv"
    md_path = reports_dir / f"{date_tag}.md"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["sim_time", "order_lines_done", "dock_util", "avg_lead_time_min", "patch"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in history:
            m = row["metrics"]
            w.writerow({
                "sim_time": row["sim_time"],
                "order_lines_done": m.get("order_lines_done"),
                "dock_util": m.get("dock_util"),
                "avg_lead_time_min": m.get("avg_lead_time_min"),
                "patch": json.dumps(row["patch"], ensure_ascii=False),
            })

    final_kpi = history[-1]["metrics"] if history else {}
    with md_path.open("w", encoding="utf-8") as m:
        m.write("# Optimizer Report\n\n")
        m.write("## Final KPI vs targets\n")
        for k, v in kpi_targets.items():
            actual = final_kpi.get(k)
            m.write(f"- {k}: {actual} / target {v}\n")
        m.write("\n## History\n")
        for row in history:
            m.write(f"t={row['sim_time']} patch={json.dumps(row['patch'])} metrics={row['metrics']}\n")

    # link latest for viewer
    shutil.copy(csv_path, reports_dir / "latest.csv")
    shutil.copy(md_path, reports_dir / "latest.md")

    print("Simulation finished.")
    print("Open visualizer at visualizer/web/index.html")

if __name__ == "__main__":
    main()
