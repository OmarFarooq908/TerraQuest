#!/usr/bin/env python3
"""Offline discovery-quality metrics (RFC-0002).

Runs the normal mission pipeline, then scores ranked results against place labels.
Does not invent candidates or call cloud APIs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from adventure_cli.pipeline import run_mission
from adventure_core.config import repo_root
from adventure_core.evaluation import (
    RankedRef,
    compute_discovery_metrics,
    load_place_labels,
    metrics_as_dict,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack", default="fixtures/karakoram_mini")
    p.add_argument(
        "--labels",
        type=Path,
        default=repo_root() / "evaluation" / "fixtures" / "karakoram_mini",
        help="Place-label JSON file or directory",
    )
    p.add_argument(
        "-p",
        "--prompt",
        default=(
            "Three days, Suzuki Swift, rivers and forests, hate crowds. "
            "Find a Fearless & Far style adventure."
        ),
    )
    p.add_argument("--mode", default="fearless_far")
    p.add_argument("--interpreter", default="rules", choices=["rules", "ollama", "auto"])
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--match-radius-km", type=float, default=2.0)
    p.add_argument("--popularity-threshold", type=float, default=7.0)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument("--json", action="store_true", help="Print metrics JSON only")
    args = p.parse_args(argv)

    labels = load_place_labels(args.labels)
    result = run_mission(
        pack=args.pack,
        mode=args.mode,
        prompt=args.prompt,
        max_results=max(args.max_results, args.k),
        interpreter=args.interpreter,
    )
    ranked = [
        RankedRef(
            candidate_id=m.candidate_id,
            score=m.score,
            lon=m.lon,
            lat=m.lat,
        )
        for m in result.missions
    ]
    metrics = compute_discovery_metrics(
        ranked,
        labels,
        k=args.k,
        match_radius_km=args.match_radius_km,
        popularity_threshold=args.popularity_threshold,
    )
    payload = {
        "pack_id": result.pack_id,
        "mode": result.mode,
        "interpreter": result.request.intent.source,
        "prompt": args.prompt,
        "ranked_candidate_ids": [m.candidate_id for m in result.missions[: args.k]],
        "metrics": metrics_as_dict(metrics),
        "notes": result.notes,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        m = metrics
        print(f"pack={result.pack_id} interpreter={result.request.intent.source} k={m.k}")
        print(f"labels={m.n_labels} interesting={m.n_interesting} matched={m.n_matched}")
        print(f"recall_at_k={m.recall_at_k}")
        print(f"precision_at_k={m.precision_at_k}")
        print(f"popularity_trap_at_k={m.popularity_trap_at_k}")
        print(f"rating_spearman={m.rating_spearman}")
        print("top:", ", ".join(payload["ranked_candidate_ids"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
