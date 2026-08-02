#!/usr/bin/env python3
"""Enforce per-module coverage floors from configs/coverage_gates.yaml (issue #16)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adventure_core.config import repo_root
from adventure_core.coverage_gates import check_coverage, load_gates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage-json",
        type=Path,
        default=Path("coverage.json"),
        help="coverage.py JSON report (default: ./coverage.json)",
    )
    parser.add_argument(
        "--gates",
        type=Path,
        default=None,
        help="YAML gates file (default: configs/coverage_gates.yaml)",
    )
    args = parser.parse_args()
    gates = args.gates or (repo_root() / "configs" / "coverage_gates.yaml")
    if not args.coverage_json.exists():
        print(f"FAIL missing {args.coverage_json}", file=sys.stderr)
        return 1
    if not gates.exists():
        print(f"FAIL missing {gates}", file=sys.stderr)
        return 1

    errors = check_coverage(args.coverage_json, gates)
    if errors:
        print("FAIL coverage gates", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    global_floor, modules = load_gates(gates)
    blob = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "ok": True,
                "global": round(blob["totals"]["percent_covered"], 2),
                "global_floor": global_floor,
                "modules_checked": len(modules),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
