# core/env/dispatcher_heuristic.py
from __future__ import annotations

from .models  import WorldState, OrderLine
from .travel  import compute_travel_seconds


def assign_lines(state: WorldState) -> None:
    """
    Назначаем свободных работников на ожидающие линии.
    Для inbound‑линий считаем только путь до DOCK_IN, чтобы
    действительно «заехать» на док, а дальнейшее перемещение
    выполняется уже в progress_model после PICK‑фазы.
    """
    active_waves = [w for w in state.waves.values() if w.status == "active"]
    if not active_waves:
        return

    wave = active_waves[0]
    candidates = [
        state.order_lines[lid]
        for lid in wave.line_ids
        if state.order_lines[lid].status == "waiting"
    ]
    if not candidates:
        return

    idle_workers = [w for w in state.workers.values() if w.state == "idle"]
    max_assign   = state.live_config.dispatcher_max_assign_per_step
    assigned     = 0

    for worker in idle_workers:
        if assigned >= max_assign or not candidates:
            break

        line = candidates.pop(0)

        # ---------- расчёт таймингов ----------
        if line.line_type == "inbound":
            # едем только до дока
            travel_sec = compute_travel_seconds(
                state, worker.current_zone_id, line.zone_id, per_cell=1.5
            )
            if line.pick_seconds is None:
                sku_obj = state.skus[line.sku]
                line.pick_seconds = sku_obj.base_pick_sec * line.qty
        else:
            travel_sec = compute_travel_seconds(
                state, worker.current_zone_id, line.zone_id, per_cell=1.5
            )
            if line.pick_seconds is None:
                line.pick_seconds = line.work_seconds_needed

        line.travel_seconds = int(travel_sec)
        if line.work_seconds_needed is None:
            line.work_seconds_needed = line.pick_seconds + line.travel_seconds

        # ---------- записываем назначение ----------
        line.status              = "assigned"
        line.assigned_worker_id  = worker.id
        line.assign_time         = state.sim_time

        worker.travel_remaining  = travel_sec
        worker.pick_remaining    = line.pick_seconds
        worker.phase             = "travel"
        worker.state             = "moving"
        worker.assigned_line_id  = line.id
        worker.progress_seconds  = 0.0

        assigned += 1
