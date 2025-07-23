from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any
import itertools, csv, os
from enum import Enum, auto
from .models import OrderLine
from .travel import compute_travel_seconds
from .putaway import choose_zone

_event_id_counter = itertools.count(1)


class EventType(Enum):
    OUTBOUND_REQUEST = auto()
    INBOUND_ARRIVAL_ACTUAL = auto()
    EMERGENCY_ACTION = auto()
    OUTBOUND_REJECTED = auto()
    CONFIG_PATCH = auto()


@dataclass
class Event:
    ts: int
    source: str
    type: EventType
    payload: dict

def next_event_id() -> str:
    return f"E{next(_event_id_counter)}"

@dataclass
class ProposedEvent:
    id: str
    time: int
    source: str          # "client_gen" | "emergency" | "disruptor" | ...
    type: str            # "OutboundRequest" | "EmergencyAction" | ...
    payload: Dict[str, Any]

@dataclass
class ValidatedEvent:
    id: str
    proposed_id: str
    time: int
    type: str
    source: str
    classification: str      # "ok" | "flag" | "reject"
    norm: Dict[str, Any]
    reason: str | None = None

@dataclass
class AppliedEvent:
    id: str
    validated_id: str
    time: int
    type: str
    effects: List[Dict[str, Any]]

class EventBus:
    """
    Минимальная реализация событийного конвейера.
    """
    def __init__(self, log_path: str = "events.csv"):
        self.proposed: List[ProposedEvent] = []
        self.validated: List[ValidatedEvent] = []
        self.to_apply: List[ValidatedEvent] = []
        self.applied: List[AppliedEvent] = []
        self._log_path = log_path
        self._init_log()

    def _init_log(self):
        if not os.path.exists(self._log_path):
            with open(self._log_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["phase","sim_time","event_id","type","source","classification","reason","payload_summary"])

    def _append_log(self, phase: str, ev_time: int, ev_id: str, type_: str,
                    source: str, classification: str, reason: str | None, payload: Dict[str, Any]):
        summary = ";".join(f"{k}={v}" for k,v in list(payload.items())[:6])
        with open(self._log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([phase, ev_time, ev_id, type_, source, classification, reason or "", summary])

    # ---------- Publish ----------
    def publish(self, source: str, type_: str, payload: Dict[str, Any], sim_time: int) -> ProposedEvent:
        pe = ProposedEvent(id=next_event_id(), time=sim_time, source=source, type=type_, payload=payload)
        self.proposed.append(pe)
        self._append_log("proposed", sim_time, pe.id, pe.type, pe.source, "", "", payload)
        return pe

    # ---------- Validate ----------
    def validate_cycle(self):
        if not self.proposed:
            return
        for pe in self.proposed:
            ve = self._validate_one(pe)
            self.validated.append(ve)
            if ve.classification != "reject":
                self.to_apply.append(ve)
            self._append_log("validated", ve.time, ve.id, ve.type, ve.source, ve.classification, ve.reason, ve.norm)
        self.proposed.clear()

    def _validate_one(self, pe: ProposedEvent) -> ValidatedEvent:
        p = dict(pe.payload)  # копия
        t = pe.type
        # Примитивные проверки
        if t == "OutboundRequest":
            # обязательные поля
            for field in ("client_id","sku_id","qty"):
                if field not in p:
                    return ValidatedEvent(
                        id=pe.id, proposed_id=pe.id, time=pe.time, type=t, source=pe.source,
                        classification="reject", norm={}, reason=f"missing {field}"
                    )
            qty = p["qty"]
            if qty <= 0:
                return ValidatedEvent(pe.id, pe.id, pe.time, t, pe.source, "reject", {}, "qty<=0")
            classification = "ok"
            return ValidatedEvent(pe.id, pe.id, pe.time, t, pe.source, classification, p, None)

        if t == "EmergencyAction":
            # просто пропускаем
            return ValidatedEvent(pe.id, pe.id, pe.time, t, pe.source, "ok", p, None)

        # default pass-through
        return ValidatedEvent(pe.id, pe.id, pe.time, t, pe.source, "ok", p, None)

    # ---------- Apply ----------
    def apply_cycle(self, state):
        if not self.to_apply:
            return
        for ve in self.to_apply:
            effects = self._apply_one(ve, state)
            ae = AppliedEvent(id=ve.id, validated_id=ve.id, time=state.sim_time, type=ve.type, effects=effects)
            self.applied.append(ae)
            self._append_log("applied", state.sim_time, ve.id, ve.type, ve.source, "", "", {"effects": len(effects)})
        self.to_apply.clear()

    def _apply_one(self, ve: ValidatedEvent, state):
            """
            Применяем события к состоянию.
            • OutboundRequest  – отдаём товар в пределах остатка, лишнее отклоняем.
            • InboundArrivalActual – пополняем запас.
            • EmergencyAction – только логируем (уже обработано самим агентом).
            """
            t = ve.type
            p = ve.norm
            effects: List[Dict[str, Any]] = []

            # ---------- 1. OUTBOUND ----------
            if t == "OutboundRequest":
                client_id = p["client_id"]
                sku_id    = p["sku_id"]
                req_qty   = p["qty"]

                # ------------- остаток клиента -------------
                stock = state.stock[client_id].get(sku_id, 0)

                served_qty   = min(req_qty, stock)
                rejected_qty = req_qty - served_qty

                if served_qty > 0:
                    state.stock[client_id][sku_id] = stock - served_qty

                    # ------ выбираем зону через put‑away ------
                    sku_obj   = state.skus[sku_id]
                    zone_id   = choose_zone(sku_obj, served_qty, state).id
                    pick_base = sku_obj.base_pick_sec
                    pick_sec   = pick_base * served_qty
                    travel_sec = compute_travel_seconds(state, "DOCK_OUT", zone_id, per_cell=1.5)
                    work_total = pick_sec + travel_sec

                    line_id = f"L{len(state.order_lines)+1}"
                    line = OrderLine(
                        id=line_id,
                        client_id=client_id,
                        sku=sku_id,
                        qty=served_qty,
                        zone_id=zone_id,
                        created_time=state.sim_time,
                        deadline_time=state.sim_time + 7200,
                        line_type="outbound",
                        work_seconds_needed=work_total,
                        pick_seconds=pick_sec,
                        travel_seconds=travel_sec
                    )
                    state.order_lines[line_id] = line
                    effects.append({"created_line": line_id, "served_qty": served_qty})

                if rejected_qty > 0:
                    self.publish(
                        source="system",
                        type_="OutboundRejected",
                        payload={
                            "client_id": client_id,
                            "sku_id":    sku_id,
                            "qty":       rejected_qty,
                            "reason":    "insufficient_stock"
                        },
                        sim_time=state.sim_time
                    )
                    # для метрик «stock‑outs»
                    state.metrics.stockouts = getattr(state.metrics, "stockouts", 0) + rejected_qty
                    effects.append({"rejected_qty": rejected_qty})
                return effects

            # ---------- 2. INBOUND ----------
            if t == "InboundArrivalActual":
                client_id  = p["client_id"]
                sku_id     = p["sku_id"]
                delivered  = p["delivered_qty"]

                prev = state.stock[client_id].get(sku_id, 0)
                state.stock[client_id][sku_id] = prev + delivered
                effects.append({
                    "inbound_added": delivered,
                    "client": client_id,
                    "sku": sku_id,
                    "new_stock": state.stock[client_id][sku_id]
                })
                return effects

            # ---------- 3. EmergencyAction (сплит и т.д.) ----------
            if t == "EmergencyAction":
                effects.append({"ack": ve.id})
                return effects

            # ---------- default ----------
            return effects