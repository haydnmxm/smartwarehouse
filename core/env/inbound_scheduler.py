# core/env/inbound_scheduler.py
from __future__ import annotations
from typing import Dict, Any
import random
from random import Random

from .putaway import choose_zone
from .models import OrderLine


# ----------------- helpers -------------------------------------------------
def _poisson(rng: random.Random, lam: float) -> int:
    """Базовый генератор Пуассона; гарантирует минимум 1."""
    L, k, p = pow(2.71828, -lam), 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return max(k - 1, 1)


def _weighted_choice(rng: random.Random, mix):
    """Выбор SKU из client.sku_mix с учётом веса.

    ``mix`` может быть списком словарей ``{"sku": id, "weight": w}`` или
    списком кортежей/списков ``(sku_id, weight)``.
    """
    if not mix:
        return None

    first = mix[0]
    if isinstance(first, dict):
        get_sku = lambda item: item["sku"]
        get_weight = lambda item: item["weight"]
    else:
        get_sku = lambda item: item[0]
        get_weight = lambda item: item[1]

    total = sum(get_weight(item) for item in mix)

    r = rng.uniform(0, total)
    upto = 0.0
    for item in mix:
        upto += get_weight(item)
        if upto >= r:
            return get_sku(item)
    return get_sku(mix[-1])           # fallback (почти не случается)
# ---------------------------------------------------------------------------


def publish_client_inbound_events(state, event_bus, rng: Random):
    """
    Генерируем InboundArrivalActual по расписанию (clients.yaml → inbound).
    Вместо «телепорта» создаём put‑away‑линию, которую возьмут работники.
    """
    for client in state.clients.values():
        cfg: Dict[str, Any] | None = getattr(client, "inbound_cfg", None)
        if not cfg:
            continue

        # Рано: ждём назначенного времени
        if state.sim_time < getattr(client, "next_inbound_time", 0):
            continue

        # ------------------- создаём поставку --------------------------------
        lines_cnt = _poisson(rng, cfg.get("batch_mean_lines", 50))

        for _ in range(lines_cnt):
            sku_id = _weighted_choice(rng, client.sku_mix)
            qty    = _poisson(rng, cfg.get("sku_qty_mean", 30))

            # 1) сгружаем товар во входной док
            dock_zone = state.zones["DOCK_IN"]
            dock_zone.current_qty += qty

            # 2) выбираем целевую зону хранения
            dest_zone = choose_zone(state.skus[sku_id], qty, state)

            # 3) формируем put‑away‑линию (line_type == "inbound")
            line_id   = f"L{len(state.order_lines) + 1}"
            pick_sec  = state.skus[sku_id].base_pick_sec * qty

            put_line = OrderLine(
                id=line_id,
                client_id=client.id,
                sku=sku_id,
                qty=qty,
                zone_id=dock_zone.id,        # брать будем из DOCK_IN
                created_time=state.sim_time,
                deadline_time=state.sim_time + 7200,
                line_type="inbound",
                status="waiting",
                work_seconds_needed=None,    # заполним при назначении
                pick_seconds=pick_sec,
                travel_seconds=None,
                metadata={"putaway_target_zone_id": dest_zone.id}
            )
            state.order_lines[line_id] = put_line

            # событие для возможной аналитики/метрик
            event_bus.publish(
                source   = "client_inbound",
                type_    = "InboundArrivalActual",
                payload  = {
                    "client_id":     client.id,
                    "sku_id":        sku_id,
                    "delivered_qty": qty,
                    "zone_id":       dest_zone.id          # куда планируем положить
                },
                sim_time = state.sim_time
            )

        # ------------------- планируем следующее прибытие --------------------
        pattern = cfg["pattern"]

        if pattern == "interval":
            base_sec   = cfg["base_interval_min"] * 60
            jitter_sec = rng.randint(cfg.get("jitter_min", 0),
                                     cfg.get("jitter_max", 0)) * 60
            client.next_inbound_time = state.sim_time + base_sec + jitter_sec

        elif pattern == "weekly":
            day_sec        = 86_400
            days           = cfg["days"]
            minute_target  = cfg["time_minute_of_day"]
            jitter_min     = cfg.get("jitter_min", 0)
            jitter_max     = cfg.get("jitter_max", 0)

            current_day    = state.sim_time // day_sec
            minute_of_day  = (state.sim_time % day_sec) // 60

            for off in range(0, 15):
                test_day = current_day + off
                dow      = test_day % 7
                if dow not in days:
                    continue

                # если ещё тот же день, но мы уже позже нужного времени — пропускаем
                if off == 0 and minute_of_day > minute_target:
                    continue

                target_time = test_day * day_sec + minute_target * 60
                target_time += rng.randint(jitter_min, jitter_max) * 60

                if target_time > state.sim_time:
                    client.next_inbound_time = target_time
                    break
        else:
            # fallback — раз в сутки
            client.next_inbound_time = state.sim_time + 86_400
