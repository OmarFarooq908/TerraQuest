"""MissionIntent validation / repair (issue #11)."""

from __future__ import annotations

import pytest
from adventure_core.intent import HardConstraints, MissionIntent, PreferenceVector
from adventure_core.intent_validate import (
    IntentValidationError,
    preferences_from_raw,
    sanitize_intent_dict,
    validate_and_repair_intent,
)
from adventure_inference.router import interpret_mission


def test_clip_out_of_range_preferences():
    prefs, repairs = preferences_from_raw({"water": 2.5, "forest": -3, "bogus": 1})
    assert prefs.water == 1.0
    assert prefs.forest == -1.0
    assert any("clip_preference:water" in r for r in repairs)
    assert any("drop_unknown_preference:bogus" in r for r in repairs)


def test_sanitize_drops_unknown_goals_and_normalizes_schema():
    data, repairs = sanitize_intent_dict(
        {
            "schema_version": "0.9",
            "preferences": {"water": 0.5},
            "goals": ["discovery", "teleportation"],
            "constraints": {},
        }
    )
    assert data["schema_version"] == "1.0"
    assert data["goals"] == ["discovery"]
    assert any("drop_unknown_goal:teleportation" in r for r in repairs)


def test_reject_non_positive_days():
    intent = MissionIntent(constraints=HardConstraints(days=0))
    with pytest.raises(IntentValidationError, match="days"):
        validate_and_repair_intent(intent)


def test_clear_unknown_vehicle_class():
    intent = MissionIntent(constraints=HardConstraints(vehicle_class="spaceship"))
    fixed = validate_and_repair_intent(intent)
    assert fixed.constraints.vehicle_class is None
    assert any("clear_unknown_vehicle_class" in r for r in fixed.intent_repairs)


def test_resolve_solitude_human_activity_contradiction():
    intent = MissionIntent(
        preferences=PreferenceVector(solitude=0.8, human_activity=0.7),
        source="llm",
    )
    fixed = validate_and_repair_intent(intent)
    assert fixed.preferences.solitude == 0.8
    assert fixed.preferences.human_activity < 0
    assert fixed.intent_repairs


def test_rules_path_still_works_with_validation():
    intent = interpret_mission(
        "love rivers and forests, hate crowds, don't want dangerous roads",
        interpreter="rules",
    )
    assert intent.preferences.water > 0.3
    assert intent.preferences.human_activity < -0.3
    assert intent.raw_prompt


def test_router_validate_then_polarity(monkeypatch: pytest.MonkeyPatch):
    bad = MissionIntent(
        preferences=PreferenceVector(human_activity=0.9, solitude=0.8),
        constraints=HardConstraints(vehicle_class="SEDAN"),
        source="llm",
    )
    import adventure_inference.router as router

    monkeypatch.setattr(router, "ollama_available", lambda *a, **k: True)
    monkeypatch.setattr(router, "interpret_ollama", lambda *a, **k: bad)

    intent = interpret_mission("I hate crowds", interpreter="ollama")
    assert intent.constraints.vehicle_class == "sedan"
    assert intent.preferences.human_activity < 0
    assert intent.intent_repairs or any("polarity_repair" in n for n in intent.interpreter_notes)
