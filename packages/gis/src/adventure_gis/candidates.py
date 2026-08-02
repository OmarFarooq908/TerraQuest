"""Generate scored-ready candidates from pack fixture layers."""

from __future__ import annotations

import math
from collections.abc import Iterable

from adventure_core.geo import Point, haversine_km
from adventure_core.schemas import Candidate, CandidateFeatures

from adventure_gis.pack_data import NamedPoint, PackData
from adventure_gis.sentinel import lookup_sentinel_indices
from adventure_gis.vlm_join import lookup_vlm_features

# Remoteness when settlement layer is absent — neutral unknown, not "maximally remote".
_UNKNOWN_REMOTENESS = 0.5

# Settlement density kernel (deterministic, pack-reproducible).
_SETTLEMENT_DENSITY_RADIUS_KM = 10.0
# Weighted count at which density saturates near 1.0 (see docs/gis-features.md).
_SETTLEMENT_DENSITY_REF = 4.0

# OSM highway=* → access quality for light vehicles (higher = easier sedan access).
_HIGHWAY_ACCESS: dict[str, float] = {
    "motorway": 1.0,
    "trunk": 0.95,
    "primary": 0.9,
    "secondary": 0.85,
    "tertiary": 0.75,
    "unclassified": 0.65,
    "residential": 0.7,
    "living_street": 0.65,
    "service": 0.55,
    "road": 0.6,
    "track": 0.4,
    "path": 0.25,
    "footway": 0.2,
    "bridleway": 0.25,
    "cycleway": 0.35,
    "pedestrian": 0.2,
}


def _min_dist_km(origin: Point, places: Iterable[NamedPoint]) -> float | None:
    """Nearest place distance in km, or None if the layer is empty."""
    dists = [haversine_km(origin, p.point) for p in places]
    if not dists:
        return None
    return min(dists)


def _clamp01(x: float) -> float:
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return max(0.0, min(1.0, x))


def _prop_unit(props: dict, key: str, default: float) -> float:
    """Read a unit-interval property; coerce bad values instead of leaking sentinels."""
    raw = props.get(key, default)
    try:
        return _clamp01(float(raw))
    except (TypeError, ValueError):
        return _clamp01(default)


def _prop_float(props: dict, key: str, default: float) -> float:
    raw = props.get(key, default)
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return default
    if math.isnan(x) or math.isinf(x):
        return default
    return x


def _local_relief_m(origin: Point, samples: list[NamedPoint], radius_km: float = 5.0) -> float:
    nearby = [
        float(s.properties.get("elevation_m", 0))
        for s in samples
        if haversine_km(origin, s.point) <= radius_km
    ]
    if len(nearby) < 2:
        if not samples:
            return 0.0
        all_e = [float(s.properties.get("elevation_m", 0)) for s in samples]
        return max(all_e) - min(all_e)
    return max(nearby) - min(nearby)


def _settlement_density_kernel(
    origin: Point,
    settlements: list[NamedPoint],
    *,
    radius_km: float = _SETTLEMENT_DENSITY_RADIUS_KM,
) -> tuple[float | None, int | None]:
    """Population-weighted, distance-decayed settlement density in ``radius_km``.

    Returns ``(density in [0,1], count)`` or ``(None, None)`` when the layer is empty.
    """
    if not settlements:
        return None, None
    weighted = 0.0
    count = 0
    for s in settlements:
        d = haversine_km(origin, s.point)
        if d > radius_km:
            continue
        count += 1
        pop = _prop_float(s.properties, "population", 0.0)
        # log10 population bump: village ~1.1, town ~1.5, city ~2.0
        pop_w = 1.0 + min(1.0, math.log10(1.0 + max(0.0, pop)) / 5.0)
        decay = 1.0 - (d / radius_km)
        weighted += pop_w * decay
    return _clamp01(weighted / _SETTLEMENT_DENSITY_REF), count


def _is_light_vehicle(vehicle: str | None, vehicle_class: str | None) -> bool:
    v = (vehicle or "").lower()
    vc = (vehicle_class or "").lower()
    return any(x in v for x in ("swift", "hatch", "sedan", "city", "corolla")) or vc in {
        "hatchback",
        "sedan",
    }


def _is_capable_vehicle(vehicle: str | None, vehicle_class: str | None) -> bool:
    v = (vehicle or "").lower()
    vc = (vehicle_class or "").lower()
    return vc in {"suv", "suv_4x4"} or any(x in v for x in ("4x4", "jeep", "land cruiser", "prado"))


def _highway_class_score(highway: str | None) -> float:
    if not highway:
        return 0.5
    return _HIGHWAY_ACCESS.get(highway, 0.5)


def _nearest_road(origin: Point, roads: list[NamedPoint]) -> tuple[float | None, str | None]:
    """Geometric nearest road-node distance and ``highway`` tag (diagnostics)."""
    if not roads:
        return None, None
    best_d: float | None = None
    best_hwy: str | None = None
    for r in roads:
        d = haversine_km(origin, r.point)
        if best_d is None or d < best_d:
            best_d = d
            raw = r.properties.get("highway")
            hwy = str(raw).strip().lower() if raw not in (None, "") else None
            best_hwy = hwy
    return best_d, best_hwy


def _select_access_road(
    origin: Point,
    roads: list[NamedPoint],
    *,
    vehicle: str | None,
    vehicle_class: str | None,
) -> tuple[float | None, str | None]:
    """Pick the road node that best explains *usable* access for this vehicle.

    Pure nearest-node is wrong for sedans when a ``path`` sits closer than a
    ``secondary``. Utility = effective_class / (1 + dist_km / 5), with shorter
    distance winning ties.
    """
    if not roads:
        return None, None
    light = _is_light_vehicle(vehicle, vehicle_class)
    capable = _is_capable_vehicle(vehicle, vehicle_class)

    best_key: tuple[float, float, float] | None = None
    best_d: float | None = None
    best_hwy: str | None = None
    for r in roads:
        d = haversine_km(origin, r.point)
        raw = r.properties.get("highway")
        hwy = str(raw).strip().lower() if raw not in (None, "") else None
        class_score = _highway_class_score(hwy)
        if light:
            effective = class_score
        elif capable:
            effective = max(class_score, 0.35)
        else:
            effective = 0.5 + 0.5 * class_score
        utility = effective / (1.0 + d / 5.0)
        key = (utility, -d, class_score)
        if best_key is None or key > best_key:
            best_key = key
            best_d = d
            best_hwy = hwy
    return best_d, best_hwy


def _access_fit(
    dist_road_km: float | None,
    highway: str | None,
    vehicle: str | None,
    vehicle_class: str | None,
    days: float | None,
) -> float:
    """Sedan/hatchback-friendly: prefer places near *usable* roads, not just any node."""
    if dist_road_km is None:
        # Missing road layer — do not pretend far-road isolation.
        return 0.35

    if dist_road_km <= 2:
        base = 0.95
    elif dist_road_km <= 8:
        base = 0.8
    elif dist_road_km <= 15:
        base = 0.55
    elif dist_road_km <= 25:
        base = 0.3
    else:
        base = 0.1

    light = _is_light_vehicle(vehicle, vehicle_class)
    capable = _is_capable_vehicle(vehicle, vehicle_class)

    class_score = _highway_class_score(highway)
    rough = highway in {"track", "path", "footway", "bridleway", "pedestrian"}

    if light:
        # Distance-only base blended with road class — tracks hurt light cars.
        base = base * (0.5 + 0.5 * class_score)
        if rough and dist_road_km > 3:
            base *= 0.55
        if dist_road_km > 12:
            base *= 0.5
    elif capable:
        base = base * (0.75 + 0.25 * max(class_score, 0.35))
    else:
        base = base * (0.6 + 0.4 * class_score)
        if rough and dist_road_km > 8:
            base *= 0.7

    if days is not None and days <= 3 and dist_road_km > 20:
        base *= 0.4
    return _clamp01(base)


def _claim_for(seed: NamedPoint, features: CandidateFeatures) -> str:
    kind = str(seed.properties.get("kind", "place"))
    mapping = {
        "alpine_lake": "alpine lake with limited nearby settlement",
        "hidden_valley": "remote valley with high isolation",
        "viewpoint": "scenic viewpoint with strong local relief",
        "abandoned_track": "forgotten track / low-connectivity access spur",
        "shepherd_settlement": "possible seasonal / sparse settlement remnant",
        "river_crossing": "interesting river crossing with access tradeoffs",
        "forest_river": "forested river corridor with low crowd proxy",
    }
    return mapping.get(kind, f"exploration candidate ({kind})")


def _round_km(dist: float | None) -> float | None:
    if dist is None:
        return None
    return round(dist, 2)


def generate_candidates(
    pack: PackData,
    *,
    vehicle: str | None = None,
    vehicle_class: str | None = None,
    days: float | None = None,
) -> list[Candidate]:
    """Deterministic feature extraction for each seed location."""
    candidates: list[Candidate] = []

    for seed in pack.catalog:
        origin = seed.point
        dist_settlement = _min_dist_km(origin, pack.settlements)
        dist_road_geom, nearest_highway_geom = _nearest_road(origin, pack.roads)
        dist_road, access_highway = _select_access_road(
            origin,
            pack.roads,
            vehicle=vehicle,
            vehicle_class=vehicle_class,
        )
        dist_water = _min_dist_km(origin, pack.water)
        settlement_density, settlements_within = _settlement_density_kernel(
            origin, pack.settlements
        )
        relief = _prop_float(seed.properties, "relief_m", 0.0)
        if relief <= 0:
            relief = _local_relief_m(origin, pack.elevation_samples)
        elev = _prop_float(seed.properties, "elevation_m", 0.0)

        # Isolation vs OSM settlements. Offset is low so valley corridors
        # (Skardu-scale) still produce a remoteness gradient; synthetic fixtures
        # with 20–40 km gaps remain near 1.0.
        layer_flags: dict[str, bool] = {
            "settlements_layer_empty": dist_settlement is None,
            "roads_layer_empty": dist_road is None,
            "water_layer_empty": dist_water is None,
            "sentinel_indices_layer_empty": not pack.sentinel_indices,
            "vlm_features_layer_empty": not pack.vlm_features,
        }
        ndvi, ndwi, sentinel_meta = lookup_sentinel_indices(seed.id, origin, pack.sentinel_indices)
        vlm_evidence = lookup_vlm_features(seed.id, pack.vlm_features)
        if dist_settlement is None:
            remoteness = _UNKNOWN_REMOTENESS
        else:
            remoteness = _clamp01((dist_settlement - 2.0) / 18.0)

        terrain = _clamp01(relief / 1200.0)
        kind = str(seed.properties.get("kind", ""))
        tags = list(seed.properties.get("tags") or [])
        if kind:
            tags.append(kind)

        if kind == "alpine_lake" or seed.properties.get("has_water"):
            water = 0.95
            if dist_water is None:
                dist_water = 0.2
            else:
                dist_water = min(dist_water, 0.2)
        elif "river" in tags or kind == "river_crossing":
            if dist_water is None:
                water = 0.85
            else:
                water = max(0.85, _clamp01(1.0 - dist_water / 15.0))
        elif dist_water is None:
            water = 0.0
        else:
            water = _clamp01(1.0 - dist_water / 15.0)

        viewpoint = terrain * 0.7 + (_clamp01(elev / 4500.0) * 0.3)
        if kind == "viewpoint":
            viewpoint = max(viewpoint, 0.85)

        building_density = _prop_unit(seed.properties, "building_density", 0.1)
        crowd_prop = _prop_unit(seed.properties, "crowd", building_density)
        # Prefer GIS settlement density when the settlements layer exists; blend
        # lightly with catalog props so hand-authored fixture cues still matter.
        if settlement_density is not None:
            crowd = _clamp01(0.7 * settlement_density + 0.3 * crowd_prop)
            density_for_novelty = settlement_density
        else:
            crowd = crowd_prop
            density_for_novelty = building_density
        novelty = _clamp01(remoteness * 0.7 + (1.0 - density_for_novelty) * 0.3)

        forest_prop = _prop_unit(seed.properties, "forest", 0.0)
        if "forest" in tags:
            forest_prop = max(forest_prop, 0.75)
        forest = forest_prop

        access = _access_fit(dist_road, access_highway, vehicle, vehicle_class, days)
        camping = _clamp01(
            (1.0 - _prop_unit(seed.properties, "slope", 0.3)) * 0.6 + water * 0.25 + access * 0.15
        )
        risk = _clamp01(
            _prop_unit(seed.properties, "hazard", 0.2) + (0.3 if relief > 1000 else 0.0)
        )
        restriction = _prop_unit(seed.properties, "protected", 0.0)

        features = CandidateFeatures(
            remoteness=remoteness,
            terrain_drama=terrain,
            water=water,
            viewpoint=viewpoint,
            novelty=novelty,
            access_fit=access,
            camping=camping,
            forest=forest,
            crowd=crowd,
            risk=risk,
            restriction=restriction,
            dist_settlement_km=_round_km(dist_settlement),
            dist_road_km=_round_km(dist_road),
            dist_water_km=_round_km(dist_water),
            elevation_m=elev,
            relief_m=round(relief, 1),
            settlement_density=settlement_density,
            settlements_within_10km=settlements_within,
            nearest_highway=access_highway,
            ndvi=ndvi,
            ndwi=ndwi,
        )

        provenance = seed.properties.get("provenance") or {}
        catalog_evidence = seed.properties.get("evidence") or {}
        densify = seed.properties.get("densify") or {}
        generator = str(seed.properties.get("generator") or "unknown")
        if generator and generator not in tags:
            tags.append(generator)

        candidates.append(
            Candidate(
                id=seed.id,
                name=seed.name,
                lon=origin.lon,
                lat=origin.lat,
                claim=_claim_for(seed, features),
                features=features,
                tags=sorted(set(tags)),
                evidence={
                    "kind": kind,
                    "generator": generator,
                    "generator_version": seed.properties.get("generator_version", "1"),
                    "catalog_schema_version": seed.properties.get(
                        "catalog_schema_version", "0.3.0"
                    ),
                    "dist_settlement_km": features.dist_settlement_km,
                    "dist_road_km": features.dist_road_km,
                    "dist_road_geom_km": _round_km(dist_road_geom),
                    "dist_water_km": features.dist_water_km,
                    "layer_flags": layer_flags,
                    "elevation_m": elev,
                    "relief_m": features.relief_m,
                    "forest": forest,
                    "crowd": crowd,
                    "settlement_density": settlement_density,
                    "settlements_within_10km": settlements_within,
                    "nearest_highway": access_highway,
                    "nearest_highway_geom": nearest_highway_geom,
                    "ndvi": ndvi,
                    "ndwi": ndwi,
                    "sentinel": sentinel_meta or None,
                    "vlm": vlm_evidence,
                    "osm_id": (provenance.get("osm_id") if isinstance(provenance, dict) else None)
                    or seed.properties.get("osm_id"),
                    "provenance": provenance,
                    "discovery_evidence": catalog_evidence,
                    "densify": densify,
                    "source": ",".join(provenance.get("sources", []))
                    if isinstance(provenance, dict) and provenance.get("sources")
                    else seed.properties.get("source", "catalog"),
                },
            )
        )

    return candidates
