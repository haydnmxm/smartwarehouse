from core.env.event_bus import EventBus
from core.env.models import WorldState

def process(event_bus: EventBus, state: WorldState, cfg: dict):
    emer_cfg = cfg.get("emergency", {})
    if not emer_cfg.get("enabled", True):
        return

    threshold = emer_cfg.get("large_order_qty_threshold", 200)

    for ve in list(event_bus.to_apply):
        if ve.type != "OutboundRequest":
            continue
        qty = ve.norm.get("qty", 0)
        if qty <= threshold:
            continue

        # — сплит —
        client_id = ve.norm["client_id"]
        sku_id    = ve.norm["sku_id"]
        first_part = threshold
        remainder  = qty - first_part

        event_bus.publish(
            source="emergency",
            type_="EmergencyAction",
            payload={
                "action": "split_large_order",
                "ref_event_id": ve.id,
                "original_qty": qty,
                "first_part": first_part,
                "remainder": remainder
            },
            sim_time=state.sim_time
        )

        ve.norm["qty"] = first_part

        event_bus.publish(
            source="emergency",
            type_="OutboundRequest",
            payload={
                "client_id": client_id,
                "sku_id": sku_id,
                "qty": remainder,
                "flagged": True
            },
            sim_time=state.sim_time
        )
