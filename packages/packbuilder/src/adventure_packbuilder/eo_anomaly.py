"""EO texture-anomaly scout + verified GeoJSON loader (RFC-0010).

Standalone feeder: scan a local GeoTIFF for high-contrast texture edges,
export triage candidates (verified=false), then import only human-verified
points at pack build. This is not archaeological detection.
"""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

SCOUT_VERSION = "eo_texture_anomaly_v1"
GPX_NS = "http://www.topografix.com/GPX/1/1"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
GPX_SCHEMA_LOC = "http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd"
GPX_CREATOR = "TerraQuest eo_anomaly_scout"


class EoAnomalyError(RuntimeError):
    """Misconfigured scout input or invalid verified GeoJSON."""


def _as_enabled(cfg: dict[str, Any] | None) -> bool:
    if not cfg:
        return False
    return bool(cfg.get("enabled"))


def _sobel_magnitude(arr: np.ndarray) -> np.ndarray:
    """Simple central-difference edge magnitude (no scipy)."""
    a = np.asarray(arr, dtype=np.float64)
    dx = np.zeros_like(a)
    dy = np.zeros_like(a)
    dx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    dy[1:-1, :] = a[2:, :] - a[:-2, :]
    return np.hypot(dx, dy)


def _label_binary(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4/8-connected component labels; returns (labels, count)."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            current += 1
            stack = [(y, x)]
            labels[y, x] = current
            while stack:
                cy, cx = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dy == 0 and dx == 0:
                            continue
                        ny, nx = cy + dy, cx + dx
                        if (
                            0 <= ny < h
                            and 0 <= nx < w
                            and mask[ny, nx]
                            and labels[ny, nx] == 0
                        ):
                            labels[ny, nx] = current
                            stack.append((ny, nx))
    return labels, current


def _pixel_to_lonlat(
    transform: Any,
    row: float,
    col: float,
    *,
    src_crs: Any,
) -> tuple[float, float]:
    from rasterio.transform import xy
    from rasterio.warp import transform as rio_transform

    xs, ys = xy(transform, row, col, offset="center")
    if src_crs is None:
        return float(xs), float(ys)
    # Already geographic
    if getattr(src_crs, "is_geographic", False):
        return float(xs), float(ys)
    lons, lats = rio_transform(src_crs, "EPSG:4326", [xs], [ys])
    return float(lons[0]), float(lats[0])


def scout_texture_anomalies(
    raster_path: str | Path,
    *,
    nir_band: int = 1,
    swir_band: int | None = 2,
    edge_threshold: float = 0.25,
    min_pixels: int = 3,
    max_pixels: int = 100,
    index_name: str = "ndmi",
    single_band: bool = False,
) -> list[dict[str, Any]]:
    """Scan a local GeoTIFF for compact high-contrast texture clusters.

    Returns candidate dicts (not yet catalog features). All have
    ``verified=False``. Bands are 1-indexed (rasterio convention).
    """
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover
        raise EoAnomalyError("rasterio is required for EO anomaly scout") from exc

    path = Path(raster_path)
    if not path.is_file():
        raise EoAnomalyError(f"raster not found: {path}")

    if nir_band < 1:
        raise EoAnomalyError("nir_band must be >= 1")
    if not single_band and (swir_band is None or swir_band < 1):
        raise EoAnomalyError("swir_band must be >= 1 unless single_band=True")
    if not (0.0 < edge_threshold <= 1.0):
        raise EoAnomalyError("edge_threshold must be in (0, 1]")
    if min_pixels < 1 or max_pixels < min_pixels:
        raise EoAnomalyError("require 1 <= min_pixels <= max_pixels")

    with rasterio.open(path) as ds:
        if ds.count < nir_band:
            raise EoAnomalyError(f"raster has {ds.count} bands; nir_band={nir_band} missing")
        # Allocate plain arrays so we do not mutate rasterio/NumPy 2.5 views.
        nir = np.empty((ds.height, ds.width), dtype=np.float64)
        nir[:] = ds.read(nir_band)
        if single_band or swir_band is None:
            index = nir
            used_index = "single_band" if index_name == "ndmi" else index_name
        else:
            if ds.count < swir_band:
                raise EoAnomalyError(
                    f"raster has {ds.count} bands; swir_band={swir_band} missing"
                )
            swir = np.empty((ds.height, ds.width), dtype=np.float64)
            swir[:] = ds.read(swir_band)
            index = (nir - swir) / (nir + swir + 1e-10)
            used_index = index_name
        transform = ds.transform
        crs = ds.crs

    edge = _sobel_magnitude(index)
    finite = np.isfinite(edge)
    if not finite.any():
        return []
    peak = float(np.nanmax(edge))
    if peak <= 0.0:
        return []
    binary = finite & (edge > peak * edge_threshold)
    labels, n_features = _label_binary(binary)

    candidates: list[dict[str, Any]] = []
    for i in range(1, n_features + 1):
        ys, xs = np.where(labels == i)
        size_pixels = int(ys.size)
        if size_pixels < min_pixels or size_pixels > max_pixels:
            continue
        y_pix = float(ys.mean())
        x_pix = float(xs.mean())
        lon, lat = _pixel_to_lonlat(transform, y_pix, x_pix, src_crs=crs)
        if not (math.isfinite(lon) and math.isfinite(lat)):
            continue
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            continue
        iy, ix = int(round(y_pix)), int(round(x_pix))
        iy = min(max(iy, 0), edge.shape[0] - 1)
        ix = min(max(ix, 0), edge.shape[1] - 1)
        intensity = float(edge[iy, ix])
        cid = f"EO_SCOUT_{len(candidates):03d}"
        candidates.append(
            {
                "id": cid,
                "type": "texture_anomaly",
                "coordinates": [round(lon, 6), round(lat, 6)],
                "verified": False,
                "metrics": {
                    "pixel_size": size_pixels,
                    "edge_intensity": intensity,
                },
                "index_name": used_index,
                "scout_version": SCOUT_VERSION,
                "raster": path.name,
            }
        )
    return candidates


def candidates_to_geojson(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Serialize scout candidates to a Point FeatureCollection."""
    features: list[dict[str, Any]] = []
    for c in candidates:
        lon, lat = c["coordinates"]
        metrics = c.get("metrics") or {}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": c["id"],
                    "type": c.get("type", "texture_anomaly"),
                    "verified": bool(c.get("verified", False)),
                    "pixel_size": int(metrics.get("pixel_size", 0)),
                    "edge_intensity": float(metrics.get("edge_intensity", 0.0)),
                    "index_name": c.get("index_name", "ndmi"),
                    "scout_version": c.get("scout_version", SCOUT_VERSION),
                    "raster": c.get("raster"),
                    "note": (
                        "Texture/edge anomaly for human triage — not a confirmed landmark."
                    ),
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "scout_version": SCOUT_VERSION,
            "disclaimer": (
                "High-contrast texture clusters only. Verify in Google Earth / field "
                "before setting verified=true for pack import (RFC-0010)."
            ),
        },
    }


def write_scout_geojson(path: str | Path, candidates: list[dict[str, Any]]) -> Path:
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(candidates_to_geojson(candidates), indent=2) + "\n",
        encoding="utf-8",
    )
    return out


def _xml_safe(text: str) -> str:
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 0x20)


def _el(tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    elem = ET.Element(tag, {k: v for k, v in attrs.items() if v is not None})
    if text is not None:
        elem.text = _xml_safe(text)
    return elem


def candidates_to_gpx(candidates: list[dict[str, Any]], *, creator: str = GPX_CREATOR) -> str:
    """Serialize scout candidates as GPX 1.1 waypoints (triage / Google Earth)."""
    ET.register_namespace("", GPX_NS)
    ET.register_namespace("xsi", XSI_NS)
    root = ET.Element(
        f"{{{GPX_NS}}}gpx",
        {
            "version": "1.1",
            "creator": creator,
            f"{{{XSI_NS}}}schemaLocation": GPX_SCHEMA_LOC,
        },
    )
    meta = _el(f"{{{GPX_NS}}}metadata")
    meta.append(_el(f"{{{GPX_NS}}}name", "TerraQuest EO texture anomaly scout"))
    meta.append(
        _el(
            f"{{{GPX_NS}}}desc",
            "Unverified texture/edge anomalies for triage. Not archaeological claims.",
        )
    )
    root.append(meta)
    for c in candidates:
        lon, lat = c["coordinates"]
        metrics = c.get("metrics") or {}
        wpt = _el(f"{{{GPX_NS}}}wpt", lat=f"{lat:.7f}", lon=f"{lon:.7f}")
        wpt.append(_el(f"{{{GPX_NS}}}name", str(c["id"])))
        wpt.append(_el(f"{{{GPX_NS}}}type", "eo_texture_anomaly"))
        wpt.append(
            _el(
                f"{{{GPX_NS}}}desc",
                f"pixel_size={metrics.get('pixel_size')}; "
                f"edge_intensity={metrics.get('edge_intensity')}; "
                f"verified={c.get('verified', False)}",
            )
        )
        root.append(wpt)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"


def write_scout_gpx(path: str | Path, candidates: list[dict[str, Any]]) -> Path:
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(candidates_to_gpx(candidates), encoding="utf-8")
    return out


def load_verified_scout_features(
    geojson_path: str | Path,
    *,
    bbox: list[float] | None = None,
    require_verified: bool = True,
) -> list[dict[str, Any]]:
    """Load Point features for pack import; optionally require verified=true."""
    path = Path(geojson_path)
    if not path.is_file():
        raise EoAnomalyError(f"eo_scout candidates_geojson not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EoAnomalyError(f"invalid JSON in {path}: {exc}") from exc
    if raw.get("type") != "FeatureCollection":
        raise EoAnomalyError("eo_scout GeoJSON must be a FeatureCollection")
    features = raw.get("features")
    if not isinstance(features, list):
        raise EoAnomalyError("eo_scout FeatureCollection missing features[]")

    west = south = east = north = None
    if bbox is not None:
        if len(bbox) != 4:
            raise EoAnomalyError("bbox must be [west, south, east, north]")
        west, south, east, north = (float(x) for x in bbox)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            raise EoAnomalyError(f"eo_scout features[{i}] must be an object")
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            raise EoAnomalyError(f"eo_scout features[{i}] must be Point geometry")
        coords = geom.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            raise EoAnomalyError(f"eo_scout features[{i}] coordinates must be [lon, lat]")
        try:
            lon = float(coords[0])
            lat = float(coords[1])
        except (TypeError, ValueError) as exc:
            raise EoAnomalyError(
                f"eo_scout features[{i}] coordinates must be numeric"
            ) from exc
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise EoAnomalyError(f"eo_scout features[{i}] coordinates must be finite")
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise EoAnomalyError(f"eo_scout features[{i}] lon/lat out of WGS84 range")
        props = dict(feat.get("properties") or {})
        if require_verified and props.get("verified") is not True:
            continue
        if west is not None and not (west <= lon <= east and south <= lat <= north):
            continue
        fid = str(props.get("id") or f"eo_scout_{i}").strip()
        if not fid:
            raise EoAnomalyError(f"eo_scout features[{i}] missing properties.id")
        if fid in seen:
            raise EoAnomalyError(f"eo_scout duplicate id {fid!r}")
        seen.add(fid)
        props["id"] = fid
        out.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    return out


def resolve_eo_scout_features(
    eo_scout_cfg: dict[str, Any] | None,
    *,
    bbox: list[float],
    repo: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return (features, source_meta) when enabled; else ([], None).

    ``source_meta`` is suitable for PackSource.extra when features are loaded.
    """
    cfg = eo_scout_cfg or {}
    if not _as_enabled(cfg):
        return [], None
    rel = cfg.get("candidates_geojson")
    if not rel:
        raise EoAnomalyError(
            "eo_scout.enabled requires candidates_geojson path to a verified Point FC"
        )
    path = Path(str(rel))
    if not path.is_absolute():
        path = repo / path
    features = load_verified_scout_features(path, bbox=bbox, require_verified=True)
    meta = {
        "candidates_geojson": str(rel),
        "verified_count": len(features),
        "scout_version": SCOUT_VERSION,
    }
    return features, meta
