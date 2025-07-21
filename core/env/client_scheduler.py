# NOTE: Старый генератор больше не используется напрямую.
# Логика генерации перенесена в SimulationEngine._publish_client_outbound_events(),
# теперь всё идёт через EventBus (OutboundRequest события).

from __future__ import annotations
import math, random
from .models import OrderLine, WorldState
from .travel import compute_travel_seconds

def publish_initial_inbound(state, event_bus, rng):
    """
    Каждому клиенту раз в первый тик предлагает стартовую поставку:
    client.sku_mix может быть списком dict {'sku':..,'weight':..}
    или списком кортежей (sku, weight).
    """
    if state.sim_time != 0:
        return

    for client in state.clients.values():
        for mix in client.sku_mix:
            # подстраиваемся под оба варианта
            if isinstance(mix, dict):
                sku_id = mix["sku"]
            elif isinstance(mix, (list, tuple)) and len(mix) >= 1:
                sku_id = mix[0]
            else:
                # неожиданный формат — пропустим
                continue

            # генерим случайный объём поставки
            qty = rng.randint(80, 150)

            event_bus.publish(
                source="client_gen",
                type_="InboundArrivalActual",
                payload={
                    "client_id":    client.id,
                    "sku_id":       sku_id,
                    "delivered_qty": qty
                },
                sim_time=state.sim_time  # =0
            )

def _poisson(rng: random.Random, lam: float) -> int:
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1

def _weighted_choice(rng: random.Random, items: list[tuple[str, float]]) -> str:
    total = sum(w for _, w in items)
    r = rng.random() * total
    acc = 0.0
    for sku_id, w in items:
        acc += w
        if r <= acc:
            return sku_id
    return items[-1][0]

def schedule_clients_outbound(state: WorldState, sim_cfg: dict, rng: random.Random):
    for client in state.clients.values():
        if state.sim_time < client.next_outbound_time:
            continue

        ob = client.outbound_cfg
        lam = ob['lines_mean']
        batch_count = _poisson(rng, lam)
        if batch_count <= 0:
            batch_count = 1

        for _ in range(batch_count):
            sku_id = _weighted_choice(rng, client.sku_mix)
            sku = state.skus[sku_id]
            zone_id = rng.choice(sku.candidate_zones)

            pick_sec = sku.base_pick_sec
            travel_sec = compute_travel_seconds(state, "DOCK_OUT", zone_id, per_cell=1.5)
            total_work = int(pick_sec + travel_sec)

            line_id = f"L{len(state.order_lines)+1}"
            line = OrderLine(
                id=line_id,
                order_id=None,
                client_id=client.id,
                sku=sku_id,
                qty=1,
                zone_id=zone_id,
                created_time=state.sim_time,
                deadline_time=state.sim_time + 7200,
                work_seconds_needed=total_work,
                pick_seconds=pick_sec,
                travel_seconds=int(travel_sec),
            )
            state.order_lines[line_id] = line

        pattern = ob['pattern']
        if pattern == "interval":
            base = ob['base_interval_min'] * 60
            j = 0
            if 'jitter_min' in ob and 'jitter_max' in ob:
                j = rng.randint(ob['jitter_min'], ob['jitter_max']) * 60
            client.next_outbound_time = state.sim_time + base + j
        elif pattern == "weekly":
            days = ob['days']
            minute_target = ob['time_minute_of_day']
            jitter_min = ob.get('jitter_min', 0)
            jitter_max = ob.get('jitter_max', 0)
            day_sec = 86400
            current_day = state.sim_time // day_sec
            minute_of_day = (state.sim_time % day_sec) // 60
            for off in range(0, 15):
                test_day = current_day + off
                dow = test_day % 7
                if dow in days:
                    if off == 0 and minute_of_day > minute_target:
                        continue
                    target_time = test_day * day_sec + minute_target * 60
                    j = 0
                    if jitter_min or jitter_max:
                        j = rng.randint(jitter_min, jitter_max) * 60
                    target_time += j
                    if target_time <= state.sim_time:
                        continue
                    client.next_outbound_time = target_time
                    break
        else:
            client.next_outbound_time = state.sim_time + 3600
