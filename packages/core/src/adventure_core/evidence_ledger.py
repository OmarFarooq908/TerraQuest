"""Evidence ledger v1 — required catalog evidence/provenance per generator (#19).

This is a *field completeness* contract for science/trust, not empirical
calibration and not content-addressed layer bytes / required ``osm_id`` (v2).
"""

from __future__ import annotations

from typing import Any, get_args

from adventure_core.catalog import GeneratorName

EVIDENCE_LEDGER_VERSION = "1"

# Required evidence keys present (non-null / non-blank where strings) per generator.
REQUIRED_EVIDENCE_KEYS: dict[str, frozenset[str]] = {
    "track_terminus": frozenset({"discovery_score", "dist_settlement_km", "endpoint"}),
    "road_spur": frozenset({"discovery_score", "dist_settlement_km", "far_endpoint"}),
    "named_waterbody": frozenset({"discovery_score", "dist_settlement_km", "water_kind", "named"}),
    "unnamed_waterbody": frozenset(
        {"discovery_score", "dist_settlement_km", "water_kind", "named"}
    ),
    "osm_peak": frozenset({"discovery_score", "dist_settlement_km"}),
    "osm_viewpoint": frozenset({"discovery_score", "dist_settlement_km"}),
    "isolation_maximum": frozenset({"discovery_score", "dist_settlement_km", "grid_res_deg"}),
    "dem_local_max": frozenset({"discovery_score", "dist_settlement_km", "elevation_m"}),
    "terrain_relief_hotspot": frozenset({"discovery_score", "dist_settlement_km", "relief_m"}),
    "synthetic_fixture": frozenset({"discovery_score", "fixture"}),
}

# String evidence keys that must be non-empty when present/required.
_NONEMPTY_STRING_KEYS = frozenset({"endpoint", "far_endpoint", "water_kind"})

OSM_SOURCE_GENERATORS = frozenset(
    {
        "track_terminus",
        "road_spur",
        "named_waterbody",
        "unnamed_waterbody",
        "osm_peak",
        "osm_viewpoint",
        "isolation_maximum",
    }
)
DEM_SOURCE_GENERATORS = frozenset({"dem_local_max", "terrain_relief_hotspot"})


def shipping_generator_names() -> frozenset[str]:
    """Generator names that packbuilder ships (excludes schema-only aliases)."""
    return frozenset(get_args(GeneratorName)) - {"synthetic_fixture"}


def _missing_keys(evidence: dict[str, Any], required: frozenset[str]) -> list[str]:
    missing: list[str] = []
    for key in sorted(required):
        if key not in evidence or evidence[key] is None:
            missing.append(key)
            continue
        if (
            key in _NONEMPTY_STRING_KEYS
            and isinstance(evidence[key], str)
            and not evidence[key].strip()
        ):
            missing.append(key)
    return missing


def validate_evidence_ledger(
    *,
    generator: str,
    provenance: dict[str, Any],
    evidence: dict[str, Any],
    feature_id: str = "feature",
) -> list[str]:
    """Return human-readable errors for incomplete evidence/provenance."""
    errors: list[str] = []
    gen = generator.strip() if isinstance(generator, str) else ""
    if not gen:
        return [f"{feature_id}: generator must be a non-empty string"]

    required = REQUIRED_EVIDENCE_KEYS.get(gen)
    if required is None:
        errors.append(f"{feature_id}: unknown generator {gen!r} for evidence ledger")
        return errors

    for key in _missing_keys(evidence, required):
        errors.append(f"{feature_id}: evidence missing required key {key!r} for {gen}")

    sources = provenance.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{feature_id}: provenance.sources must be a non-empty list")
        sources_list: list[Any] = []
    else:
        sources_list = sources

    synthetic = "synthetic" in sources_list
    if (synthetic or gen == "synthetic_fixture") and evidence.get("fixture") is not True:
        errors.append(
            f"{feature_id}: synthetic / synthetic_fixture requires evidence.fixture=true "
            "(keep fixtures honestly marked)"
        )

    if gen in OSM_SOURCE_GENERATORS and not synthetic and "osm" not in sources_list:
        errors.append(f"{feature_id}: provenance.sources must include 'osm' for {gen}")
    if gen in DEM_SOURCE_GENERATORS and not synthetic and "dem" not in sources_list:
        errors.append(f"{feature_id}: provenance.sources must include 'dem' for {gen}")

    if gen in DEM_SOURCE_GENERATORS and not synthetic and not provenance.get("dem_tile"):
        errors.append(f"{feature_id}: provenance.dem_tile required for {gen}")

    if not synthetic and gen != "synthetic_fixture" and not provenance.get("layer"):
        # DEM generators may omit layer when dem_tile is set
        if gen not in DEM_SOURCE_GENERATORS:
            errors.append(f"{feature_id}: provenance.layer required for {gen}")

    return errors
