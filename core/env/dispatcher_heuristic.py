from __future__ import annotations
from .models import WorldState
from .travel import compute_travel_seconds

def assign_lines(state: WorldState):
    active_waves = [w for w in state.waves.values() if w.status == "active"]
    if not active_waves:
        return
    wave = active_waves[0]

    candidates = [state.order_lines[lid] for lid in wave.line_ids if state.order_lines[lid].status == "waiting"]
    if not candidates:
        return

    idle_workers = [w for w in state.workers.values() if w.state == "idle"]

    max_assign = state.live_config.dispatcher_max_assign_per_step
    assigned_this_step = 0

    for worker in idle_workers:
        if assigned_this_step >= max_assign or not candidates:
            break
        line = candidates.pop(0)
        line.status = "assigned"
        line.assigned_worker_id = worker.id
        line.assign_time = state.sim_time
        # travel от текущей позиции работника
        travel_sec = compute_travel_seconds(state, worker.current_zone_id, line.zone_id, per_cell=1.5)
        if line.pick_seconds is None:  # старые линии, если появятся
            line.pick_seconds = line.work_seconds_needed
        line.travel_seconds = int(travel_sec)
        line.work_seconds_needed = int(line.pick_seconds + travel_sec)
        worker.assigned_line_id = line.id
        worker.state = "working"
        worker.progress_seconds = 0.0
        assigned_this_step += 1
