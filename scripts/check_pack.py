#!/usr/bin/env python3
"""Offline validation for a Region Pack directory or fixture."""

from __future__ import annotations

import argparse
import json
import sys

from adventure_core.catalog import CATALOG_SCHEMA_VERSION
from adventure_core.config import load_pack_manifest
from adventure_gis import load_pack_data
from adventure_gis.pack_validate import validate_pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", help="Pack id or fixtures/... path")
    parser.add_argument(
        "--allow-legacy-seeds",
        action="store_true",
        help="Allow deprecated seeds.geojson alongside or instead of catalog.geojson",
    )
    args = parser.parse_args()
    errors = validate_pack(args.pack, allow_legacy_seeds=args.allow_legacy_seeds)
    if errors:
        print("FAIL", args.pack, file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    manifest, pack_dir = load_pack_manifest(args.pack)
    data = load_pack_data(pack_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "pack_id": manifest.pack_id,
                "catalog_count": len(data.catalog),
                "schema": CATALOG_SCHEMA_VERSION,
                "dir": str(pack_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
