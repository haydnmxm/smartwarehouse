from __future__ import annotations
import random
from pathlib import Path
import yaml
from .models import (
    Zone, Worker, Dock, Client, SKU, InventoryRecord,
    LiveConfig, MetricsAccumulator, WorldState
)
from .data_loader import load_layout, load_skus, load_clients


# -------------------- служебка --------------------
def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# -------------------- основной конструктор --------------------
def build_initial_state(layout_cfg: dict, sim_cfg: dict, seed: int = 42) -> WorldState:
    rng = random.Random(seed)

    # пути к конфиг‑файлам
    files_cfg   = sim_cfg.get("files", {})
    layout_path = files_cfg.get("layout",  "config/layout.yaml")
    skus_path   = files_cfg.get("skus",    "config/skus.yaml")
    clients_path= files_cfg.get("clients", "config/clients.yaml")

    # загружаем исходные структуры
    zones        = load_layout(layout_path)           # dict[str, Zone]
    skus         = load_skus(skus_path)               # dict[str, SKU]
    clients_raw  = load_clients(clients_path)         # dict[str, Client]

    # клиенты (можем обогатить при необходимости)
    clients: dict[str, Client] = {cid: c for cid, c in clients_raw.items()}

    # ------- создаём работников -------
    workers = {}
    pickers_count = sim_cfg.get("workers", {}).get("pickers", 5)
    for i in range(1, pickers_count + 1):
        wid = f"W{i}"
        workers[wid] = Worker(
            id=wid,
            role="picker",
            state="idle",
            speed_factor=1.0 + rng.uniform(-0.05, 0.05),
            current_zone_id="DOCK_OUT"
        )

    # ------- live‑конфиг симуляции -------
    live_config = LiveConfig(
        dispatcher_max_assign_per_step = sim_cfg.get("dispatcher", {}).get("max_assign_per_step", 10),
        wave_size                      = sim_cfg.get("waves", {}).get("size", 100),
        wave_build_timeout             = sim_cfg.get("waves", {}).get("build_timeout_seconds", 300),
        look_ahead_lines_per_worker    = sim_cfg.get("dispatcher", {}).get("look_ahead_lines_per_worker", 1)
    )

    metrics = MetricsAccumulator()

    # ------- формируем стартовый инвентарь и заполняем зоны -------
    inventory: dict[str, InventoryRecord] = {}
    for sku in skus.values():
        if not sku.candidate_zones:
            sku.candidate_zones = [sku.zone_id]

        inv = InventoryRecord(
            sku_id   = sku.id,
            zone_id  = sku.zone_id,
            qty      = sku.initial_qty
        )
        inventory[f"{sku.id}_{sku.zone_id}"] = inv

        # ⬇⬇ добавляем стартовый объём в ёмкость зоны
        if sku.zone_id in zones:
            zones[sku.zone_id].current_qty += sku.initial_qty

    # ------- «карманы» клиентов -------
    stock_map: dict[str, dict[str, int]] = {
        cid: {sku_id: 0 for sku_id in skus.keys()} for cid in clients.keys()
    }

    docks = {
        "D_IN":  Dock(id="D_IN",  kind="inbound"),
        "D_OUT": Dock(id="D_OUT", kind="outbound")
    }

    # ------- финальный объект состояния -------
    state = WorldState(
        pending_optimizations=[],
        flags={},
        sim_time=0,
        docks=docks,
        zones=zones,
        workers=workers,
        clients=clients,
        order_lines={},
        waves={},
        skus=skus,
        inventory=inventory,
        live_config=live_config,
        metrics=metrics,
        rng_seed=seed,
        stock=stock_map
    )
    return state
