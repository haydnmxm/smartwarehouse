from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal

ZoneType = Literal["storage", "pack", "dock_in", "dock_out", "staging"]
LineStatus = Literal["waiting", "assigned", "done", "canceled"]
WaveStatus = Literal["building", "active", "complete"]
WorkerState = Literal["idle", "moving", "picking", "off", "charging"]

@dataclass
class Zone:
    id: str
    type: ZoneType
    capacity: int
    current_qty: int = 0
    status: str = "active"
    recovery_timer: int = 0
    x: int = 0
    y: int = 0
    w: int = 1
    h: int = 1

@dataclass
class Worker:
    id: str
    role: str
    state: WorkerState = "idle"
    zone_id: Optional[str] = None
    assigned_line_id: Optional[str] = None
    progress_seconds: float = 0.0
    battery: int = 100
    speed_factor: float = 1.0
    # --- новое ---
    travel_remaining: float = 0.0
    pick_remaining: float = 0.0
    phase: Literal["travel", "pick"] | None = None
    current_zone_id: str = "DOCK_OUT"  # добавили для travel

@dataclass
class Client:
    id: str
    name: str
    tier: str = "standard"
    outbound_cfg: dict | None = None
    sku_mix: list[tuple[str, float]] | None = None
    next_outbound_time: int = 0

@dataclass
class OrderLine:
    # --- ОБЯЗАТЕЛЬНЫЕ (без default) ---
    id: str
    client_id: str
    sku: str
    qty: int
    zone_id: str
    created_time: int
    deadline_time: int

    # --- ОПЦИОНАЛЬНЫЕ / С ДЕФОЛТАМИ ---
    order_id: Optional[str] = None
    line_type: str = "outbound"          # "outbound" | "inbound"
    status: str = "waiting"              # waiting | assigned | done | backorder | on_hold
    priority: int = 0

    assigned_worker_id: Optional[str] = None
    assign_time: Optional[int] = None
    start_time: Optional[int] = None
    done_time: Optional[int] = None

    # Трудозатраты
    work_seconds_needed: float = 0.0
    pick_seconds: Optional[float] = None
    travel_seconds: Optional[float] = None

    # Backorder / активация
    backorder_flag: bool = False
    activated_from_backorder_time: Optional[int] = None

    # Прочие расширения
    metadata: Dict[str, str] = field(default_factory=dict)

@dataclass
class Wave:
    id: str
    line_ids: List[str] = field(default_factory=list)
    status: WaveStatus = "building"
    created_time: int = 0
    activated_time: Optional[int] = None
    complete_time: Optional[int] = None
    target_size: int = 0

@dataclass
class SKU:
    id: str
    desc: str
    zone_id: str           # “главная” зона (исторический ярлык)
    base_pick_sec: int
    initial_qty: int
    candidate_zones: list[str] | None = None

# ----------------- док‑станции -----------------
@dataclass
class Dock:
    id: str
    kind: Literal["inbound", "outbound"]
    service_seconds: int = 30*60
    status: Literal["free", "busy"] = "free"
    busy_until: int = 0
    queue: list[str] = field(default_factory=list)

@dataclass
class InventoryRecord:
    sku_id: str
    zone_id: str
    qty: int

@dataclass
class LiveConfig:
    dispatcher_max_assign_per_step: int
    wave_size: int
    wave_build_timeout: int
    look_ahead_lines_per_worker: int = 1

@dataclass
class MetricsAccumulator:
    lines_completed: int = 0
    total_line_latency: float = 0.0
    assigned_count: int = 0
    sla_breach_count: int = 0
    snapshots: List[dict] = field(default_factory=list)

@dataclass
class WorldState:
    sim_time: int
    zones: Dict[str, Zone]
    workers: Dict[str, Worker]
    clients: Dict[str, Client]
    order_lines: Dict[str, OrderLine]
    waves: Dict[str, Wave]
    docks: Dict[str, Dock]
    skus: Dict[str, SKU]
    inventory: Dict[str, InventoryRecord]          # можешь оставить (пока не активно)
    live_config: LiveConfig
    metrics: MetricsAccumulator
    rng_seed: int = 0

    # ---- НОВОЕ ----
    # inventory_simple: dict[str, int] = field(default_factory=dict)   # остаток по SKU (общий)
    # backorders: dict[str, list[str]] = field(default_factory=dict)   # sku_id -> list[line_id] в ожидании
    pending_optimizations: list[dict] = field(default_factory=list)  # для будущего Optimizer
    flags: dict[str, bool] = field(default_factory=dict)             # произвольные флаги (например ‘priority_mode’)
    stock: dict[str, dict[str, int]] = field(default_factory=dict)  # {client_id: {sku_id: qty}}
    