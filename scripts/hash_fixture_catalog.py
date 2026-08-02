#!/usr/bin/env python3
"""Compute / check SHA256 of fixtures/karakoram_mini catalog for CI drift."""

from __future__ import annotations

import argparse
import hashlib
import sys

from adventure_core.config import repo_root


def catalog_hash() -> str:
    root = repo_root()
    path = root / "fixtures" / "karakoram_mini" / "layers" / "catalog.geojson"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if hash != catalog.sha256")
    parser.add_argument("--write", action="store_true", help="Write fixtures/.../catalog.sha256")
    args = parser.parse_args()
    digest = catalog_hash()
    root = repo_root()
    expected_path = root / "fixtures" / "karakoram_mini" / "catalog.sha256"

    if args.write:
        expected_path.write_text(digest + "\n", encoding="utf-8")
        print(f"wrote {expected_path}: {digest}")
        return 0

    if args.check:
        if not expected_path.exists():
            print(f"missing {expected_path}; run with --write", file=sys.stderr)
            return 1
        expected = expected_path.read_text(encoding="utf-8").strip().split()[0]
        if digest != expected:
            print(f"hash drift: got {digest} expected {expected}", file=sys.stderr)
            return 1
        print(f"ok {digest}")
        return 0

    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
