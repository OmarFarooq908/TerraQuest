"""Download Copernicus GLO-30 DEM tiles from AWS Open Data and sample elevations."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

try:
    import rasterio
    from rasterio.windows import from_bounds
except ImportError:  # pragma: no cover
    rasterio = None  # type: ignore


def _tile_name(lat_floor: int, lon_floor: int) -> str:
    """Copernicus GLO-30 AWS COG folder/file naming."""
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def dem_tile_urls(bbox: list[float]) -> list[tuple[str, str]]:
    """Return (tile_id, https_url) covering the bbox."""
    west, south, east, north = bbox
    lat0 = math.floor(south)
    lat1 = math.floor(north)
    lon0 = math.floor(west)
    lon1 = math.floor(east)
    urls: list[tuple[str, str]] = []
    for lat in range(lat0, lat1 + 1):
        for lon in range(lon0, lon1 + 1):
            name = _tile_name(lat, lon)
            # AWS Open Data public bucket
            url = f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"
            urls.append((name, url))
    return urls


def download_dem_tiles(
    bbox: list[float],
    dest_dir: Path,
    *,
    timeout_s: float = 300.0,
) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        for name, url in dem_tile_urls(bbox):
            out = dest_dir / f"{name}.tif"
            if out.exists() and out.stat().st_size > 1000:
                paths.append(out)
                continue
            resp = client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"DEM download failed for {name}: HTTP {resp.status_code} ({url})"
                )
            out.write_bytes(resp.content)
            paths.append(out)
    return paths


def sample_elevations(
    points: list[tuple[float, float]],
    dem_paths: list[Path],
) -> list[float | None]:
    """Sample elevation (meters) at lon/lat points from local DEM GeoTIFFs."""
    if rasterio is None:
        raise RuntimeError("rasterio is required for DEM sampling")
    if not dem_paths:
        return [None] * len(points)

    datasets = [rasterio.open(p) for p in dem_paths]
    try:
        results: list[float | None] = []
        for lon, lat in points:
            val: float | None = None
            for ds in datasets:
                if (
                    ds.bounds.left <= lon <= ds.bounds.right
                    and ds.bounds.bottom <= lat <= ds.bounds.top
                ):
                    row, col = ds.index(lon, lat)
                    if 0 <= row < ds.height and 0 <= col < ds.width:
                        v = ds.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
                        # Copernicus nodata often 0 or very negative
                        if v is not None and float(v) > -1000:
                            val = float(v)
                            break
            results.append(val)
        return results
    finally:
        for ds in datasets:
            ds.close()


def local_relief_from_dem(
    lon: float,
    lat: float,
    dem_paths: list[Path],
    *,
    radius_deg: float = 0.03,
) -> float:
    """Rough local relief: max-min elevation in a small window around the point."""
    if rasterio is None:
        return 0.0
    for path in dem_paths:
        with rasterio.open(path) as ds:
            if not (
                ds.bounds.left <= lon <= ds.bounds.right
                and ds.bounds.bottom <= lat <= ds.bounds.top
            ):
                continue
            window = from_bounds(
                lon - radius_deg,
                lat - radius_deg,
                lon + radius_deg,
                lat + radius_deg,
                transform=ds.transform,
            )
            data = ds.read(1, window=window, boundless=True, fill_value=np.nan)
            data = data.astype("float64")
            data[data < -1000] = np.nan
            if np.all(np.isnan(data)):
                return 0.0
            return float(np.nanmax(data) - np.nanmin(data))
    return 0.0


def dem_source_meta(paths: list[Path]) -> dict:
    return {
        "kind": "dem",
        "provider": "Copernicus GLO-30 (AWS Open Data)",
        "license": "Copernicus DEM license — see https://spacedata.copernicus.eu/",
        "attribution": "© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "tiles": [p.name for p in paths],
    }
