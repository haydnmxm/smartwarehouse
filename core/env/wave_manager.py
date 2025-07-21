from __future__ import annotations
from .models import WorldState, Wave

def ensure_building_wave(state: WorldState):
    building = [w for w in state.waves.values() if w.status == "building"]
    if building:
        return building[0]
    wave_id = f"W{len(state.waves)+1}"
    wave = Wave(id=wave_id, created_time=state.sim_time, target_size=state.live_config.wave_size)
    state.waves[wave_id] = wave
    return wave

def update_waves(state: WorldState, cfg: dict):
    wave = ensure_building_wave(state)
    waiting_lines = [l for l in state.order_lines.values() if l.status == "waiting" and l.id not in wave.line_ids]
    for line in waiting_lines:
        if len(wave.line_ids) >= wave.target_size:
            break
        wave.line_ids.append(line.id)

    timeout = cfg["waves"].get("build_timeout_seconds", 300)
    if (len(wave.line_ids) >= wave.target_size) or (state.sim_time - wave.created_time >= timeout):
        wave.status = "active"
        if wave.activated_time is None:
            wave.activated_time = state.sim_time

    for w in state.waves.values():
        if w.status == "active":
            if all(state.order_lines[lid].status == "done" for lid in w.line_ids):
                w.status = "complete"
                w.complete_time = state.sim_time
