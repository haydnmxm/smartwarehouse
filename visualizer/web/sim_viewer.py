# core/visualizer/web/sim_viewer.py
import tempfile, shutil
from pathlib import Path

from core.env.state_builder import load_yaml, build_initial_state
from core.env.simulation_engine import SimulationEngine
from .layout_loader import load_layout
from .frame_builder import draw_frame
from .animator import build_gif


# ───────── инициализация движка ─────────
def init_engine(seed: int = 42) -> SimulationEngine:
    sim_cfg = load_yaml("config/sim_params.yaml")
    state = build_initial_state({}, sim_cfg, seed=seed)
    return SimulationEngine(state, sim_cfg)


# ───────── основной рендер ─────────
def run_and_render(run_seconds: int = 3600, fps: int = 4):
    """
    Прогоняет симуляцию и собирает GIF.
    run_seconds – сколько сим‑секунд моделировать.
    fps         – кадров в секунду у итогового GIF.
    """
    layout = load_layout(Path("config/layout.yaml"))
    engine = init_engine()

    tmp_dir = Path(tempfile.mkdtemp())
    frame_paths = []

    step_sec = 60                        # кадр раз в игровую минуту
    for t in range(0, run_seconds, step_sec):
        engine.step()                    # один сим‑шаг
        frame_path = tmp_dir / f"frame_{t:06d}.png"
        draw_frame(engine.state, layout, save_to=frame_path)
        frame_paths.append(frame_path)

    build_gif(frame_paths, Path("simulation.gif"), fps=fps)
    shutil.rmtree(tmp_dir)
    print("✔ simulation.gif ready")


if __name__ == "__main__":
    run_and_render()
