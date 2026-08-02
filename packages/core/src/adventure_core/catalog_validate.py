"""Strict validation for Region Pack catalog.geojson (issue #13)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from adventure_core.catalog import (
    CATALOG_SCHEMA_VERSION,
    CatalogCandidate,
    DensifyHook,
    Provenance,
)
from adventure_core.evidence_ledger import validate_evidence_ledger

REQUIRED_FEATURE_KEYS = ("id", "name", "generator", "provenance", "evidence", "densify")


class CatalogValidationError(ValueError):
    """Catalog or pack layout failed strict validation."""


def _point_lon_lat(geom: Any) -> tuple[float, float]:
    if not isinstance(geom, dict):
        raise CatalogValidationError("feature geometry must be an object")
    if geom.get("type") != "Point":
        raise CatalogValidationError(f"geometry type must be Point, got {geom.get('type')!r}")
    coords = geom.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        raise CatalogValidationError("Point coordinates must be [lon, lat]")
    try:
        lon = float(coords[0])
        lat = float(coords[1])
    except (TypeError, ValueError) as exc:
        raise CatalogValidationError(f"invalid coordinates: {coords!r}") from exc
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        raise CatalogValidationError(f"coordinates out of range: {[lon, lat]}")
    return lon, lat


def validate_catalog_feature(feature: dict[str, Any], *, index: int) -> list[str]:
    """Validate one GeoJSON Feature; return error strings (empty if ok)."""
    errors: list[str] = []
    label = f"features[{index}]"
    if not isinstance(feature, dict):
        return [f"{label}: not an object"]
    if feature.get("type") != "Feature":
        errors.append(f"{label}: type must be Feature")

    props = feature.get("properties")
    if not isinstance(props, dict):
        errors.append(f"{label}: properties must be an object")
        return errors

    fid = props.get("id") or feature.get("id") or label
    for key in REQUIRED_FEATURE_KEYS:
        if key not in props:
            errors.append(f"{fid}: missing property {key}")

    try:
        lon, lat = _point_lon_lat(feature.get("geometry"))
    except CatalogValidationError as exc:
        errors.append(f"{fid}: {exc}")
        lon, lat = 0.0, 0.0

    schema = str(props.get("catalog_schema_version") or "")
    if schema and schema != CATALOG_SCHEMA_VERSION:
        errors.append(f"{fid}: catalog_schema_version {schema!r} != {CATALOG_SCHEMA_VERSION!r}")

    # Structural checks via pydantic models (provenance / densify)
    try:
        if "provenance" in props:
            if not isinstance(props["provenance"], dict):
                errors.append(f"{fid}: provenance must be an object")
            else:
                Provenance.model_validate(props["provenance"])
                if not props["provenance"].get("method"):
                    errors.append(f"{fid}: provenance.method is required")
                sources = props["provenance"].get("sources")
                if sources is not None and not isinstance(sources, list):
                    errors.append(f"{fid}: provenance.sources must be a list")
        if "densify" in props:
            DensifyHook.model_validate(props["densify"])
        if "evidence" in props and not isinstance(props["evidence"], dict):
            errors.append(f"{fid}: evidence must be an object")
        elif (
            isinstance(props.get("evidence"), dict)
            and isinstance(props.get("provenance"), dict)
            and props.get("generator")
        ):
            errors.extend(
                validate_evidence_ledger(
                    generator=str(props["generator"]),
                    provenance=props["provenance"],
                    evidence=props["evidence"],
                    feature_id=str(fid),
                )
            )
    except ValidationError as exc:
        errors.append(f"{fid}: schema error: {exc.errors()[0]['msg']}")

    # Optional full CatalogCandidate round-trip when enough fields present
    if not errors and all(k in props for k in REQUIRED_FEATURE_KEYS):
        try:
            CatalogCandidate(
                id=str(props["id"]),
                name=str(props["name"]),
                lon=lon,
                lat=lat,
                kind=str(props.get("kind") or "place"),
                generator=str(props["generator"]),
                generator_version=str(props.get("generator_version") or "1"),
                catalog_schema_version=str(
                    props.get("catalog_schema_version") or CATALOG_SCHEMA_VERSION
                ),
                tags=list(props.get("tags") or []),
                provenance=Provenance.model_validate(props["provenance"]),
                evidence=dict(props.get("evidence") or {}),
                densify=DensifyHook.model_validate(props["densify"]),
                building_density=float(props.get("building_density", 0.1)),
                crowd=float(props.get("crowd", 0.1)),
                forest=float(props.get("forest", 0.1)),
                hazard=float(props.get("hazard", 0.2)),
                protected=float(props.get("protected", 0.0)),
                slope=float(props.get("slope", 0.2)),
                has_water=bool(props.get("has_water", False)),
                elevation_m=props.get("elevation_m"),
                relief_m=props.get("relief_m"),
                highway=props.get("highway"),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            errors.append(f"{fid}: CatalogCandidate invalid: {exc}")

    return errors


def validate_catalog_geojson(data: dict[str, Any]) -> list[str]:
    """Validate a FeatureCollection catalog document."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["catalog root must be an object"]
    if data.get("type") != "FeatureCollection":
        errors.append("catalog type must be FeatureCollection")
    features = data.get("features")
    if not isinstance(features, list):
        errors.append("catalog features must be a list")
        return errors
    if not features:
        errors.append("catalog features is empty")
    for i, feat in enumerate(features):
        errors.extend(validate_catalog_feature(feat if isinstance(feat, dict) else {}, index=i))
    return errors
