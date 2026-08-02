#!/usr/bin/env python3
"""Offline discovery-quality metrics + generator ablations (RFC-0002 / issue #24).

Runs the normal mission pipeline, then scores ranked results against place labels.
Does not invent candidates or call cloud APIs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from adventure_cli.pipeline import run_mission
from adventure_core.config import load_pack_manifest, repo_root
from adventure_core.evaluation import (
    RankedRef,
    compute_discovery_metrics,
    load_place_labels,
    metrics_as_dict,
)
from adventure_gis.pack_hash import pack_content_hash

DEFAULT_PROMPT = (
    "Three days, Suzuki Swift, rivers and forests, hate crowds. "
    "Find a Fearless & Far style adventure."
)

# Fixture-scale generator ablations for reproducible comparison reports.
FIXTURE_ABLATIONS: dict[str, dict[str, Any]] = {
    "all_generators": {"include_generators": None},
    "water_only": {
        "include_generators": ["named_waterbody", "unnamed_waterbody"],
    },
    "dem_terrain": {
        "include_generators": ["dem_local_max", "terrain_relief_hotspot", "isolation_maximum"],
    },
    "access_only": {
        "include_generators": ["track_terminus", "road_spur"],
    },
}


def _parse_csv(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    items = [p.strip() for p in raw.split(",") if p.strip()]
    return items or None


def pack_fingerprint(pack: str) -> str:
    """Content hash of pack layers (pins reports to catalog bytes)."""
    _, pack_dir = load_pack_manifest(pack)
    layers = pack_dir / "layers"
    stats_path = pack_dir / "build_stats.json"
    stats = None
    if stats_path.is_file():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    return pack_content_hash(layers, stats)


def run_eval(
    *,
    pack: str,
    labels_path: Path,
    prompt: str,
    mode: str,
    interpreter: str,
    k: int,
    match_radius_km: float,
    popularity_threshold: float,
    max_results: int,
    include_generators: list[str] | None = None,
    exclude_generators: list[str] | None = None,
    ablation_name: str | None = None,
) -> dict[str, Any]:
    labels = load_place_labels(labels_path)
    result = run_mission(
        pack=pack,
        mode=mode,
        prompt=prompt,
        max_results=max(max_results, k),
        interpreter=interpreter,
        include_generators=include_generators,
        exclude_generators=exclude_generators,
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
        k=k,
        match_radius_km=match_radius_km,
        popularity_threshold=popularity_threshold,
    )
    payload: dict[str, Any] = {
        "ablation": ablation_name or "custom",
        "pack_id": result.pack_id,
        "pack_content_hash": pack_fingerprint(pack),
        "mode": result.mode,
        "interpreter": result.request.intent.source,
        "prompt": prompt,
        "include_generators": include_generators,
        "exclude_generators": exclude_generators,
        "ranked_candidate_ids": [m.candidate_id for m in result.missions[:k]],
        "metrics": metrics_as_dict(metrics),
        "notes": result.notes,
    }
    return payload


def _fmt_metric(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.4f}"


def write_markdown_report(runs: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    first = runs[0]
    lines = [
        "# Discovery ranking comparison",
        "",
        f"- pack: `{first['pack_id']}`",
        f"- pack_content_hash: `{first['pack_content_hash']}`",
        f"- interpreter: `{first['interpreter']}`",
        f"- mode: `{first['mode']}`",
        f"- k: `{first['metrics']['k']}`",
        f"- prompt: {first['prompt']!r}",
        "",
        "Synthetic fixture-scale ablation (issue #24). Not a Skardu field study.",
        "",
        "| Ablation | include_generators | recall@k | precision@k | nDCG@k | pop_trap@k | spearman | top ids |",
        "|----------|--------------------|----------|-------------|--------|------------|----------|---------|",
    ]
    for run in runs:
        m = run["metrics"]
        gens = run.get("include_generators")
        gen_s = ",".join(gens) if gens else "(all)"
        tops = ", ".join(f"`{c}`" for c in run["ranked_candidate_ids"][:3])
        lines.append(
            "| "
            + " | ".join(
                [
                    run["ablation"],
                    f"`{gen_s}`",
                    _fmt_metric(m.get("recall_at_k")),
                    _fmt_metric(m.get("precision_at_k")),
                    _fmt_metric(m.get("ndcg_at_k")),
                    _fmt_metric(m.get("popularity_trap_at_k")),
                    _fmt_metric(m.get("rating_spearman")),
                    tops or "—",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- North Star: maximize `recall_at_k` on `interesting=true` without inflating `popularity_trap_at_k`.",
            "- `nDCG@k` uses label `human_rating` as graded relevance.",
            "- Re-run: `uv run python scripts/eval_discovery.py --ablations --write-report "
            + str(path.relative_to(repo_root()) if path.is_absolute() else path)
            + "`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack", default="fixtures/karakoram_mini")
    p.add_argument(
        "--labels",
        type=Path,
        default=repo_root() / "evaluation" / "fixtures" / "karakoram_mini",
        help="Place-label JSON file or directory",
    )
    p.add_argument("-p", "--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--mode", default="fearless_far")
    p.add_argument("--interpreter", default="rules", choices=["rules", "ollama", "auto"])
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--match-radius-km", type=float, default=2.0)
    p.add_argument("--popularity-threshold", type=float, default=7.0)
    p.add_argument("--max-results", type=int, default=10)
    p.add_argument(
        "--include-generators",
        default=None,
        help="Comma-separated generator allowlist (ablation)",
    )
    p.add_argument(
        "--exclude-generators",
        default=None,
        help="Comma-separated generator denylist",
    )
    p.add_argument(
        "--ablations",
        action="store_true",
        help="Run fixture preset ablations (all / water / dem_terrain / access)",
    )
    p.add_argument(
        "--write-report",
        type=Path,
        default=None,
        help="Write markdown comparison table (implies --ablations if no single run)",
    )
    p.add_argument("--json", action="store_true", help="Print metrics JSON only")
    args = p.parse_args(argv)

    common = dict(
        pack=args.pack,
        labels_path=args.labels,
        prompt=args.prompt,
        mode=args.mode,
        interpreter=args.interpreter,
        k=args.k,
        match_radius_km=args.match_radius_km,
        popularity_threshold=args.popularity_threshold,
        max_results=args.max_results,
    )

    runs: list[dict[str, Any]]
    if args.ablations or (args.write_report and not args.include_generators):
        runs = []
        for name, cfg in FIXTURE_ABLATIONS.items():
            runs.append(
                run_eval(
                    **common,
                    include_generators=cfg.get("include_generators"),
                    exclude_generators=cfg.get("exclude_generators"),
                    ablation_name=name,
                )
            )
    else:
        runs = [
            run_eval(
                **common,
                include_generators=_parse_csv(args.include_generators),
                exclude_generators=_parse_csv(args.exclude_generators),
                ablation_name="custom",
            )
        ]

    if args.write_report:
        write_markdown_report(runs, args.write_report)

    if args.json:
        out = runs[0] if len(runs) == 1 else {"runs": runs}
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        for payload in runs:
            m = payload["metrics"]
            print(
                f"[{payload['ablation']}] pack={payload['pack_id']} "
                f"hash={payload['pack_content_hash']} "
                f"interpreter={payload['interpreter']} k={m['k']}"
            )
            print(
                f"  labels={m['n_labels']} interesting={m['n_interesting']} "
                f"matched={m['n_matched']}"
            )
            print(f"  recall_at_k={m['recall_at_k']}")
            print(f"  precision_at_k={m['precision_at_k']}")
            print(f"  ndcg_at_k={m['ndcg_at_k']}")
            print(f"  popularity_trap_at_k={m['popularity_trap_at_k']}")
            print(f"  rating_spearman={m['rating_spearman']}")
            print("  top:", ", ".join(payload["ranked_candidate_ids"]))
            if len(runs) > 1:
                print()
        if args.write_report:
            print(f"wrote {args.write_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
