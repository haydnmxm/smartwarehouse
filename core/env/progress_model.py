from __future__ import annotations
from .models import WorldState
from .models import OrderLine

def advance_progress(state: WorldState, tick: int):
    for w in state.workers.values():
        if w.state in ("idle", "off", "charging") or not w.assigned_line_id:
            continue

        line = state.order_lines[w.assigned_line_id]
        delta = tick * w.speed_factor

        # ---------- TRAVEL ----------
        if w.phase == "travel":
            if delta >= w.travel_remaining:
                delta -= w.travel_remaining
                w.travel_remaining = 0
                w.current_zone_id = line.zone_id      # теперь точно DOCK_IN
                w.phase = "pick"
                w.state = "picking"
                continue             # <‑‑‑ добавь: PICK начнётся в следующий tick
            else:
                w.travel_remaining -= delta
                continue

        # ---------- PICK ----------
        if w.phase == "pick":
            if delta >= w.pick_remaining:
                # работа завершена
                zone = state.zones[line.zone_id]
                zone.current_qty = max(zone.current_qty - line.qty, 0)

                line.status = "done"
                line.done_time = state.sim_time + tick

                if line.line_type == "inbound":
                    # переносим запас из DOCK_IN → целевая зона
                    dest_id  = line.metadata["putaway_target_zone_id"]
                    dest_z   = state.zones[dest_id]
                    src_z    = state.zones[line.zone_id]

                    moved_qty = min(line.qty, src_z.current_qty)
                    src_z.current_qty  -= moved_qty
                    dest_z.current_qty = min(dest_z.capacity, dest_z.current_qty + moved_qty)

                    # перемещаем работника в конечную зону
                    worker_obj = state.workers[line.assigned_worker_id]
                    worker_obj.current_zone_id = dest_id

                w.assigned_line_id = None
                w.state = "idle"
                w.phase = None
                w.pick_remaining = w.travel_remaining = 0
            else:
                w.pick_remaining -= delta
