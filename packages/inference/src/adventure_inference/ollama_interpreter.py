"""Ollama-backed Mission Interpreter — outputs MissionIntent JSON, never rankings."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from adventure_core.intent import (
    PREFERENCE_DIMENSIONS,
    SCHEMA_VERSION,
    HardConstraints,
    MissionIntent,
    PreferenceVector,
)

DEFAULT_MODEL = "llama3.2"
FALLBACK_MODELS = ("llama3.2", "llama3.1:8b", "qwen3:8b", "llama3.2:3b")

SYSTEM_PROMPT = f"""You are the Mission Interpreter for Adventure AI, a local exploration system.
Convert the user prompt into JSON matching schema_version "{SCHEMA_VERSION}".

Rules:
- Output ONLY valid JSON. No markdown. No commentary.
- You translate language into a structured mission intent.
- You do NOT choose places, coordinates, or rankings.
- preferences values are floats in [-1, 1]. 0 means unspecified.
- Negative preference means avoid that dimension (e.g. human_activity=-0.9 for hate crowds).
- danger negative means avoid hazardous roads/terrain; positive means seek challenge.
- constraints are hard logistics (vehicle, days, budget, origin city, departure/return).
- goals are from: discovery, photography, camping, hiking, history, wildlife, relaxation, surprise.

Preference dimensions (use only these keys):
{", ".join(PREFERENCE_DIMENSIONS)}

JSON shape:
{{
  "schema_version": "{SCHEMA_VERSION}",
  "constraints": {{
    "days": number|null,
    "vehicle": string|null,
    "vehicle_class": "hatchback"|"sedan"|"suv"|"suv_4x4"|null,
    "party_size": number|null,
    "budget_per_person": number|null,
    "currency": string|null,
    "origin": string|null,
    "departure": string|null,
    "return_by": string|null
  }},
  "preferences": {{ "<dimension>": number }},
  "goals": ["discovery"]
}}
"""


def ollama_available(base_url: str = "http://127.0.0.1:11434", timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _post_chat(model: str, prompt: str, base_url: str, timeout: float) -> str:
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.1},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return str(payload.get("message", {}).get("content", ""))


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in model output")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be object")
    return data


def _list_models(base_url: str) -> set[str]:
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=2.0) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return {m.get("name", "") for m in payload.get("models", [])}
    except Exception:
        return set()


def _pick_model(preferred: str, base_url: str) -> str:
    available = _list_models(base_url)
    if not available:
        return preferred
    if preferred in available or any(preferred in a for a in available):
        return preferred
    for cand in FALLBACK_MODELS:
        if cand in available or any(cand.split(":")[0] in a for a in available):
            return next(a for a in available if cand.split(":")[0] in a)
    raise RuntimeError(
        f"Ollama model {preferred!r} not installed; tried fallbacks {FALLBACK_MODELS}. "
        f"Available: {sorted(available)}"
    )


def interpret_ollama(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 120.0,
) -> MissionIntent:
    chosen = _pick_model(model, base_url)
    raw = _post_chat(chosen, prompt, base_url, timeout)
    data = _extract_json(raw)

    constraints_raw = data.get("constraints") or {}
    prefs_raw = data.get("preferences") or {}
    goals = [str(g) for g in (data.get("goals") or [])]

    # Fill origin coords from gazetteer if city name present
    from adventure_core.constraints import CITY_COORDS

    origin = constraints_raw.get("origin")
    origin_lon = constraints_raw.get("origin_lon")
    origin_lat = constraints_raw.get("origin_lat")
    if origin and (origin_lon is None or origin_lat is None):
        key = str(origin).strip().lower()
        if key in CITY_COORDS:
            origin_lon, origin_lat = CITY_COORDS[key]

    constraints = HardConstraints(
        days=constraints_raw.get("days"),
        vehicle=constraints_raw.get("vehicle"),
        vehicle_class=constraints_raw.get("vehicle_class"),
        party_size=constraints_raw.get("party_size"),
        budget_per_person=constraints_raw.get("budget_per_person"),
        currency=constraints_raw.get("currency"),
        origin=origin,
        origin_lon=origin_lon,
        origin_lat=origin_lat,
        departure=constraints_raw.get("departure"),
        return_by=constraints_raw.get("return_by"),
    )

    pref_kwargs = {d: float(prefs_raw.get(d, 0.0) or 0.0) for d in PREFERENCE_DIMENSIONS}
    preferences = PreferenceVector(**pref_kwargs)

    return MissionIntent(
        schema_version=str(data.get("schema_version") or SCHEMA_VERSION),
        constraints=constraints,
        preferences=preferences,
        goals=goals,
        source="llm",
        interpreter_notes=[f"ollama_model={chosen}"],
        raw_prompt=prompt,
    )
