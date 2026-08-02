"""Geofabrik PBF → clipped extract → GeoJSON layers via osmium-tool."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from adventure_packbuilder.osm import _fc, _point_feature

USER_AGENT = (
    "TerraQuest/0.2 (packbuilder; local-first; +https://github.com/OmarFarooq908/TerraQuest)"
)


def require_osmium() -> str:
    path = shutil.which("osmium")
    if not path:
        raise RuntimeError(
            "osmium-tool not found on PATH (needed for production pack builds). "
            "Install it, then retry: brew install osmium-tool  # macOS; "
            "see https://osmcode.org/osmium-tool/ for Linux packages. "
            "For offline CI, use a fixture pack: "
            "adventurectl mission run --pack fixtures/karakoram_mini ..."
        )
    return path


def download_pbf(url: str, dest: Path, *, timeout_s: float = 600.0) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    partial = dest.with_suffix(dest.suffix + ".partial")
    with (
        httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client,
        client.stream("GET", url) as resp,
    ):
        resp.raise_for_status()
        with partial.open("wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)
    partial.replace(dest)
    return dest


def extract_bbox(pbf: Path, bbox: list[float], out_pbf: Path) -> Path:
    """Clip regional PBF to pack bbox with osmium extract."""
    osmium = require_osmium()
    out_pbf.parent.mkdir(parents=True, exist_ok=True)
    west, south, east, north = bbox
    bbox_arg = f"{west},{south},{east},{north}"
    cmd = [
        osmium,
        "extract",
        "-b",
        bbox_arg,
        "-o",
        str(out_pbf),
        "--overwrite",
        str(pbf),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_pbf


def filter_features(extract_pbf: Path, filtered_pbf: Path) -> Path:
    """Keep only place/water/road/peak/viewpoint objects needed for seeds."""
    osmium = require_osmium()
    expressions = [
        "n/place=city,town,village,hamlet,isolated_dwelling",
        "n/natural=peak",
        "n/tourism=viewpoint",
        "wr/natural=water",
        "w/water=lake,reservoir,pond",
        "w/waterway=river,stream",
        "w/highway=primary,secondary,tertiary,trunk,track,path,unclassified,residential",
    ]
    cmd = [
        osmium,
        "tags-filter",
        str(extract_pbf),
        *expressions,
        "-o",
        str(filtered_pbf),
        "--overwrite",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return filtered_pbf


def export_geojson(filtered_pbf: Path, out_geojson: Path) -> Path:
    osmium = require_osmium()
    cmd = [
        osmium,
        "export",
        "-f",
        "geojson",
        "-u",
        "type_id",
        "-a",
        "type,id",
        "-o",
        str(out_geojson),
        "--overwrite",
        str(filtered_pbf),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_geojson


def _centroid(geom: dict[str, Any]) -> tuple[float, float] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not gtype or coords is None:
        return None
    if gtype == "Point":
        return float(coords[0]), float(coords[1])
    if gtype == "LineString":
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    if gtype == "MultiLineString":
        pts = [c for line in coords for c in line]
        xs = [c[0] for c in pts]
        ys = [c[1] for c in pts]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    if gtype == "Polygon":
        ring = coords[0]
        xs = [c[0] for c in ring]
        ys = [c[1] for c in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    if gtype == "MultiPolygon":
        ring = coords[0][0]
        xs = [c[0] for c in ring]
        ys = [c[1] for c in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    return None


def _osm_identity(props: dict[str, Any]) -> tuple[str, int]:
    """Parse osmium export id fields → (type, id)."""
    raw_id = props.get("@id") or props.get("id") or props.get("osm_id") or 0
    osm_type = str(props.get("@type") or props.get("type") or "node")
    if isinstance(raw_id, str) and "/" in raw_id:
        # type_id unique id: "way/12345"
        osm_type, raw_id = raw_id.split("/", 1)
    try:
        osm_id = int(raw_id)
    except (TypeError, ValueError):
        osm_id = 0
    return osm_type, osm_id


def _line_coords(geom: dict[str, Any]) -> list[list[float]] | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "LineString" and coords and len(coords) >= 2:
        return coords
    if gtype == "MultiLineString" and coords:
        # longest segment as primary geometry
        best = max(coords, key=len)
        if len(best) >= 2:
            return best
    return None


def geojson_to_layers(fc: dict[str, Any]) -> dict[str, Any]:
    settlements: list[dict] = []
    peaks: list[dict] = []
    viewpoints: list[dict] = []
    water: list[dict] = []
    water_geoms: list[dict] = []
    road_nodes: list[dict] = []
    road_lines: list[dict] = []

    for feat in fc.get("features", []):
        geom = feat.get("geometry") or {}
        props_in = feat.get("properties") or {}
        pt = _centroid(geom)
        if not pt:
            continue
        lon, lat = pt
        osm_type, osm_id = _osm_identity(props_in)
        # Drop osmium meta keys from tag copy
        tags = {
            k: v
            for k, v in props_in.items()
            if not k.startswith("@") and k not in {"id", "type", "osm_id", "osm_type"}
        }
        feat_pt = _point_feature(osm_type, osm_id, lon, lat, tags)
        props = feat_pt["properties"]

        place = tags.get("place")
        if place in {"city", "town", "village", "hamlet", "isolated_dwelling"}:
            props["kind"] = "settlement"
            if str(props["name"]).startswith("unnamed_"):
                props["name"] = f"unnamed_settlement_{osm_id}"
            settlements.append(feat_pt)
            continue

        if tags.get("natural") == "peak":
            props["kind"] = "peak"
            if str(props["name"]).startswith("unnamed_"):
                props["name"] = f"unnamed_peak_{osm_id}"
            if tags.get("ele"):
                try:
                    props["elevation_m"] = float(str(tags["ele"]).replace("m", ""))
                except ValueError:
                    pass
            peaks.append(feat_pt)
            continue

        if tags.get("tourism") == "viewpoint":
            props["kind"] = "viewpoint"
            if str(props["name"]).startswith("unnamed_"):
                props["name"] = f"unnamed_viewpoint_{osm_id}"
            viewpoints.append(feat_pt)
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
            props["kind"] = kind
            props["has_water"] = True
            if str(props["name"]).startswith("unnamed_"):
                props["name"] = f"unnamed_{kind}_{osm_id}"
            water.append(feat_pt)
            water_geoms.append(
                {
                    "type": "Feature",
                    "geometry": geom,
                    "properties": dict(props),
                }
            )
            continue

        highway = tags.get("highway")
        if highway:
            props["kind"] = "road"
            props["highway"] = highway
            if str(props["name"]).startswith("unnamed_"):
                props["name"] = f"unnamed_{highway}_{osm_id}"
            road_nodes.append(feat_pt)
            line = _line_coords(geom)
            if line:
                road_lines.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": line},
                        "properties": dict(props),
                    }
                )

    return {
        "settlements": _fc(settlements),
        "peaks": _fc(peaks),
        "viewpoints": _fc(viewpoints),
        "water": _fc(water),
        "water_geoms": _fc(water_geoms),
        "road_nodes": _fc(road_nodes),
        "road_lines": _fc(road_lines),
        "meta": {
            "retrieved_at": datetime.now(UTC).isoformat(),
            "method": "geofabrik+osmium",
            "element_count": len(fc.get("features", [])),
            "settlement_count": len(settlements),
            "water_count": len(water),
            "road_count": len(road_nodes),
            "road_line_count": len(road_lines),
            "peak_count": len(peaks),
            "viewpoint_count": len(viewpoints),
        },
    }


def fetch_geofabrik_layers(
    bbox: list[float],
    work_dir: Path,
    *,
    pbf_url: str = "https://download.geofabrik.de/asia/pakistan-latest.osm.pbf",
    cache_pbf: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    """Download/clip/filter/export → layer FeatureCollections + artifact paths."""
    work_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_pbf or (work_dir / "region.osm.pbf")
    region = download_pbf(pbf_url, cache)
    extract = work_dir / "bbox.osm.pbf"
    filtered = work_dir / "filtered.osm.pbf"
    exported = work_dir / "filtered.geojson"

    extract_bbox(region, bbox, extract)
    filter_features(extract, filtered)
    export_geojson(filtered, exported)

    fc = json.loads(exported.read_text(encoding="utf-8"))
    layers = geojson_to_layers(fc)
    artifacts = {
        "region_pbf": region,
        "extract_pbf": extract,
        "filtered_pbf": filtered,
        "exported_geojson": exported,
    }
    return layers, artifacts
