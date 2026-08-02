"""Evidence ledger v1 — required catalog evidence/provenance per generator (#19).

This is a *field completeness* contract for science/trust, not empirical
calibration and not content-addressed layer bytes (those are follow-ups).
"""

from __future__ import annotations

from typing import Any

EVIDENCE_LEDGER_VERSION = "1"

# Required evidence keys present (non-null) for each shipping generator.
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


def _missing_keys(evidence: dict[str, Any], required: frozenset[str]) -> list[str]:
    missing: list[str] = []
    for key in sorted(required):
        if key not in evidence or evidence[key] is None:
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
    required = REQUIRED_EVIDENCE_KEYS.get(generator)
    if required is None:
        errors.append(f"{feature_id}: unknown generator {generator!r} for evidence ledger")
        return errors

    for key in _missing_keys(evidence, required):
        errors.append(f"{feature_id}: evidence missing required key {key!r} for {generator}")

    sources = provenance.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{feature_id}: provenance.sources must be a non-empty list")
        sources_list: list[Any] = []
    else:
        sources_list = sources

    synthetic = "synthetic" in sources_list
    if synthetic and evidence.get("fixture") is not True:
        errors.append(
            f"{feature_id}: synthetic provenance requires evidence.fixture=true "
            "(keep fixtures honestly marked)"
        )

    if generator in OSM_SOURCE_GENERATORS and not synthetic and "osm" not in sources_list:
        errors.append(f"{feature_id}: provenance.sources must include 'osm' for {generator}")
    if generator in DEM_SOURCE_GENERATORS and not synthetic and "dem" not in sources_list:
        errors.append(f"{feature_id}: provenance.sources must include 'dem' for {generator}")

    if generator in DEM_SOURCE_GENERATORS and not synthetic and not provenance.get("dem_tile"):
        errors.append(f"{feature_id}: provenance.dem_tile required for {generator}")

    if not synthetic and generator != "synthetic_fixture" and not provenance.get("layer"):
        # DEM generators may omit layer when dem_tile is set
        if generator not in DEM_SOURCE_GENERATORS:
            errors.append(f"{feature_id}: provenance.layer required for {generator}")

    return errors
