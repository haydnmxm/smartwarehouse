ALLOWED_PATCH = {
    "workers.pickers":              {"type": int,   "min": 1,  "max": 40},
    "workers.speed_cells_per_sec":  {"type": float, "min": .5, "max": 3.0},
    "dispatcher.max_assign_per_step":{"type": int,  "min": 1,  "max": 50},
    "orders.lines_lambda_per_min":  {"type": float, "min": 1.0,"max": 60.0},
    "orders.line_pick_time_base":   {"type": float, "min": 5.0,"max": 30.0},
    "orders.zone_multipliers.A":    {"type": float, "min": .8, "max": 1.5},
    "orders.zone_multipliers.B":    {"type": float, "min": .8, "max": 1.5},
    "orders.zone_multipliers.C":    {"type": float, "min": .8, "max": 1.5},
    "waves.size":                   {"type": int,   "min": 20, "max": 500},
    "waves.build_timeout_seconds":  {"type": int,   "min": 60, "max": 900},
    "optimizer.period_min":         {"type": int,   "min": 10, "max": 600},
}