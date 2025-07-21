from __future__ import annotations
import argparse
from .state_builder import load_yaml, build_initial_state
from .simulation_engine import SimulationEngine
from .metrics import flush_metrics
import random

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", default="config/layout.yaml")  # не нужен для build_initial_state напрямую, но оставим
    parser.add_argument("--params", default="config/sim_params.yaml")
    parser.add_argument("--shift-seconds", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    sim_cfg = load_yaml(args.params)
    if args.shift_seconds:
        sim_cfg.setdefault("time", {})
        sim_cfg["time"]["shift_seconds"] = args.shift_seconds

    if "files" not in sim_cfg:
        raise ValueError("sim_params.yaml должен содержать секцию files: layout/skus/clients")

    state = build_initial_state({}, sim_cfg, seed=args.seed)
    engine = SimulationEngine(state, sim_cfg)

    shift_end = sim_cfg["time"]["shift_seconds"]

    while state.sim_time < shift_end:
        engine.step()

    flush_metrics(state)
    print("Simulation finished.")
    done = len([l for l in state.order_lines.values() if l.status == "done"])
    print(f"Total lines done: {done}")
    # Пример распределения по клиентам
    if state.order_lines:
        from collections import Counter
        cnt = Counter(l.client_id for l in state.order_lines.values())
        print("Lines per client:", dict(cnt))

if __name__ == "__main__":
    main()
