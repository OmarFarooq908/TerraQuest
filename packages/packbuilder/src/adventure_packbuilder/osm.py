"""Fetch real OpenStreetMap features for a bbox via Overpass API."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx
from adventure_core.geo import Point

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _fc(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _point_feature(
    osm_type: str,
    osm_id: int,
    lon: float,
    lat: float,
    props: dict[str, Any],
) -> dict:
    fid = f"{osm_type}/{osm_id}"
    name = props.get("name") or props.get("name:en")
    if not name or name == fid:
        name = f"unnamed_{props.get('kind') or osm_type}_{osm_id}"
    properties = {
        "id": fid,
        "osm_id": osm_id,
        "osm_type": osm_type,
        "name": name,
        **{k: v for k, v in props.items() if k not in {"name", "name:en"}},
    }
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def _element_point(el: dict) -> tuple[float, float] | None:
    if "lon" in el and "lat" in el:
        return float(el["lon"]), float(el["lat"])
    center = el.get("center")
    if center and "lon" in center and "lat" in center:
        return float(center["lon"]), float(center["lat"])
    return None


def _query_slices(bbox: list[float]) -> list[tuple[str, str, float]]:
    """(name, query, timeout_s) — keep queries small for production reliability."""
    west, south, east, north = bbox
    bb = f"({south},{west},{north},{east})"
    return [
        (
            "places",
            f'[out:json][timeout:40];node["place"~"city|town|village|hamlet|isolated_dwelling"]{bb};out body;',
            45.0,
        ),
        (
            "peaks",
            f'[out:json][timeout:40];node["natural"="peak"]{bb};out body;',
            45.0,
        ),
        (
            "viewpoints",
            f'[out:json][timeout:30];node["tourism"="viewpoint"]{bb};out body;',
            35.0,
        ),
        (
            "lakes",
            f'[out:json][timeout:50];(way["natural"="water"]{bb};way["water"="lake"]{bb};relation["natural"="water"]{bb};);out center tags;',
            55.0,
        ),
        (
            "rivers",
            f'[out:json][timeout:50];way["waterway"="river"]{bb};out center tags;',
            55.0,
        ),
        (
            "roads_main",
            f'[out:json][timeout:50];way["highway"~"primary|secondary|tertiary|trunk"]{bb};out center tags;',
            55.0,
        ),
        (
            "tracks",
            f'[out:json][timeout:50];way["highway"~"track|path"]{bb};out center tags;',
            55.0,
        ),
    ]


_USER_AGENT = "AdventureAI/0.1 (packbuilder; local-first OSM)"


def _post_overpass(url: str, query: str, timeout_s: float) -> dict[str, Any]:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    with httpx.Client(timeout=timeout_s, headers=headers, follow_redirects=True) as client:
        resp = client.post(url, data={"data": query})
        if resp.status_code == 406:
            raise RuntimeError(f"Overpass 406 Not Acceptable from {url} (rate limit / UA)")
        resp.raise_for_status()
        # Overpass sometimes returns HTML error pages
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype and not resp.text.lstrip().startswith("{"):
            raise RuntimeError(f"non-JSON response from {url}: {resp.text[:120]}")
        return resp.json()


def fetch_overpass(
    bbox: list[float],
    *,
    url: str = "https://overpass-api.de/api/interpreter",
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Fetch OSM via sliced Overpass queries; tolerate partial failures."""
    mirrors = [url] + [m for m in OVERPASS_MIRRORS if m != url]
    elements: list[dict] = []
    seen: set[tuple[str, int]] = set()
    ok_slices: list[str] = []
    errors: list[str] = []

    for slice_name, query, slice_timeout in _query_slices(bbox):
        slice_timeout = min(slice_timeout, timeout_s)
        succeeded = False
        for mirror in mirrors:
            try:
                payload = _post_overpass(mirror, query, slice_timeout)
                n = 0
                for el in payload.get("elements", []):
                    key = (el.get("type", ""), int(el.get("id", 0)))
                    if key in seen:
                        continue
                    seen.add(key)
                    elements.append(el)
                    n += 1
                ok_slices.append(f"{slice_name}:{n}")
                succeeded = True
                time.sleep(1.0)  # be kind to public Overpass
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{slice_name}@{mirror}: {type(exc).__name__}: {exc}")
                time.sleep(1.0)
        if not succeeded:
            errors.append(f"{slice_name}:ALL_MIRRORS_FAILED")

    if not elements:
        raise RuntimeError(f"Overpass fetch failed (no elements). Errors: {errors[:8]}")

    return {
        "elements": elements,
        "remark": f"ok_slices={ok_slices}; errors={len(errors)}",
        "errors": errors,
    }


def build_overpass_query(bbox: list[float]) -> str:
    return _query_slices(bbox)[0][1]


def overpass_to_layers(payload: dict[str, Any]) -> dict[str, dict]:
    settlements: list[dict] = []
    peaks: list[dict] = []
    viewpoints: list[dict] = []
    water: list[dict] = []
    road_nodes: list[dict] = []

    for el in payload.get("elements", []):
        pt = _element_point(el)
        if not pt:
            continue
        lon, lat = pt
        tags = el.get("tags") or {}
        osm_type = el.get("type", "node")
        osm_id = int(el.get("id", 0))
        feat = _point_feature(osm_type, osm_id, lon, lat, tags)

        place = tags.get("place")
        if place in {"city", "town", "village", "hamlet", "isolated_dwelling"}:
            feat["properties"]["kind"] = "settlement"
            settlements.append(feat)
            continue

        if tags.get("natural") == "peak":
            feat["properties"]["kind"] = "peak"
            if tags.get("ele"):
                try:
                    feat["properties"]["elevation_m"] = float(str(tags["ele"]).replace("m", ""))
                except ValueError:
                    pass
            peaks.append(feat)
            continue

        if tags.get("tourism") == "viewpoint":
            feat["properties"]["kind"] = "viewpoint"
            viewpoints.append(feat)
            continue

        if (
            tags.get("natural") == "water"
            or tags.get("water") in {"lake", "reservoir", "pond"}
            or tags.get("waterway") in {"river", "stream"}
        ):
            kind = (
                "lake"
                if tags.get("water") in {"lake", "reservoir", "pond"}
                or tags.get("natural") == "water"
                else "river"
            )
            feat["properties"]["kind"] = kind
            feat["properties"]["has_water"] = True
            water.append(feat)
            continue

        highway = tags.get("highway")
        if highway:
            feat["properties"]["kind"] = "road"
            feat["properties"]["highway"] = highway
            road_nodes.append(feat)

    return {
        "settlements": _fc(settlements),
        "peaks": _fc(peaks),
        "viewpoints": _fc(viewpoints),
        "water": _fc(water),
        "road_nodes": _fc(road_nodes),
        "meta": {
            "retrieved_at": datetime.now(UTC).isoformat(),
            "element_count": len(payload.get("elements", [])),
            "settlement_count": len(settlements),
            "water_count": len(water),
            "road_count": len(road_nodes),
            "peak_count": len(peaks),
            "viewpoint_count": len(viewpoints),
            "remark": payload.get("remark"),
            "errors": payload.get("errors", [])[:10],
        },
    }


def layer_points(fc: dict) -> list[tuple[str, Point, dict]]:
    out = []
    for feat in fc.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"]
        props = feat.get("properties") or {}
        out.append((str(props.get("id")), Point(float(lon), float(lat)), props))
    return out
