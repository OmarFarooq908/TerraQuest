#!/usr/bin/env python3
"""Offline EO texture-anomaly scout (RFC-0010).

Scans a local GeoTIFF for compact high-contrast texture clusters and writes
GeoJSON (+ optional GPX) for human triage. Does **not** invent catalog candidates
at mission time — set verified=true after Google Earth / field checks, then
point pack ``eo_scout.candidates_geojson`` at the verified file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raster", required=True, type=Path, help="Local GeoTIFF path")
    parser.add_argument(
        "--out-geojson",
        required=True,
        type=Path,
        help="Output Point FeatureCollection (verified=false)",
    )
    parser.add_argument(
        "--out-gpx",
        type=Path,
        default=None,
        help="Optional GPX waypoints for Google Earth triage",
    )
    parser.add_argument("--nir-band", type=int, default=1, help="1-indexed NIR band")
    parser.add_argument(
        "--swir-band",
        type=int,
        default=2,
        help="1-indexed SWIR band (ignored with --single-band)",
    )
    parser.add_argument(
        "--single-band",
        action="store_true",
        help="Use nir-band alone (no NDMI); for mono test rasters",
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=0.25,
        help="Fraction of max edge magnitude (0-1]",
    )
    parser.add_argument("--min-pixels", type=int, default=3)
    parser.add_argument("--max-pixels", type=int, default=100)
    parser.add_argument(
        "--index-name",
        default="ndmi",
        help="Recorded index_name (default ndmi)",
    )
    args = parser.parse_args(argv)

    from adventure_packbuilder.eo_anomaly import (
        EoAnomalyError,
        scout_texture_anomalies,
        write_scout_geojson,
        write_scout_gpx,
    )

    try:
        candidates = scout_texture_anomalies(
            args.raster,
            nir_band=args.nir_band,
            swir_band=None if args.single_band else args.swir_band,
            edge_threshold=args.edge_threshold,
            min_pixels=args.min_pixels,
            max_pixels=args.max_pixels,
            index_name=args.index_name,
            single_band=args.single_band,
        )
    except EoAnomalyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    geo_path = write_scout_geojson(args.out_geojson, candidates)
    print(f"wrote {len(candidates)} unverified candidates → {geo_path}")
    if args.out_gpx is not None:
        gpx_path = write_scout_gpx(args.out_gpx, candidates)
        print(f"wrote GPX → {gpx_path}")
    print(
        "Next: triage in Google Earth, set properties.verified=true on keepers, "
        "point pack eo_scout.candidates_geojson at the verified GeoJSON, rebuild pack."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
