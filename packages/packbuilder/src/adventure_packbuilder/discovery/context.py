"""Shared layer context for discovery generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adventure_core.catalog import DensifyHook, DiscoveryConfig
from adventure_core.geo import Point, haversine_km

from adventure_packbuilder.osm import layer_points


@dataclass
class LineFeature:
    id: str
    coords: list[tuple[float, float]]  # (lon, lat)
    props: dict[str, Any]

    @property
    def start(self) -> Point:
        lon, lat = self.coords[0]
        return Point(lon, lat)

    @property
    def end(self) -> Point:
        lon, lat = self.coords[-1]
        return Point(lon, lat)


@dataclass
class DiscoveryContext:
    bbox: list[float]
    config: DiscoveryConfig
    settlements: list[Point]
    settlement_props: list[dict[str, Any]]
    water_points: list[tuple[str, Point, dict[str, Any]]]
    road_nodes: list[tuple[str, Point, dict[str, Any]]]
    road_lines: list[LineFeature]
    peaks: list[tuple[str, Point, dict[str, Any]]]
    viewpoints: list[tuple[str, Point, dict[str, Any]]]
    dem_paths: list[Path] = field(default_factory=list)

    def dist_settlement(self, pt: Point) -> float:
        if not self.settlements:
            return 999.0
        return min(haversine_km(pt, s) for s in self.settlements)

    def dist_road(self, pt: Point, *, highways: set[str] | None = None) -> float:
        best = 999.0
        for _, rp, props in self.road_nodes:
            if highways and props.get("highway") not in highways:
                continue
            best = min(best, haversine_km(pt, rp))
        return best

    def dist_drivable(self, pt: Point) -> float:
        return self.dist_road(
            pt,
            highways={"primary", "secondary", "tertiary", "trunk", "unclassified", "residential"},
        )

    def cell_id(self, lon: float, lat: float) -> str:
        res = self.config.grid_res_deg
        return f"c_{lat // res * res:.4f}_{lon // res * res:.4f}"

    def densify_hook(self, lon: float, lat: float, parent_id: str | None = None) -> DensifyHook:
        return DensifyHook(
            cell_id=self.cell_id(lon, lat),
            parent_id=parent_id,
            densify_allowed=True,
            grid_res_deg=self.config.grid_res_deg,
        )

    def human_proxies(self, pt: Point) -> tuple[float, float]:
        dist_s = self.dist_settlement(pt)
        building = 0.35 if dist_s < 2 else (0.12 if dist_s < 8 else 0.03)
        crowd = min(0.9, building * 1.5)
        return building, crowd

    def grid_points(self) -> list[Point]:
        west, south, east, north = self.bbox
        res = self.config.grid_res_deg
        pts: list[Point] = []
        lat = south + res / 2
        while lat < north:
            lon = west + res / 2
            while lon < east:
                pts.append(Point(lon, lat))
                lon += res
            lat += res
        return pts


def _lines_from_fc(fc: dict[str, Any]) -> list[LineFeature]:
    out: list[LineFeature] = []
    for feat in fc.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords_raw = geom.get("coordinates") or []
        if len(coords_raw) < 2:
            continue
        props = feat.get("properties") or {}
        coords = [(float(c[0]), float(c[1])) for c in coords_raw]
        fid = str(props.get("id") or f"line_{len(out)}")
        out.append(LineFeature(id=fid, coords=coords, props=props))
    return out


def build_context(
    layers: dict[str, dict],
    *,
    bbox: list[float],
    config: DiscoveryConfig,
    dem_paths: list[Path] | None = None,
) -> DiscoveryContext:
    settlements_pts = layer_points(layers.get("settlements", {"features": []}))
    return DiscoveryContext(
        bbox=bbox,
        config=config,
        settlements=[p for _, p, _ in settlements_pts],
        settlement_props=[props for _, _, props in settlements_pts],
        water_points=layer_points(layers.get("water", {"features": []})),
        road_nodes=layer_points(layers.get("road_nodes", {"features": []})),
        road_lines=_lines_from_fc(layers.get("road_lines", {"features": []})),
        peaks=layer_points(layers.get("peaks", {"features": []})),
        viewpoints=layer_points(layers.get("viewpoints", {"features": []})),
        dem_paths=list(dem_paths or []),
    )
