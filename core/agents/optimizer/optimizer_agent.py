import json
import csv
import datetime
import pathlib
import time
from typing import Dict, Any

try:
    import openai  # type: ignore
except Exception:  # noqa: BLE001
    openai = None

from core.env.models import WorldState, Worker
from core.env.metrics import rollup

SYSTEM_PROMPT = (
    "\nYou are a warehouse optimisation agent. "
    "Target OTIF \u2265 {otif}, mean_cycle_s \u2264 {cycle}, dock_queue \u2264 {queue}.\n"
    "Return ONLY via `propose_patch` with schema provided."
)

PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "delta": {"type": "integer"},
                    "zone_id": {"type": "string"},
                    "priority": {"type": "integer"},
                    "percent": {"type": "integer"},
                },
                "required": ["type"],
            },
        }
    },
    "required": ["actions"],
}

ALLOWED_ACTIONS = {"add_workers", "set_zone_priority", "tune_speed"}


def _assistant_cache_path(model: str) -> pathlib.Path:
    return pathlib.Path(f".assistant_{model}.id")


def get_or_create_assistant(model: str, kpi_targets: Dict[str, Any]) -> str:
    cache = _assistant_cache_path(model)
    if cache.exists():
        return cache.read_text().strip()

    if openai is None:
        raise RuntimeError("openai package not available")

    assistant = openai.beta.assistants.create(
        name="optimizer",
        model=model,
        instructions=SYSTEM_PROMPT.format(
            otif=kpi_targets.get("otif"),
            cycle=kpi_targets.get("mean_cycle_s"),
            queue=kpi_targets.get("dock_queue"),
        ),
        tools=[{
            "type": "function",
            "function": {"name": "propose_patch", "parameters": PATCH_SCHEMA},
        }],
    )
    cache.write_text(assistant.id)
    return assistant.id


def call_optimizer(snapshot_path: str, cfg: Dict[str, Any]) -> Dict[str, Any] | None:
    if openai is None:
        return None

    assistant_id = get_or_create_assistant(cfg["model"], cfg.get("kpi_targets", {}))
    thread = openai.beta.threads.create()
    with open(snapshot_path, "rb") as f:
        file_id = openai.files.create(purpose="assistants", file=f).id
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="Analyse and propose next patch.",
            attachments=[{
                "file_id": file_id,
                "tools": [{"type": "propose_patch"}],
            }],
        )
    run = openai.beta.threads.runs.create(
        assistant_id=assistant_id,
        thread_id=thread.id,
    )
    while True:
        run = openai.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status in ("completed", "failed", "cancelled"):
            break
        time.sleep(1)
    if run.status != "completed":
        return None
    tool_call = run.required_action["submit_tool_outputs"]["tool_calls"][0]
    return json.loads(tool_call["function"]["arguments"])


def apply_patch(state: WorldState, cfg: Dict[str, Any], patch: Dict[str, Any]) -> None:
    limits = cfg.get("optimizer", {}).get("patch_limits", {})
    for act in patch.get("actions", []):
        t = act.get("type")
        if t not in ALLOWED_ACTIONS:
            continue
        if t == "add_workers":
            delta = int(act.get("delta", 0))
            if abs(delta) > limits.get("max_workers_delta", 0):
                continue
            if delta > 0:
                for _ in range(delta):
                    wid = f"W{len(state.workers) + 1}"
                    state.workers[wid] = Worker(id=wid, role="picker")
            elif delta < 0:
                for wid in list(state.workers.keys())[: abs(delta)]:
                    state.workers.pop(wid, None)
        elif t == "set_zone_priority":
            zid = act.get("zone_id")
            pr = int(act.get("priority", 0))
            if zid in state.zones:
                state.zones[zid].priority = pr
        elif t == "tune_speed":
            pct = int(act.get("percent", 0))
            if abs(pct) > limits.get("tune_speed_pct", 100):
                continue
            for w in state.workers.values():
                w.speed_factor *= 1 + pct / 100


def log_opt_event(state: WorldState, before_snap: Dict[str, Any], patch: Dict[str, Any]) -> None:
    csv_path = pathlib.Path("reports/optimizer/opt_events.csv")
    md_path = pathlib.Path("reports/optimizer") / f"{datetime.date.today().isoformat()}.md"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    after_snap = rollup(state, 1)

    write_header = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                "sim_time",
                "cycle_before",
                "cycle_after",
                "queue_before",
                "queue_after",
                "otif_before",
                "otif_after",
                "actions",
            ])
        writer.writerow([
            state.sim_time,
            before_snap.get("mean_cycle_s", 0),
            after_snap.get("mean_cycle_s", 0),
            before_snap.get("dock_queue", 0),
            after_snap.get("dock_queue", 0),
            before_snap.get("otif", 0),
            after_snap.get("otif", 0),
            json.dumps(patch.get("actions", [])),
        ])

    with md_path.open("a", encoding="utf-8") as m:
        m.write(
            f"### {state.sim_time//3600:02d}:{(state.sim_time%3600)//60:02d}\n"
        )
        m.write(
            f"*Before* – cycle {before_snap['mean_cycle_s']} s, "
            f"OTIF {before_snap['otif']:.2f}, queue {before_snap['dock_queue']}\n"
        )
        m.write(f"*Patch* – `{json.dumps(patch.get('actions', []))}`\n")
        m.write(
            f"*After* – cycle {after_snap['mean_cycle_s']} s, "
            f"OTIF {after_snap['otif']:.2f}, queue {after_snap['dock_queue']}\n\n"
        )


def process(state: WorldState, cfg: Dict[str, Any]) -> None:
    opt_cfg = cfg.get("optimizer")
    if not opt_cfg:
        return
    period_sec = int(opt_cfg.get("period_min", 60) * 60)
    if state.sim_time == 0 or state.sim_time % period_sec != 0:
        return

    snap = rollup(state, period_sec)
    snap_path = pathlib.Path("reports/optimizer") / f"snapshot_{state.sim_time}.json"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    with snap_path.open("w", encoding="utf-8") as f:
        json.dump(snap, f)

    patch = call_optimizer(str(snap_path), opt_cfg)
    if patch:
        apply_patch(state, cfg, patch)
        log_opt_event(state, snap, patch)