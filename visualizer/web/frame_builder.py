# core/visualizer/web/frame_builder.py
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import cm

# только для подсветки заполненности storage‑зон
STORAGE_CMAP = cm.get_cmap("Blues")        # 0 → светлый, 1 → тёмно‑синий


def draw_frame(state, layout, save_to: str | None = None):
    """
    Строит PNG‑кадр: зоны + метрика + (опционально) работники.
    `layout` – список ZoneShape из layout_loader.load_layout().
    """
    # словарь {zone_id → ZoneShape} для быстрого доступа к координатам
    shape_map = {shape.id: shape for shape in layout}

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_aspect("equal")
    ax.axis("off")

    # ───────── отрисовка зон ─────────
    max_x = max(z.x + z.w for z in layout)
    max_y = max(z.y + z.h for z in layout)

    for shape in layout:
        # заполняемость 0‑1
        z_state = state.zones.get(shape.id)
        ratio = (
            min(z_state.current_qty / z_state.capacity, 1.0)
            if z_state and z_state.capacity else 0.0
        )

        if shape.type == "storage":
            face = STORAGE_CMAP(ratio)
        elif shape.type == "dock_in":
            face = "#81d4fa"
        elif shape.type == "dock_out":
            face = "#a5d6a7"
        else:  # buffer / иное
            face = "#ffe082"

        ax.add_patch(
            patches.Rectangle(
                (shape.x, shape.y), shape.w, shape.h,
                facecolor=face, edgecolor="black", alpha=0.8
            )
        )
        ax.text(
            shape.x + shape.w / 2, shape.y + shape.h / 2,
            shape.id, ha="center", va="center", fontsize=9, weight="bold"
        )

    ax.set_xlim(-1, max_x + 1)
    ax.set_ylim(-1, max_y + 1)

    # ───────── работники (красные круги) ─────────
    if hasattr(state, "workers"):
        for w in state.workers.values():
            zid = getattr(w, "current_zone_id", None)
            if zid and zid in shape_map:
                s = shape_map[zid]
                ax.plot(s.x + s.w / 2, s.y + s.h / 2,
                        "o", markersize=7, color="red")

    # ───────── быстрые метрики ─────────
    tot_cap = sum(z.capacity for z in state.zones.values())
    tot_qty = sum(z.current_qty for z in state.zones.values())
    load_pct = 100 * tot_qty / tot_cap if tot_cap else 0
    otif = getattr(state.metrics, "otif", 0.0)

    ax.text(
        max_x, max_y + 0.25,
        f"Load: {load_pct:5.1f}%   OTIF: {otif:5.1f}%",
        ha="right", va="bottom", fontsize=8
    )

    # ───────── сохранение ─────────
    if save_to:
        fig.savefig(save_to, dpi=120, bbox_inches="tight")
    plt.close(fig)
