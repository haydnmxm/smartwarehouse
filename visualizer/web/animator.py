# core/visualizer/web/animator.py
import imageio.v2 as imageio
from pathlib import Path

def build_gif(frame_paths: list[Path], out_path: Path, fps: int = 5):
    with imageio.get_writer(out_path, mode="I", fps=fps) as writer:
        for p in frame_paths:
            writer.append_data(imageio.imread(p))
