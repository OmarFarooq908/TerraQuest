#!/usr/bin/env python3
"""Offline validation for a Region Pack directory or fixture."""

from __future__ import annotations

import argparse
import json
import sys

from adventure_gis import verify_pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", help="Pack id or fixtures/... path")
    parser.add_argument(
        "--allow-legacy-seeds",
        action="store_true",
        help="Allow deprecated seeds.geojson alongside or instead of catalog.geojson",
    )
    args = parser.parse_args()
    report = verify_pack(args.pack, allow_legacy_seeds=args.allow_legacy_seeds)
    if not report["ok"]:
        print("FAIL", args.pack, file=sys.stderr)
        for e in report["errors"]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    # Stable CI-facing success payload (subset of verify_pack report).
    print(
        json.dumps(
            {
                "ok": True,
                "pack_id": report["pack_id"],
                "catalog_count": report["catalog_count"],
                "schema": report["schema"],
                "dir": report["dir"],
                "fingerprint": report["fingerprint"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
