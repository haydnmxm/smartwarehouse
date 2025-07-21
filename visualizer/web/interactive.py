import plotly.graph_objects as go
from pathlib import Path
from .layout_loader import load_layout
from core.env.state_builder import build_initial_state, load_yaml
from core.env.simulation_engine import SimulationEngine

# ---------- helpers ----------
def zone_color(ratio: float) -> str:
    """0 → белый, 1 → насыщенно‑синий"""
    c = int(255 * (1 - ratio))
    return f"rgb({c},{c},255)"

def make_shapes(state, layout):
    shapes = []
    for z in layout:
        zs = state.zones[z.id]
        fill = zone_color(min(zs.current_qty / zs.capacity, 1) if zs.capacity else 0)
        shapes.append(
            dict(type="rect",
                 x0=z.x, y0=z.y, x1=z.x+z.w, y1=z.y+z.h,
                 line=dict(color="black"), fillcolor=fill, opacity=0.85)
        )
    return shapes

# ---------- build ----------
def build_html(seconds=36000, step=60, out="sim_view.html"):
    cfg      = load_yaml("config/sim_params.yaml")
    layout   = load_layout(Path("config/layout.yaml"))
    state    = build_initial_state({}, cfg)
    engine   = SimulationEngine(state, cfg)

    # первый кадр
    frames = []
    for t in range(0, seconds+1, step):
        frame_shapes = make_shapes(state, layout)
        frames.append(go.Frame(data=[], name=str(t), layout=dict(shapes=frame_shapes)))
        engine.step()

    # начальное отображение
    fig = go.Figure(
        data=[],
        layout=go.Layout(
            title="Warehouse simulation (zone colour = fill level)",
            xaxis=dict(range=[-1, 15], zeroline=False, showticklabels=False),
            yaxis=dict(range=[-1, 10], zeroline=False, showticklabels=False),
            shapes=frames[0].layout.shapes,
            updatemenus=[{
                "type": "buttons",
                "buttons": [{
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 200},
                                    "fromcurrent": True}]
                }]
            }],
            sliders=[{
                "steps": [
                    {"args": [[f.name], {"frame": {"duration": 0},
                                         "mode": "immediate"}],
                     "label": f.name, "method": "animate"}
                    for f in frames],
                "transition": {"duration": 0},
                "x": 0.1, "y": -0.05, "len": 0.8
            }]
        ),
        frames=frames
    )
    fig.write_html(out, auto_play=False)
    print(f"✔ HTML saved → {out}")

if __name__ == "__main__":
    build_html()
