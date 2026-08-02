"""Load Region Pack layers + discovery catalog (GeoJSON FeatureCollections)."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from adventure_core.catalog_validate import CatalogValidationError, validate_catalog_geojson
from adventure_core.geo import Point


@dataclass
class NamedPoint:
    id: str
    name: str
    point: Point
    properties: dict = field(default_factory=dict)


@dataclass
class PackData:
    pack_dir: Path
    settlements: list[NamedPoint]
    roads: list[NamedPoint]
    water: list[NamedPoint]
    catalog: list[NamedPoint]
    elevation_samples: list[NamedPoint]
    # Optional Sentinel-2 indices (RFC-0006); empty when layer absent.
    sentinel_indices: list[NamedPoint] = field(default_factory=list)
    # Optional pack-time VLM labels (RFC-0007); empty when layer absent.
    vlm_features: list[NamedPoint] = field(default_factory=list)

    @property
    def seeds(self) -> list[NamedPoint]:
        """Deprecated alias for ``catalog`` (mission API compatibility)."""
        return self.catalog


def _load_points(path: Path, default_kind: str) -> list[NamedPoint]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    features = raw.get("features", [])
    out: list[NamedPoint] = []
    for i, feat in enumerate(features):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom["coordinates"]
        props = feat.get("properties") or {}
        fid = str(props.get("id") or feat.get("id") or f"{default_kind}_{i}")
        name = str(props.get("name") or fid)
        out.append(
            NamedPoint(
                id=fid,
                name=name,
                point=Point(lon=float(coords[0]), lat=float(coords[1])),
                properties=props,
            )
        )
    return out


def load_pack_data(
    pack_dir: Path,
    *,
    allow_legacy_seeds: bool = True,
    strict: bool = True,
) -> PackData:
    """Load pack layers. Canonical candidate file is ``layers/catalog.geojson``.

    When ``strict=True`` (default), catalog FeatureCollection must pass
    ``validate_catalog_geojson`` — no silent fill of required fields.

    Dual-path (catalog + seeds) emits a DeprecationWarning. Strict pack CI uses
    ``validate_pack`` / ``scripts/check_pack.py``, which fails when both files
    are present unless ``--allow-legacy-seeds`` is passed.
    """
    layers = pack_dir / "layers"
    catalog_path = layers / "catalog.geojson"
    seeds_path = layers / "seeds.geojson"

    if catalog_path.exists() and seeds_path.exists():
        warnings.warn(
            f"{pack_dir}: both layers/catalog.geojson and deprecated "
            f"layers/seeds.geojson present; catalog is canonical",
            DeprecationWarning,
            stacklevel=2,
        )

    catalog_file: Path | None = None
    if catalog_path.exists():
        catalog_file = catalog_path
    elif seeds_path.exists():
        warnings.warn(
            f"{pack_dir}: layers/seeds.geojson is deprecated; use layers/catalog.geojson",
            DeprecationWarning,
            stacklevel=2,
        )
        if not allow_legacy_seeds:
            raise FileNotFoundError(
                f"{pack_dir}: missing layers/catalog.geojson "
                f"(legacy seeds.geojson alone requires allow_legacy_seeds=True)"
            )
        catalog_file = seeds_path

    if catalog_file is not None and strict:
        raw = json.loads(catalog_file.read_text(encoding="utf-8"))
        schema_errors = validate_catalog_geojson(raw)
        if schema_errors:
            raise CatalogValidationError(
                f"{catalog_file}: catalog validation failed:\n  - " + "\n  - ".join(schema_errors)
            )

    catalog_pts = _load_points(catalog_file, "catalog") if catalog_file else []

    return PackData(
        pack_dir=pack_dir,
        settlements=_load_points(layers / "settlements.geojson", "settlement"),
        roads=_load_points(layers / "road_nodes.geojson", "road"),
        water=_load_points(layers / "water.geojson", "water"),
        catalog=catalog_pts,
        elevation_samples=_load_points(layers / "elevation.geojson", "elev"),
        sentinel_indices=_load_points(layers / "sentinel_indices.geojson", "sentinel"),
        vlm_features=_load_points(layers / "vlm_features.geojson", "vlm"),
    )
