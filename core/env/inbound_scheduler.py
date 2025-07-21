# core/env/inbound_scheduler.py
from __future__ import annotations
from typing import Dict, Any
import random
from random import Random
from .putaway import choose_zone

def _poisson(rng: random.Random, lam: float) -> int:
    L, k, p = pow(2.71828, -lam), 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return max(k - 1, 1) 

def _weighted_choice(rng: random.Random, mix):
    total = sum(item["weight"] for item in mix)
    r = rng.uniform(0, total)
    upto = 0
    for item in mix:
        upto += item["weight"]
        if upto >= r:
            return item["sku"]
    return mix[-1]["sku"]           # если случится точное совпадение

def publish_client_inbound_events(state, event_bus, rng):
    """
    Генерируем InboundArrivalActual по расписанию, если в clients.yaml
    у клиента есть секция `inbound`.
    """
    for client in state.clients.values():
        cfg: Dict[str, Any] | None = getattr(client, "inbound_cfg", None)
        if not cfg:
            continue

        # ждём своего времени
        if state.sim_time < getattr(client, "next_inbound_time", 0):
            continue

        # --- сколько SKU привезли ---
        lines_cnt = _poisson(rng, cfg.get("batch_mean_lines", 50))
        for _ in range(lines_cnt):
            sku_id = _weighted_choice(rng, client.sku_mix)
            qty    = _poisson(rng, cfg.get("sku_qty_mean", 30))

            # ❷ логика размещения + обновление ёмкости
            zone = choose_zone(state.skus[sku_id], qty, state)
            zone.current_qty += qty

            event_bus.publish(
                source   = "client_inbound",
                type_    = "InboundArrivalActual",
                payload  = {
                    "client_id":     client.id,
                    "sku_id":        sku_id,
                    "delivered_qty": qty,
                    "zone_id":       zone.id
                },
                sim_time = state.sim_time
            )

        # --- Пересчитываем следующий приезд ---
        pattern = cfg["pattern"]
        if pattern == "interval":
            base_sec   = cfg["base_interval_min"] * 60
            jitter_sec = rng.randint(cfg.get("jitter_min", 0),
                                     cfg.get("jitter_max", 0)) * 60
            client.next_inbound_time = state.sim_time + base_sec + jitter_sec

        elif pattern == "weekly":
            days = cfg["days"]
            minute_target = cfg["time_minute_of_day"]
            jitter_min = cfg.get("jitter_min", 0)
            jitter_max = cfg.get("jitter_max", 0)
            day_sec = 86400
            current_day = state.sim_time // day_sec
            minute_of_day = (state.sim_time % day_sec) // 60
            for off in range(0, 15):
                test_day = current_day + off
                dow = test_day % 7
                if dow in days:
                    # пропускаем, если уже поздно в тот же день
                    if off == 0 and minute_of_day > minute_target:
                        continue
                    target_time = test_day * day_sec + minute_target * 60
                    jitter = rng.randint(jitter_min, jitter_max) * 60
                    target_time += jitter
                    if target_time <= state.sim_time:
                        continue
                    client.next_inbound_time = target_time
                    break

        else:  # дефолт
            client.next_inbound_time = state.sim_time + 86400
