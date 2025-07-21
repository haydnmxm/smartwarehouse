from __future__ import annotations
from .models import WorldState

def advance_progress(state: WorldState, tick_seconds: int):
    for worker in state.workers.values():
        if worker.state != "working" or not worker.assigned_line_id:
            continue
        line = state.order_lines[worker.assigned_line_id]
        worker.progress_seconds += tick_seconds * worker.speed_factor
        if worker.progress_seconds >= line.work_seconds_needed:
            line.status = "done"
            line.done_time = state.sim_time + tick_seconds
            worker.assigned_line_id = None
            worker.state = "idle"
            # обновляем "позицию"
            worker.current_zone_id = line.zone_id
