import json
from typing import Any, Dict, Optional

try:
    import openai  # type: ignore
except Exception:  # noqa: BLE001
    openai = None

from .schema import ALLOWED_PATCH  # ← новый импорт

SYSTEM_PROMPT = "You are a warehouse optimizer."

# ---- динамические правила, основанные на whitelist ----
_ALLOWED_KEYS_STR = ", ".join(sorted(ALLOWED_PATCH))
EXTRA_RULES = (
    f"ALLOWED_ACTIONS: You may update ONLY these keys "
    f"({_ALLOWED_KEYS_STR}). "
    'Respond ONLY with JSON object {"<key>": <number>, ...}.'
)

# -------------------------------------------------------


def _clamp(value, spec):
    """Приводим к нужному типу и зажимаем в min‑max диапазон."""
    v = spec["type"](value)
    return max(spec["min"], min(spec["max"], v))


def propose_patch(
    state_summary: Dict[str, Any],
    kpi_targets: Dict[str, Any],
    last_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """Запрашиваем у LLM патч и фильтруем по ALLOWED_PATCH."""
    if openai is None:
        return {}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"KPI_TARGETS: {json.dumps(kpi_targets)}"},
    ]
    if last_summary:
        messages.append(
            {"role": "system", "content": f"PREVIOUS_SUMMARY: {last_summary}"}
        )
    else:
        messages.append({"role": "system", "content": "PREVIOUS_SUMMARY: None"})

    messages.append(
        {
            "role": "user",
            "content": f"CURRENT_METRICS: {json.dumps(state_summary)}\n" + EXTRA_RULES,
        }
    )

    try:
        resp = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.3,
        )
        content = resp.choices[0].message.content.strip()
        raw_patch = json.loads(content)
    except Exception as e:  # noqa: BLE001
        print(f"Optimizer error: {e}")
        return {}

    cleaned: Dict[str, Any] = {}
    for path, val in (raw_patch or {}).items():
        if path not in ALLOWED_PATCH:
            print(f"Skip unknown key from LLM: {path}")
            continue
        spec = ALLOWED_PATCH[path]
        try:
            cleaned[path] = _clamp(val, spec)
        except Exception:
            print(f"Value type mismatch for {path}")
            continue
    print("RAW PATCH FROM LLM:", raw_patch)
    return cleaned
