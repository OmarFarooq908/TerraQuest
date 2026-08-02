#!/usr/bin/env python3
"""Offline validation for a Region Pack directory or fixture."""

from __future__ import annotations

import argparse
import json
import sys

from adventure_core.catalog import CATALOG_SCHEMA_VERSION
from adventure_core.config import load_pack_manifest
from adventure_gis import load_pack_data

REQUIRED_PROPS = ("id", "name", "generator", "provenance", "evidence", "densify")


def validate_pack(pack_ref: str) -> list[str]:
    errors: list[str] = []
    manifest, pack_dir = load_pack_manifest(pack_ref)
    catalog_path = pack_dir / "layers" / "catalog.geojson"
    if not catalog_path.exists():
        errors.append(f"missing {catalog_path}")
        return errors

    data = load_pack_data(pack_dir)
    if not data.catalog:
        errors.append("catalog is empty")
    for cand in data.catalog:
        props = cand.properties
        for key in REQUIRED_PROPS:
            if key not in props:
                errors.append(f"{cand.id}: missing property {key}")
                break
        schema = str(props.get("catalog_schema_version", ""))
        if schema and schema != CATALOG_SCHEMA_VERSION:
            errors.append(f"{cand.id}: catalog_schema_version {schema} != {CATALOG_SCHEMA_VERSION}")
    if manifest.feature_schema_version != CATALOG_SCHEMA_VERSION and not manifest.synthetic:
        errors.append(
            f"manifest feature_schema_version={manifest.feature_schema_version} "
            f"expected {CATALOG_SCHEMA_VERSION}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", help="Pack id or fixtures/... path")
    args = parser.parse_args()
    errors = validate_pack(args.pack)
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
