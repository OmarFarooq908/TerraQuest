"""Semantic MissionIntent validation and safe repair (issue #11)."""

from __future__ import annotations

from typing import Any

from adventure_core.intent import (
    PREFERENCE_DIMENSIONS,
    SCHEMA_VERSION,
    MissionIntent,
    PreferenceVector,
)

KNOWN_VEHICLE_CLASSES = frozenset({"hatchback", "sedan", "suv", "suv_4x4"})
KNOWN_GOALS = frozenset(
    {
        "discovery",
        "photography",
        "camping",
        "hiking",
        "history",
        "wildlife",
        "relaxation",
        "surprise",
    }
)

# Strong contradiction threshold on both axes
_CONTRADICTION_ABS = 0.45


class IntentValidationError(ValueError):
    """Intent cannot be safely repaired — fail closed."""


def _clip_pref(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise IntentValidationError(f"non-numeric preference value: {value!r}") from exc
    if x != x:  # NaN
        raise IntentValidationError("NaN preference value")
    return max(-1.0, min(1.0, x))


def preferences_from_raw(raw: dict[str, Any] | None) -> tuple[PreferenceVector, list[str]]:
    """Build PreferenceVector from loose LLM JSON; drop unknown keys; clip values."""
    repairs: list[str] = []
    raw = raw or {}
    if not isinstance(raw, dict):
        raise IntentValidationError("preferences must be an object")

    kwargs: dict[str, float] = {}
    for key, value in raw.items():
        if key not in PREFERENCE_DIMENSIONS:
            repairs.append(f"drop_unknown_preference:{key}")
            continue
        try:
            original = float(value)
        except (TypeError, ValueError) as exc:
            raise IntentValidationError(f"non-numeric preference value: {value!r}") from exc
        clipped = _clip_pref(original)
        if abs(original - clipped) > 1e-9:
            repairs.append(f"clip_preference:{key}:{original}->{clipped}")
        kwargs[key] = clipped

    return PreferenceVector(**kwargs), repairs


def sanitize_intent_dict(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalize raw interpreter JSON before MissionIntent construction."""
    if not isinstance(data, dict):
        raise IntentValidationError("intent root must be an object")

    repairs: list[str] = []
    out = dict(data)

    schema = str(out.get("schema_version") or SCHEMA_VERSION)
    if schema != SCHEMA_VERSION:
        repairs.append(f"normalize_schema_version:{schema}->{SCHEMA_VERSION}")
        out["schema_version"] = SCHEMA_VERSION

    prefs, pref_repairs = preferences_from_raw(out.get("preferences") or {})
    repairs.extend(pref_repairs)
    out["preferences"] = prefs.as_dict()

    goals_raw = out.get("goals") or []
    if not isinstance(goals_raw, list):
        raise IntentValidationError("goals must be a list")
    goals: list[str] = []
    for g in goals_raw:
        gs = str(g)
        if gs in KNOWN_GOALS:
            goals.append(gs)
        else:
            repairs.append(f"drop_unknown_goal:{gs}")
    out["goals"] = goals

    constraints = out.get("constraints") or {}
    if constraints is None:
        constraints = {}
    if not isinstance(constraints, dict):
        raise IntentValidationError("constraints must be an object")
    out["constraints"] = dict(constraints)

    return out, repairs


def validate_and_repair_intent(intent: MissionIntent) -> MissionIntent:
    """Apply semantic repairs; raise IntentValidationError if unrecoverable."""
    repairs = list(intent.intent_repairs)
    notes = list(intent.interpreter_notes)
    constraints = intent.constraints.model_copy()
    prefs = intent.preferences.model_copy()
    goals = list(intent.goals)

    # --- constraints ---
    if constraints.days is not None:
        if constraints.days <= 0:
            raise IntentValidationError(f"days must be > 0 when set (got {constraints.days})")
        if constraints.days > 60:
            repairs.append(f"clip_days:{constraints.days}->60")
            constraints.days = 60.0

    if constraints.party_size is not None and constraints.party_size <= 0:
        repairs.append(f"clear_invalid_party_size:{constraints.party_size}")
        constraints.party_size = None

    if constraints.budget_per_person is not None and constraints.budget_per_person < 0:
        raise IntentValidationError("budget_per_person cannot be negative")

    if constraints.vehicle_class is not None:
        vc = str(constraints.vehicle_class).strip().lower()
        if vc not in KNOWN_VEHICLE_CLASSES:
            repairs.append(f"clear_unknown_vehicle_class:{constraints.vehicle_class}")
            constraints.vehicle_class = None
        else:
            constraints.vehicle_class = vc

    if constraints.origin_lon is not None and not (-180.0 <= constraints.origin_lon <= 180.0):
        raise IntentValidationError("origin_lon out of range")
    if constraints.origin_lat is not None and not (-90.0 <= constraints.origin_lat <= 90.0):
        raise IntentValidationError("origin_lat out of range")

    # --- goals ---
    cleaned_goals: list[str] = []
    for g in goals:
        if g in KNOWN_GOALS:
            cleaned_goals.append(g)
        else:
            repairs.append(f"drop_unknown_goal:{g}")
    goals = cleaned_goals

    # --- preference contradictions ---
    solitude = float(prefs.solitude)
    human = float(prefs.human_activity)
    if solitude >= _CONTRADICTION_ABS and human >= _CONTRADICTION_ABS:
        # Prefer solitude when both claim strong positives (crowd-averse default)
        repairs.append(
            f"resolve_contradiction:solitude={solitude:+.2f},human_activity={human:+.2f}"
            f"->human_activity={-abs(human):+.2f}"
        )
        prefs.human_activity = -abs(human)

    # Schema version
    schema = intent.schema_version
    if schema != SCHEMA_VERSION:
        repairs.append(f"normalize_schema_version:{schema}->{SCHEMA_VERSION}")
        schema = SCHEMA_VERSION

    if repairs:
        notes = notes + [f"intent_repair:{r}" for r in repairs]

    return intent.model_copy(
        update={
            "schema_version": schema,
            "constraints": constraints,
            "preferences": prefs,
            "goals": goals,
            "interpreter_notes": notes,
            "intent_repairs": repairs,
        }
    )
