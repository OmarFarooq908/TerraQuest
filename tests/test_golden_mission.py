"""Mission intent + preference-vector scoring tests (offline rules interpreter)."""

from __future__ import annotations

from adventure_cli.pipeline import run_mission
from adventure_core.constraints import parse_constraints
from adventure_core.intent import PreferenceVector
from adventure_core.interpreters import interpret_rules
from adventure_scoring.scorer import preference_alignment

PROMPT = (
    "I have three days, a Suzuki Swift, four friends, and PKR 20,000 each. "
    "Find somewhere that feels like a Fearless & Far adventure."
)

PROMPT_LAHORE = (
    "I'm in Lahore. My friends and I can leave after work on Friday and need "
    "to be back by Sunday night. We have a Honda City, don't want dangerous roads, "
    "love rivers and forests, hate crowds, and can spend around PKR 15,000 each. "
    "Surprise us."
)


def test_parse_constraints_fearless_far_prompt():
    c = parse_constraints(PROMPT)
    assert c.days == 3.0
    assert c.vehicle == "suzuki swift"
    assert c.party_size == 5


def test_rules_interpreter_emits_preference_vector():
    intent = interpret_rules(PROMPT_LAHORE)
    assert intent.schema_version == "1.0"
    assert intent.constraints.origin == "Lahore"
    assert intent.constraints.vehicle == "honda city"
    assert intent.preferences.water > 0.5
    assert intent.preferences.forest > 0.5
    assert intent.preferences.human_activity < -0.3
    assert intent.preferences.danger < -0.3


def test_preference_alignment_prefers_matching_dimensions():
    want_forest_river = PreferenceVector(water=0.9, forest=0.9, human_activity=-0.8)
    high = {
        "water": 0.95,
        "forest": 0.9,
        "human_activity": 0.05,
        **{
            d: 0.3
            for d in PreferenceVector.model_fields
            if d not in {"water", "forest", "human_activity"}
        },
    }
    low = {
        "water": 0.1,
        "forest": 0.05,
        "human_activity": 0.8,
        **{
            d: 0.3
            for d in PreferenceVector.model_fields
            if d not in {"water", "forest", "human_activity"}
        },
    }
    f_high, _ = preference_alignment(want_forest_river, high)
    f_low, _ = preference_alignment(want_forest_river, low)
    assert f_high > f_low


def test_golden_mission_returns_at_least_three_with_confidence():
    result = run_mission(
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        prompt=PROMPT,
        max_results=5,
        interpreter="rules",
    )
    assert len(result.missions) >= 3
    assert result.request.intent.source == "rules"
    for mission in result.missions:
        assert mission.score > 0
        assert mission.evidence.get("dimensions")


def test_control_near_town_not_top_under_fearless_far():
    result = run_mission(
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        prompt=PROMPT,
        max_results=3,
        interpreter="rules",
    )
    assert "seed_near_town_hill" not in [m.candidate_id for m in result.missions]


def test_explorer_mode_runs():
    result = run_mission(
        pack="karakoram_mini",
        mode="explorer",
        prompt="Find a remote valley",
        max_results=3,
        interpreter="rules",
    )
    assert len(result.missions) >= 3


def test_rich_prompt_changes_ranking_toward_river_forest():
    baseline = run_mission(
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        prompt=PROMPT,
        max_results=5,
        interpreter="rules",
    )
    rich = run_mission(
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        prompt=PROMPT_LAHORE,
        max_results=5,
        interpreter="rules",
    )
    assert [m.candidate_id for m in baseline.missions] != [m.candidate_id for m in rich.missions]
    assert rich.missions[0].candidate_id in {
        "seed_pine_river",
        "seed_river_ford",
        "seed_silent_valley",
    }
    pref_field = next(f for f in rich.coverage.fields if f.field == "preference_vector")
    assert pref_field.scoring == "used"
    assert "seed_sunrise_ridge" not in [m.candidate_id for m in rich.missions[:2]]


def test_candidate_dimensions_stable_keys():
    result = run_mission(
        pack="fixtures/karakoram_mini",
        mode="fearless_far",
        prompt=PROMPT,
        max_results=1,
        interpreter="rules",
    )
    dims = result.missions[0].evidence["dimensions"]
    assert set(dims) >= {"water", "forest", "solitude", "human_activity"}
