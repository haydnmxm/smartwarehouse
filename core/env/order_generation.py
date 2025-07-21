# # core/env/order_generation.py
# from __future__ import annotations
# import math, random
# from .models import WorldState, OrderLine

# def poisson(rng: random.Random, lam: float) -> int:
#     """Классический генератор Пуассона (Knuth). lam – среднее за интервал."""
#     L = math.exp(-lam)
#     k, p = 0, 1.0
#     while p > L:
#         k += 1
#         p *= rng.random()
#     return k - 1

# def generate_lines(state: WorldState, cfg: dict):
#     """Вызываем, например, раз в 60 сим-секунд."""
#     orders_cfg = cfg["orders"]
#     # lambda: lines per minute
#     lam = orders_cfg["lines_lambda_per_min"]
#     rng = random.Random(state.rng_seed + state.sim_time)  # простой детерминизм
#     new_count = poisson(rng, lam)

#     # Выбираем зоны-источники для строк (storage)
#     storage_zones = [z.id for z in state.zones.values() if z.type == "storage"]
#     if not storage_zones:
#         return

#     for i in range(new_count):
#         line_id = f"L{len(state.order_lines)+1}"
#         zone_id = rng.choice(storage_zones)
#         # простая длительность: базовое время * множитель по зоне
#         base_pick = orders_cfg.get("line_pick_time_base", 12)
#         zone_mult = cfg["orders"].get("zone_multipliers", {}).get(zone_id, 1.0)
#         work_needed = base_pick * zone_mult
#         deadline_offset = orders_cfg.get("deadline_offset_min", 120) * 60  # в сек
#         line = OrderLine(
#             id=line_id,
#             order_id=None,
#             client_id="C1" if "C1" in state.clients else next(iter(state.clients.keys()), "C?"),
#             sku="SKU1",
#             qty=1,
#             zone_id=zone_id,
#             created_time=state.sim_time,
#             deadline_time=state.sim_time + deadline_offset,
#             work_seconds_needed=work_needed
#         )
#         state.order_lines[line_id] = line
