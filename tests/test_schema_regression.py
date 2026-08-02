"""Schema regression pins for MissionIntent + catalog (#66).

Pinned JSON Schemas under ``schemas/`` must stay aligned with Pydantic models.
Intentional schema bumps update both the pin and the version constants.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    HardConstraints,
    MissionIntent,
    PreferenceVector,
)

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
    required = set(schema["required"])
    assert required <= set(MissionIntent.model_fields)
    assert {"schema_version", "constraints", "preferences", "goals", "source"} <= required


def test_preference_dimensions_match_pin_and_model() -> None:
    schema = _load(MISSION_SCHEMA)
    pinned = schema["$defs"]["PreferenceVector"]["required"]
    assert tuple(pinned) == PREFERENCE_DIMENSIONS
    assert set(pinned) == set(PreferenceVector.model_fields)
    # Live model must not silently gain/lose dims without updating the pin.
    assert len(PREFERENCE_DIMENSIONS) == 15


def test_hard_constraints_fields_match_pin() -> None:
    schema = _load(MISSION_SCHEMA)
    pinned = set(schema["$defs"]["HardConstraints"]["properties"])
    assert pinned == set(HardConstraints.model_fields)


def test_mission_intent_optional_meta_fields_documented() -> None:
    schema = _load(MISSION_SCHEMA)
    props = set(schema["properties"])
    assert {"interpreter_notes", "intent_repairs", "raw_prompt"} <= props
    assert props == set(MissionIntent.model_fields)


def test_catalog_schema_version_and_required_props() -> None:
    schema = _load(CATALOG_SCHEMA)
    assert schema["properties"]["catalog_schema_version"]["const"] == CATALOG_SCHEMA_VERSION
    assert CATALOG_SCHEMA_VERSION == "0.3.0"
    required = set(schema["required"])
    assert required == {"id", "name", "generator", "provenance", "evidence", "densify"}
    # Required keys are a subset of CatalogCandidate (lon/lat live on geometry).
    model_props = set(CatalogCandidate.model_fields) - {"lon", "lat"}
    assert required <= model_props | {"id", "name"}  # id/name are on candidate too
    assert {"id", "name", "generator", "provenance", "evidence", "densify"} <= set(
        CatalogCandidate.model_fields
    )


def test_provenance_and_densify_pins_match_models() -> None:
    schema = _load(CATALOG_SCHEMA)
    assert set(schema["$defs"]["Provenance"]["properties"]) == set(Provenance.model_fields)
    assert set(schema["$defs"]["Provenance"]["required"]) == {"sources", "method"}
    assert set(schema["$defs"]["DensifyHook"]["properties"]) == set(DensifyHook.model_fields)
    assert set(schema["$defs"]["DensifyHook"]["required"]) == {"cell_id"}


def test_catalog_feature_pin_covers_candidate_property_keys() -> None:
    """Pin property bag should include every CatalogCandidate field except lon/lat."""
    schema = _load(CATALOG_SCHEMA)
    pinned = set(schema["properties"])
    model = set(CatalogCandidate.model_fields) - {"lon", "lat"}
    missing = model - pinned
    assert not missing, f"catalog pin missing fields: {sorted(missing)}"


def test_fixture_catalog_features_satisfy_required_pin_keys() -> None:
    root = repo_root() / "fixtures" / "karakoram_mini" / "layers" / "catalog.geojson"
    fc = json.loads(root.read_text(encoding="utf-8"))
    required = set(_load(CATALOG_SCHEMA)["required"])
    for feat in fc["features"]:
        props = feat["properties"]
        assert required <= set(props), props.get("id")


@pytest.mark.parametrize(
    "dim",
    list(PREFERENCE_DIMENSIONS),
)
def test_each_preference_dimension_in_schema_properties(dim: str) -> None:
    schema = _load(MISSION_SCHEMA)
    assert dim in schema["$defs"]["PreferenceVector"]["properties"]
