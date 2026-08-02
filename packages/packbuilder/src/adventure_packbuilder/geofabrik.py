"""Geofabrik PBF → clipped extract → GeoJSON layers via osmium-tool."""

from __future__ import annotations

import hashlib
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

_LATEST_URL_MARKERS = ("-latest.osm.pbf", "-latest.osm.bz2", "/latest/")


def is_latest_geofabrik_url(url: str) -> bool:
    """True when the URL looks like a moving Geofabrik ``*-latest*`` extract."""
    lower = url.strip().lower()
    return any(m in lower for m in _LATEST_URL_MARKERS)


def assert_geofabrik_url_allowed(url: str, *, allow_latest: bool) -> None:
    """Fail closed when production configs forbid moving ``latest`` extracts."""
    if allow_latest:
        return
    if is_latest_geofabrik_url(url):
        raise ValueError(
            f"osm.allow_latest is false but geofabrik_url looks like a moving extract: {url!r}. "
            "Pin a dated file such as "
            "https://download.geofabrik.de/asia/pakistan-260801.osm.pbf "
            "(see docs/pack-builder.md)."
        )


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_geofabrik_md5_text(text: str) -> str:
    """Parse Geofabrik ``*.osm.pbf.md5`` contents → lowercase hex digest."""
    token = text.strip().split()[0] if text.strip() else ""
    digest = token.lower()
    if len(digest) != 32 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"invalid Geofabrik md5 text: {text!r}")
    return digest


def verify_pbf_checksums(
    path: Path,
    *,
    expected_md5: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, str]:
    """Verify optional MD5 / SHA-256 pins; return computed digests that were checked."""
    if not path.is_file():
        raise FileNotFoundError(path)
    out: dict[str, str] = {}
    if expected_md5:
        want = expected_md5.strip().lower().split()[0]
        got = file_md5(path)
        out["md5"] = got
        if got != want:
            raise ValueError(f"PBF md5 mismatch for {path.name}: expected {want}, got {got}")
    if expected_sha256:
        want = expected_sha256.strip().lower().split()[0]
        got = file_sha256(path)
        out["sha256"] = got
        if got != want:
            raise ValueError(f"PBF sha256 mismatch for {path.name}: expected {want}, got {got}")
    return out


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


def download_pbf(
    url: str,
    dest: Path,
    *,
    timeout_s: float = 600.0,
    expected_md5: str | None = None,
    expected_sha256: str | None = None,
    allow_latest: bool = True,
    force: bool = False,
) -> Path:
    """Download a regional PBF (or reuse cache) and optionally verify checksums."""
    assert_geofabrik_url_allowed(url, allow_latest=allow_latest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _verify() -> None:
        verify_pbf_checksums(dest, expected_md5=expected_md5, expected_sha256=expected_sha256)

    if dest.exists() and dest.stat().st_size > 1_000_000 and not force:
        try:
            _verify()
            return dest
        except ValueError:
            # Stale cache from a previous latest/dated file — replace.
            dest.unlink(missing_ok=True)

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
    _verify()
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
    expected_md5: str | None = None,
    expected_sha256: str | None = None,
    allow_latest: bool = True,
) -> tuple[dict[str, Any], dict[str, Path]]:
    """Download/clip/filter/export → layer FeatureCollections + artifact paths."""
    work_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_pbf or (work_dir / "region.osm.pbf")
    region = download_pbf(
        pbf_url,
        cache,
        expected_md5=expected_md5,
        expected_sha256=expected_sha256,
        allow_latest=allow_latest,
    )
    extract = work_dir / "bbox.osm.pbf"
    filtered = work_dir / "filtered.osm.pbf"
    exported = work_dir / "filtered.geojson"

    extract_bbox(region, bbox, extract)
    filter_features(extract, filtered)
    export_geojson(filtered, exported)

    fc = json.loads(exported.read_text(encoding="utf-8"))
    layers = geojson_to_layers(fc)
    pin_meta = {
        "geofabrik_url": pbf_url,
        "allow_latest": allow_latest,
        "cache_pbf": str(region),
        "is_latest_url": is_latest_geofabrik_url(pbf_url),
    }
    if expected_md5:
        pin_meta["geofabrik_md5"] = expected_md5.strip().lower().split()[0]
        pin_meta["md5"] = file_md5(region)
    if expected_sha256:
        pin_meta["geofabrik_sha256"] = expected_sha256.strip().lower().split()[0]
        pin_meta["sha256"] = file_sha256(region)
    layers.setdefault("meta", {})
    layers["meta"]["geofabrik_pin"] = pin_meta
    artifacts = {
        "region_pbf": region,
        "extract_pbf": extract,
        "filtered_pbf": filtered,
        "exported_geojson": exported,
    }
    return layers, artifacts
