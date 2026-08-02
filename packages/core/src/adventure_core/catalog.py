"""Region Pack candidate catalog schema (discovery pipeline output).

MissionIntent is unchanged: the mission engine only filters + scores catalog
entries. Phase C (mission-time local densification) can attach children via
``densify.parent_id`` / ``cell_id`` without altering the intent contract.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CATALOG_SCHEMA_VERSION = "0.3.0"

GeneratorName = Literal[
    "track_terminus",
    "road_spur",
    "unnamed_waterbody",
    "named_waterbody",
    "isolation_maximum",
    "dem_local_max",
    "terrain_relief_hotspot",
    "osm_peak",
    "osm_viewpoint",
    "synthetic_fixture",
]


class Provenance(BaseModel):
    sources: list[str] = Field(default_factory=list)  # osm | dem | synthetic
    method: str
    osm_id: int | None = None
    osm_type: str | None = None
    layer: str | None = None
    dem_tile: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DensifyHook(BaseModel):
    """Reserved for Phase C local densification around catalog winners."""

    cell_id: str
    parent_id: str | None = None
    densify_allowed: bool = True
    grid_res_deg: float = 0.02


class CatalogCandidate(BaseModel):
    """One discovered place in the pack catalog (GeoJSON properties + geometry)."""

    id: str
    name: str
    lon: float
    lat: float
    kind: str
    generator: str
    generator_version: str = "1"
    catalog_schema_version: str = CATALOG_SCHEMA_VERSION
    tags: list[str] = Field(default_factory=list)
    provenance: Provenance
    evidence: dict[str, Any] = Field(default_factory=dict)
    densify: DensifyHook
    # Featurization hints for the GIS mission layer
    building_density: float = 0.1
    crowd: float = 0.1
    forest: float = 0.1
    hazard: float = 0.2
    protected: float = 0.0
    slope: float = 0.2
    has_water: bool = False
    elevation_m: float | None = None
    relief_m: float | None = None
    highway: str | None = None

    def to_geojson_feature(self) -> dict[str, Any]:
        props = self.model_dump(exclude={"lon", "lat"})
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
            "properties": props,
        }


class GeneratorQuota(BaseModel):
    quota: int = 20
    min_spacing_km: float | None = None  # override global


class DiscoveryConfig(BaseModel):
    """Per-pack discovery controls (configs/packs/*.yaml → discovery:)."""

    min_spacing_km: float = 0.6
    grid_res_deg: float = 0.02
    generators: dict[str, GeneratorQuota] = Field(default_factory=dict)

    def quota_for(self, name: str, default: int = 20) -> int:
        g = self.generators.get(name)
        return g.quota if g else default

    def spacing_for(self, name: str) -> float:
        g = self.generators.get(name)
        if g and g.min_spacing_km is not None:
            return g.min_spacing_km
        return self.min_spacing_km
