"""Load Region Pack layers + discovery catalog (GeoJSON FeatureCollections)."""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

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


def _normalize_catalog_props(props: dict) -> dict:
    """Ensure fixture and rich catalog entries share required keys."""
    out = dict(props)
    if "generator" not in out:
        out["generator"] = "synthetic_fixture"
    if "provenance" not in out:
        out["provenance"] = {
            "sources": ["synthetic"],
            "method": "fixture_seed",
        }
    if "evidence" not in out:
        out["evidence"] = {}
    if "densify" not in out:
        out["densify"] = {
            "cell_id": f"fixture_{out.get('id', 'x')}",
            "parent_id": None,
            "densify_allowed": True,
            "grid_res_deg": 0.02,
        }
    out.setdefault("catalog_schema_version", "0.3.0")
    return out


def load_pack_data(pack_dir: Path) -> PackData:
    """Load pack layers. Canonical candidate file is ``layers/catalog.geojson``."""
    layers = pack_dir / "layers"
    catalog_path = layers / "catalog.geojson"
    seeds_path = layers / "seeds.geojson"

    if catalog_path.exists():
        catalog_pts = _load_points(catalog_path, "catalog")
    elif seeds_path.exists():
        warnings.warn(
            f"{pack_dir}: layers/seeds.geojson is deprecated; use layers/catalog.geojson",
            DeprecationWarning,
            stacklevel=2,
        )
        catalog_pts = _load_points(seeds_path, "seed")
    else:
        catalog_pts = []

    normalized = [
        NamedPoint(
            id=p.id,
            name=p.name,
            point=p.point,
            properties=_normalize_catalog_props(p.properties),
        )
        for p in catalog_pts
    ]
    return PackData(
        pack_dir=pack_dir,
        settlements=_load_points(layers / "settlements.geojson", "settlement"),
        roads=_load_points(layers / "road_nodes.geojson", "road"),
        water=_load_points(layers / "water.geojson", "water"),
        catalog=normalized,
        elevation_samples=_load_points(layers / "elevation.geojson", "elev"),
    )
