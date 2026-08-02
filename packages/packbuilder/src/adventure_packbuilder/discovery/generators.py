"""Named deterministic discovery generators."""

from __future__ import annotations

from adventure_core.catalog import CatalogCandidate, Provenance
from adventure_core.evidence_ledger import coerce_positive_osm_id
from adventure_core.geo import Point
from adventure_core.ontology import water_kind_to_ontology_id

from adventure_packbuilder.dem import local_relief_from_dem, sample_elevations
from adventure_packbuilder.discovery.context import DiscoveryContext


def _is_named(props: dict) -> bool:
    name = str(props.get("name") or "")
    return bool(name) and not name.startswith("unnamed_")


def _base_score_isolation(dist_s: float) -> float:
    return min(1.0, dist_s / 25.0)


def _require_osm_id(props: dict) -> int | None:
    """Ledger v2: OSM-element candidates need a positive osm_id."""
    return coerce_positive_osm_id(props.get("osm_id"))


# ---------------------------------------------------------------------------
# Access / graph-ish generators
# ---------------------------------------------------------------------------


def gen_track_terminus(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    out: list[CatalogCandidate] = []
    lines = [ln for ln in ctx.road_lines if ln.props.get("highway") in {"track", "path"}]
    if not lines:
        # Fallback: isolated track centroids when lines unavailable (Overpass path)
        for sid, pt, props in ctx.road_nodes:
            if props.get("highway") not in {"track", "path"}:
                continue
            dist_s = ctx.dist_settlement(pt)
            if dist_s < 3.0:
                continue
            osm_id = _require_osm_id(props)
            if osm_id is None:
                continue
            building, crowd = ctx.human_proxies(pt)
            cid = f"gen:track_terminus:{sid}:centroid"
            out.append(
                CatalogCandidate(
                    id=cid,
                    name=str(props.get("name") or f"track_terminus_{osm_id}"),
                    lon=pt.lon,
                    lat=pt.lat,
                    kind="abandoned_track",
                    generator="track_terminus",
                    tags=["track", "access", str(props.get("highway"))],
                    provenance=Provenance(
                        sources=["osm"],
                        method="track_centroid_fallback",
                        osm_id=osm_id,
                        osm_type=props.get("osm_type"),
                        layer="road_nodes",
                    ),
                    evidence={
                        "discovery_score": _base_score_isolation(dist_s) + 0.1,
                        "dist_settlement_km": round(dist_s, 2),
                        "endpoint": "centroid",
                    },
                    densify=ctx.densify_hook(pt.lon, pt.lat),
                    building_density=building,
                    crowd=crowd,
                    hazard=0.25,
                    highway=props.get("highway"),
                )
            )
        return out

    for ln in lines:
        for endpoint_name, pt in (("a", ln.start), ("b", ln.end)):
            dist_s = ctx.dist_settlement(pt)
            if dist_s < 2.5:
                continue
            osm_id = _require_osm_id(ln.props)
            if osm_id is None:
                continue
            building, crowd = ctx.human_proxies(pt)
            cid = f"gen:track_terminus:{ln.id}:{endpoint_name}"
            out.append(
                CatalogCandidate(
                    id=cid,
                    name=str(ln.props.get("name") or f"track_terminus_{osm_id}_{endpoint_name}"),
                    lon=pt.lon,
                    lat=pt.lat,
                    kind="abandoned_track",
                    generator="track_terminus",
                    tags=["track", "access", "terminus", str(ln.props.get("highway"))],
                    provenance=Provenance(
                        sources=["osm"],
                        method="linestring_endpoint",
                        osm_id=osm_id,
                        osm_type=ln.props.get("osm_type"),
                        layer="road_lines",
                        extra={"endpoint": endpoint_name},
                    ),
                    evidence={
                        "discovery_score": _base_score_isolation(dist_s) + 0.15,
                        "dist_settlement_km": round(dist_s, 2),
                        "endpoint": endpoint_name,
                        "line_id": ln.id,
                    },
                    densify=ctx.densify_hook(pt.lon, pt.lat),
                    building_density=building,
                    crowd=crowd,
                    hazard=0.25,
                    highway=ln.props.get("highway"),
                )
            )
    return out


def gen_road_spur(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    """Track/path with one end near drivable network and the other more remote."""
    out: list[CatalogCandidate] = []
    lines = [ln for ln in ctx.road_lines if ln.props.get("highway") in {"track", "path"}]
    for ln in lines:
        a, b = ln.start, ln.end
        da_road, db_road = ctx.dist_drivable(a), ctx.dist_drivable(b)
        da_set, db_set = ctx.dist_settlement(a), ctx.dist_settlement(b)
        # Spur: one end attached to roads, far end more isolated
        if da_road <= 1.2 and db_set > da_set and db_set >= 3.0:
            far, near_dist_road, far_label = b, da_road, "b"
        elif db_road <= 1.2 and da_set > db_set and da_set >= 3.0:
            far, near_dist_road, far_label = a, db_road, "a"
        else:
            continue
        osm_id = _require_osm_id(ln.props)
        if osm_id is None:
            continue
        building, crowd = ctx.human_proxies(far)
        dist_s = ctx.dist_settlement(far)
        cid = f"gen:road_spur:{ln.id}:{far_label}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=str(ln.props.get("name") or f"road_spur_{osm_id}"),
                lon=far.lon,
                lat=far.lat,
                kind="abandoned_track",
                generator="road_spur",
                tags=["track", "spur", "access"],
                provenance=Provenance(
                    sources=["osm"],
                    method="spur_endpoint",
                    osm_id=osm_id,
                    osm_type=ln.props.get("osm_type"),
                    layer="road_lines",
                    extra={"far_endpoint": far_label},
                ),
                evidence={
                    "discovery_score": _base_score_isolation(dist_s) + 0.25,
                    "dist_settlement_km": round(dist_s, 2),
                    "dist_drivable_near_end_km": round(near_dist_road, 2),
                    "far_endpoint": far_label,
                },
                densify=ctx.densify_hook(far.lon, far.lat),
                building_density=building,
                crowd=crowd,
                hazard=0.25,
                highway=ln.props.get("highway"),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Water generators
# ---------------------------------------------------------------------------


def _water_candidates(ctx: DiscoveryContext, *, named: bool) -> list[CatalogCandidate]:
    out: list[CatalogCandidate] = []
    gen = "named_waterbody" if named else "unnamed_waterbody"
    for sid, pt, props in ctx.water_points:
        is_named = _is_named(props)
        if named != is_named:
            continue
        osm_id = _require_osm_id(props)
        if osm_id is None:
            continue
        kind_raw = props.get("kind") or "lake"
        seed_kind = "alpine_lake" if kind_raw == "lake" else "river_crossing"
        dist_s = ctx.dist_settlement(pt)
        building, crowd = ctx.human_proxies(pt)
        # Prefer remote + lakes slightly
        score = _base_score_isolation(dist_s) + (0.2 if kind_raw == "lake" else 0.05)
        if named:
            score += 0.05
        cid = f"gen:{gen}:{sid}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=str(props.get("name") or f"{gen}_{osm_id}"),
                lon=pt.lon,
                lat=pt.lat,
                kind=seed_kind,
                generator=gen,
                tags=["water", kind_raw] + (["river"] if kind_raw == "river" else []),
                provenance=Provenance(
                    sources=["osm"],
                    method="water_centroid",
                    osm_id=osm_id,
                    osm_type=props.get("osm_type"),
                    layer="water",
                ),
                evidence={
                    "discovery_score": score,
                    "dist_settlement_km": round(dist_s, 2),
                    "water_kind": kind_raw,
                    "named": named,
                    "ontology_ids": [water_kind_to_ontology_id(str(kind_raw))],
                },
                densify=ctx.densify_hook(pt.lon, pt.lat),
                building_density=building,
                crowd=crowd,
                forest=0.35 if kind_raw in {"lake", "river"} else 0.1,
                has_water=True,
            )
        )
    return out


def gen_named_waterbody(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    return _water_candidates(ctx, named=True)


def gen_unnamed_waterbody(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    return _water_candidates(ctx, named=False)


# ---------------------------------------------------------------------------
# OSM named landmarks (still generators — not a silent POI dump)
# ---------------------------------------------------------------------------


def gen_osm_peak(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    out: list[CatalogCandidate] = []
    for sid, pt, props in ctx.peaks:
        osm_id = _require_osm_id(props)
        if osm_id is None:
            continue
        dist_s = ctx.dist_settlement(pt)
        building, crowd = ctx.human_proxies(pt)
        elev = props.get("elevation_m") or props.get("ele")
        try:
            elev_f = float(elev) if elev is not None else None
        except (TypeError, ValueError):
            elev_f = None
        score = _base_score_isolation(dist_s) + (0.2 if elev_f and elev_f > 3500 else 0.1)
        cid = f"gen:osm_peak:{sid}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=str(props.get("name") or f"peak_{osm_id}"),
                lon=pt.lon,
                lat=pt.lat,
                kind="viewpoint",
                generator="osm_peak",
                tags=["viewpoint", "peak", "geology"],
                provenance=Provenance(
                    sources=["osm"],
                    method="osm_peak_node",
                    osm_id=osm_id,
                    osm_type=props.get("osm_type"),
                    layer="peaks",
                ),
                evidence={
                    "discovery_score": score,
                    "dist_settlement_km": round(dist_s, 2),
                    "osm_ele": elev_f,
                },
                densify=ctx.densify_hook(pt.lon, pt.lat),
                building_density=building,
                crowd=crowd,
                hazard=0.45,
                elevation_m=elev_f,
            )
        )
    return out


def gen_osm_viewpoint(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    out: list[CatalogCandidate] = []
    for sid, pt, props in ctx.viewpoints:
        osm_id = _require_osm_id(props)
        if osm_id is None:
            continue
        dist_s = ctx.dist_settlement(pt)
        building, crowd = ctx.human_proxies(pt)
        cid = f"gen:osm_viewpoint:{sid}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=str(props.get("name") or f"viewpoint_{osm_id}"),
                lon=pt.lon,
                lat=pt.lat,
                kind="viewpoint",
                generator="osm_viewpoint",
                tags=["viewpoint"],
                provenance=Provenance(
                    sources=["osm"],
                    method="osm_viewpoint_node",
                    osm_id=osm_id,
                    osm_type=props.get("osm_type"),
                    layer="viewpoints",
                ),
                evidence={
                    "discovery_score": _base_score_isolation(dist_s) + 0.1,
                    "dist_settlement_km": round(dist_s, 2),
                },
                densify=ctx.densify_hook(pt.lon, pt.lat),
                building_density=building,
                crowd=crowd,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Terrain / isolation generators (grid + DEM)
# ---------------------------------------------------------------------------


def gen_isolation_maximum(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    grid = ctx.grid_points()
    if not grid:
        return []
    scores = [ctx.dist_settlement(p) for p in grid]
    res = ctx.config.grid_res_deg
    index = {(round(p.lon, 6), round(p.lat, 6)): scores[i] for i, p in enumerate(grid)}
    out: list[CatalogCandidate] = []
    for i, pt in enumerate(grid):
        s = scores[i]
        if s < 4.0:
            continue
        neighbors = []
        for dlon, dlat in ((res, 0), (-res, 0), (0, res), (0, -res)):
            key = (round(pt.lon + dlon, 6), round(pt.lat + dlat, 6))
            if key in index:
                neighbors.append(index[key])
        # Strict local maximum on the isolation surface
        if neighbors and s <= max(neighbors):
            continue
        building, crowd = ctx.human_proxies(pt)
        cid = f"gen:isolation_maximum:{ctx.cell_id(pt.lon, pt.lat)}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=f"isolation_max_{ctx.cell_id(pt.lon, pt.lat)}",
                lon=pt.lon,
                lat=pt.lat,
                kind="hidden_valley",
                generator="isolation_maximum",
                tags=["isolation", "remoteness"],
                provenance=Provenance(
                    sources=["osm"],
                    method="settlement_distance_grid_local_max",
                    layer="settlements",
                    extra={"grid_res_deg": res},
                ),
                evidence={
                    "discovery_score": _base_score_isolation(s) + 0.3,
                    "dist_settlement_km": round(s, 2),
                    "grid_res_deg": res,
                },
                densify=ctx.densify_hook(pt.lon, pt.lat),
                building_density=building,
                crowd=crowd,
                hazard=0.2,
            )
        )
    return out


def gen_dem_local_max(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    if not ctx.dem_paths:
        return []
    grid = ctx.grid_points()
    elevs = sample_elevations([(p.lon, p.lat) for p in grid], ctx.dem_paths)
    res = ctx.config.grid_res_deg
    cells: list[tuple[Point, float]] = [
        (p, float(e)) for p, e in zip(grid, elevs, strict=True) if e is not None
    ]
    if not cells:
        return []
    index = {(round(p.lon, 6), round(p.lat, 6)): elev for p, elev in cells}
    out: list[CatalogCandidate] = []
    for pt, elev in cells:
        neighbors = []
        for dlon, dlat in ((res, 0), (-res, 0), (0, res), (0, -res), (res, res), (-res, -res)):
            key = (round(pt.lon + dlon, 6), round(pt.lat + dlat, 6))
            if key in index:
                neighbors.append(index[key])
        if not neighbors or elev <= max(neighbors):
            continue
        dist_s = ctx.dist_settlement(pt)
        if dist_s < 2.0:
            continue
        building, crowd = ctx.human_proxies(pt)
        cid = f"gen:dem_local_max:{ctx.cell_id(pt.lon, pt.lat)}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=f"dem_peak_{int(elev)}m_{ctx.cell_id(pt.lon, pt.lat)}",
                lon=pt.lon,
                lat=pt.lat,
                kind="viewpoint",
                generator="dem_local_max",
                tags=["viewpoint", "peak", "dem", "geology"],
                provenance=Provenance(
                    sources=["dem"],
                    method="dem_grid_local_max",
                    dem_tile=ctx.dem_paths[0].name if ctx.dem_paths else None,
                    extra={"grid_res_deg": res},
                ),
                evidence={
                    "discovery_score": min(1.0, elev / 6000.0)
                    + _base_score_isolation(dist_s) * 0.3,
                    "dist_settlement_km": round(dist_s, 2),
                    "elevation_m": round(elev, 1),
                },
                densify=ctx.densify_hook(pt.lon, pt.lat),
                building_density=building,
                crowd=crowd,
                hazard=0.4,
                elevation_m=round(elev, 1),
            )
        )
    return out


def gen_terrain_relief_hotspot(ctx: DiscoveryContext) -> list[CatalogCandidate]:
    if not ctx.dem_paths:
        return []
    grid = ctx.grid_points()
    out: list[CatalogCandidate] = []
    for pt in grid:
        relief = local_relief_from_dem(
            pt.lon, pt.lat, ctx.dem_paths, radius_deg=ctx.config.grid_res_deg
        )
        if relief < 400:
            continue
        dist_s = ctx.dist_settlement(pt)
        building, crowd = ctx.human_proxies(pt)
        score = min(1.0, relief / 2000.0) + _base_score_isolation(dist_s) * 0.2
        cid = f"gen:terrain_relief_hotspot:{ctx.cell_id(pt.lon, pt.lat)}"
        out.append(
            CatalogCandidate(
                id=cid,
                name=f"relief_{int(relief)}m_{ctx.cell_id(pt.lon, pt.lat)}",
                lon=pt.lon,
                lat=pt.lat,
                kind="viewpoint",
                generator="terrain_relief_hotspot",
                tags=["relief", "terrain", "viewpoint"],
                provenance=Provenance(
                    sources=["dem"],
                    method="dem_local_relief_window",
                    dem_tile=ctx.dem_paths[0].name if ctx.dem_paths else None,
                ),
                evidence={
                    "discovery_score": score,
                    "dist_settlement_km": round(dist_s, 2),
                    "relief_m": round(relief, 1),
                },
                densify=ctx.densify_hook(pt.lon, pt.lat),
                building_density=building,
                crowd=crowd,
                hazard=0.35 if relief > 1000 else 0.25,
                relief_m=round(relief, 1),
            )
        )
    return out


GENERATORS = {
    "track_terminus": gen_track_terminus,
    "road_spur": gen_road_spur,
    "unnamed_waterbody": gen_unnamed_waterbody,
    "named_waterbody": gen_named_waterbody,
    "isolation_maximum": gen_isolation_maximum,
    "dem_local_max": gen_dem_local_max,
    "terrain_relief_hotspot": gen_terrain_relief_hotspot,
    "osm_peak": gen_osm_peak,
    "osm_viewpoint": gen_osm_viewpoint,
}
