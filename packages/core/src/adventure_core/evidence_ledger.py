"""Evidence ledger v2 — required catalog evidence/provenance per generator (#19 / #64).

Field-completeness contract for science/trust. v1: required evidence keys +
source kinds. v2: required ``provenance.osm_id`` on OSM-*element* generators.
DEM window polygons remain deferred.
"""

from __future__ import annotations

from typing import Any, get_args

from adventure_core.catalog import GeneratorName

EVIDENCE_LEDGER_VERSION = "2"

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

# Catalog points derived from a concrete OSM node/way/relation (ledger v2).
# Grid isolation uses OSM settlements as input but is not itself an OSM element.
OSM_ELEMENT_GENERATORS = frozenset(
    {
        "track_terminus",
        "road_spur",
        "named_waterbody",
        "unnamed_waterbody",
        "osm_peak",
        "osm_viewpoint",
    }
)


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


def _valid_osm_id(value: Any) -> bool:
    return coerce_positive_osm_id(value) is not None


def coerce_positive_osm_id(value: Any) -> int | None:
    """Return a positive OSM id, or None if missing/invalid.

    Accepts ints and integral floats (common in GeoJSON). Rejects bools,
    non-integral floats, strings, zero, and negatives.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        as_int = int(value)
        return as_int if as_int > 0 else None
    return None


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

    if gen in DEM_SOURCE_GENERATORS and not synthetic:
        dem_tile = provenance.get("dem_tile")
        if not (isinstance(dem_tile, str) and dem_tile.strip()):
            errors.append(f"{feature_id}: provenance.dem_tile required for {gen}")

    if not synthetic and gen != "synthetic_fixture":
        layer = provenance.get("layer")
        # DEM generators may omit layer when dem_tile is set
        if gen not in DEM_SOURCE_GENERATORS and not (isinstance(layer, str) and layer.strip()):
            errors.append(f"{feature_id}: provenance.layer required for {gen}")

    if (
        not synthetic
        and gen in OSM_ELEMENT_GENERATORS
        and not _valid_osm_id(provenance.get("osm_id"))
    ):
        errors.append(
            f"{feature_id}: provenance.osm_id must be a positive int for {gen} "
            "(evidence ledger v2; OSM-element generators)"
        )

    if "ontology_ids" in evidence:
        raw_ids = evidence["ontology_ids"]
        if not isinstance(raw_ids, list):
            errors.append(f"{feature_id}: evidence.ontology_ids must be a list")
        else:
            for i, item in enumerate(raw_ids):
                if not isinstance(item, str):
                    errors.append(f"{feature_id}: evidence.ontology_ids[{i}] must be a string")
            str_ids = [x for x in raw_ids if isinstance(x, str)]
            # Lazy import: ontology loads configs; keep ledger import light.
            from adventure_core.ontology import validate_ontology_ids

            for msg in validate_ontology_ids(str_ids, canonical_only=True):
                errors.append(f"{feature_id}: evidence.ontology_ids — {msg}")

    return errors
