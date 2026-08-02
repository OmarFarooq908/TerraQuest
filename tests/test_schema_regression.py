"""Schema regression pins for MissionIntent + catalog (#66).

Pinned JSON Schemas under ``schemas/`` must stay aligned with Pydantic models.
Intentional schema bumps update both the pin and the version constants.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from adventure_core.catalog import (
    CATALOG_SCHEMA_VERSION,
    CatalogCandidate,
    DensifyHook,
    Provenance,
)
from adventure_core.config import repo_root
from adventure_core.intent import (
    PREFERENCE_DIMENSIONS,
    SCHEMA_VERSION,
    GoalId,
    HardConstraints,
    MissionIntent,
    PreferenceVector,
)
from adventure_core.intent_validate import KNOWN_GOALS, KNOWN_VEHICLE_CLASSES

SCHEMAS = repo_root() / "schemas"
MISSION_SCHEMA = SCHEMAS / "mission_intent.schema.json"
CATALOG_SCHEMA = SCHEMAS / "catalog_feature.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_pin_files_exist() -> None:
    assert MISSION_SCHEMA.is_file()
    assert CATALOG_SCHEMA.is_file()


def test_mission_intent_schema_version_pin() -> None:
    schema = _load(MISSION_SCHEMA)
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION == "1.0"
    assert schema.get("additionalProperties") is False
    required = set(schema["required"])
    assert required == {"schema_version", "constraints", "preferences", "goals", "source"}
    assert required <= set(MissionIntent.model_fields)


def test_preference_dimensions_match_pin_and_model() -> None:
    schema = _load(MISSION_SCHEMA)
    pinned = schema["$defs"]["PreferenceVector"]["required"]
    assert tuple(pinned) == PREFERENCE_DIMENSIONS
    assert set(pinned) == set(PreferenceVector.model_fields)
    assert set(pinned) == set(schema["$defs"]["PreferenceVector"]["properties"])
    # Live model must not silently gain/lose dims without updating the pin.
    assert len(PREFERENCE_DIMENSIONS) == 15


def test_hard_constraints_fields_match_pin() -> None:
    schema = _load(MISSION_SCHEMA)
    pinned = set(schema["$defs"]["HardConstraints"]["properties"])
    assert pinned == set(HardConstraints.model_fields)


def test_known_goals_and_vehicle_classes_match_pins() -> None:
    schema = _load(MISSION_SCHEMA)
    goal_enum = schema["properties"]["goals"]["items"]["enum"]
    assert set(goal_enum) == KNOWN_GOALS == frozenset(get_args(GoalId))
    assert tuple(goal_enum) == get_args(GoalId)

    vc = schema["$defs"]["HardConstraints"]["properties"]["vehicle_class"]
    # anyOf: null | enum
    enums = [branch["enum"] for branch in vc["anyOf"] if "enum" in branch]
    assert len(enums) == 1
    assert set(enums[0]) == KNOWN_VEHICLE_CLASSES


def test_mission_intent_optional_meta_fields_documented() -> None:
    schema = _load(MISSION_SCHEMA)
    props = set(schema["properties"])
    assert {"interpreter_notes", "intent_repairs", "raw_prompt"} <= props
    assert props == set(MissionIntent.model_fields)


def test_catalog_schema_version_and_required_props() -> None:
    schema = _load(CATALOG_SCHEMA)
    assert schema.get("additionalProperties") is False
    assert schema["properties"]["catalog_schema_version"]["const"] == CATALOG_SCHEMA_VERSION
    assert CATALOG_SCHEMA_VERSION == "0.3.0"
    required = set(schema["required"])
    assert required == {
        "id",
        "name",
        "generator",
        "provenance",
        "evidence",
        "densify",
        "catalog_schema_version",
    }
    assert required <= set(CatalogCandidate.model_fields)


def test_provenance_and_densify_pins_match_models() -> None:
    schema = _load(CATALOG_SCHEMA)
    assert set(schema["$defs"]["Provenance"]["properties"]) == set(Provenance.model_fields)
    assert set(schema["$defs"]["Provenance"]["required"]) == {"sources", "method"}
    assert schema["$defs"]["Provenance"].get("additionalProperties") is False
    assert set(schema["$defs"]["DensifyHook"]["properties"]) == set(DensifyHook.model_fields)
    assert set(schema["$defs"]["DensifyHook"]["required"]) == {"cell_id"}
    assert schema["$defs"]["DensifyHook"].get("additionalProperties") is False


def test_catalog_feature_pin_matches_candidate_property_keys() -> None:
    """Pin property bag ↔ CatalogCandidate fields (except lon/lat on geometry)."""
    schema = _load(CATALOG_SCHEMA)
    pinned = set(schema["properties"])
    model = set(CatalogCandidate.model_fields) - {"lon", "lat"}
    assert pinned == model, (
        f"pin≠model extra={sorted(pinned - model)} missing={sorted(model - pinned)}"
    )


def test_fixture_catalog_features_satisfy_required_pin_keys() -> None:
    root = repo_root() / "fixtures" / "karakoram_mini" / "layers" / "catalog.geojson"
    fc = json.loads(root.read_text(encoding="utf-8"))
    required = set(_load(CATALOG_SCHEMA)["required"])
    for feat in fc["features"]:
        props = feat["properties"]
        assert required <= set(props), props.get("id")


def test_default_mission_intent_dump_covers_required_pin() -> None:
    """Post-default MissionIntent JSON includes every pinned required key + pref dim."""
    schema = _load(MISSION_SCHEMA)
    dumped = json.loads(MissionIntent().model_dump_json())
    assert set(schema["required"]) <= set(dumped)
    assert set(PREFERENCE_DIMENSIONS) <= set(dumped["preferences"])


@pytest.mark.parametrize(
    "dim",
    list(PREFERENCE_DIMENSIONS),
)
def test_each_preference_dimension_in_schema_properties(dim: str) -> None:
    schema = _load(MISSION_SCHEMA)
    assert dim in schema["$defs"]["PreferenceVector"]["properties"]
