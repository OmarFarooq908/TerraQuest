#!/usr/bin/env python3
"""Offline discovery-quality metrics + generator ablations (RFC-0002 / issue #24).

Runs the normal mission pipeline, then scores ranked results against place labels.
Does not invent candidates or call cloud APIs.

Generator filters apply **after** catalog load (rank among features from those
generators) — they do not re-run packbuilder discovery.
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
    NorthStarConfig,
    RankedRef,
    compute_discovery_metrics,
    load_north_star_config,
    load_place_labels,
    metrics_as_dict,
)
from adventure_gis import load_pack_data
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
    "osm_landmarks": {
        "include_generators": ["osm_peak", "osm_viewpoint"],
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


def catalog_ids_for_generators(
    pack: str,
    *,
    include_generators: list[str] | None = None,
    exclude_generators: list[str] | None = None,
) -> list[str]:
    """Catalog feature ids in the filtered generator pool (for pool-relative nDCG)."""
    _, pack_dir = load_pack_manifest(pack)
    data = load_pack_data(pack_dir)
    include = set(include_generators) if include_generators is not None else None
    exclude = set(exclude_generators) if exclude_generators is not None else None
    ids: list[str] = []
    for seed in data.catalog:
        gen = str(seed.properties.get("generator") or "")
        if include is not None and gen not in include:
            continue
        if exclude is not None and gen in exclude:
            continue
        ids.append(seed.id)
    return ids


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
    duckdb_join: bool = False,
) -> dict[str, Any]:
    labels = load_place_labels(labels_path)
    pool_ids = catalog_ids_for_generators(
        pack,
        include_generators=include_generators,
        exclude_generators=exclude_generators,
    )
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
    # Pool-relative ideal when filtering generators; global ideal for all_generators.
    ideal_ids = (
        pool_ids if include_generators is not None or exclude_generators is not None else None
    )
    metrics = compute_discovery_metrics(
        ranked,
        labels,
        k=k,
        match_radius_km=match_radius_km,
        popularity_threshold=popularity_threshold,
        ideal_catalog_ids=ideal_ids,
    )
    payload: dict[str, Any] = {
        "ablation": ablation_name or "custom",
        "pack_id": result.pack_id,
        "pack_content_hash": pack_fingerprint(pack),
        "labels_path": str(labels_path),
        "mode": result.mode,
        "interpreter": result.request.intent.source,
        "prompt": prompt,
        "match_radius_km": match_radius_km,
        "popularity_threshold": popularity_threshold,
        "include_generators": include_generators,
        "exclude_generators": exclude_generators,
        "pool_catalog_ids": pool_ids,
        "ranked_candidate_ids": [m.candidate_id for m in result.missions[:k]],
        "metrics": metrics_as_dict(metrics),
        "notes": result.notes,
    }
    if duckdb_join:
        from adventure_gis.pack_query import catalog_label_join_counts

        payload["duckdb_join"] = catalog_label_join_counts(
            pack, [lab.model_dump() for lab in labels]
        )
    return payload


def _fmt_metric(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.4f}"


def write_markdown_report(runs: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    first = runs[0]
    try:
        rerun_path = str(path.resolve().relative_to(repo_root()))
    except ValueError:
        rerun_path = str(path)
    lines = [
        "# Discovery ranking comparison",
        "",
        f"- pack: `{first['pack_id']}`",
        f"- pack_content_hash: `{first['pack_content_hash']}`",
        f"- labels: `{first.get('labels_path', '')}`",
        f"- interpreter: `{first['interpreter']}`",
        f"- mode: `{first['mode']}`",
        f"- k: `{first['metrics']['k']}`",
        f"- match_radius_km: `{first.get('match_radius_km', 2.0)}`",
        f"- prompt: {first['prompt']!r}",
        "",
        "Synthetic fixture-scale ablation (issue #24). Not a Skardu field study.",
        "Filters rank among **existing catalog features** from selected generators",
        "(post-catalog); they do not re-run packbuilder discovery.",
        "Ablation `nDCG@k` uses a **pool-relative** ideal (labels whose `catalog_id`",
        "is in the filtered catalog); `all_generators` uses the global ideal.",
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
            "- North Star (RFC-0005): maximize `recall_at_k` on `interesting=true` without inflating `popularity_trap_at_k`.",
            "- `nDCG@k` uses label `human_rating` with exponential gain `(2^rel - 1) / log2(rank+1)`.",
            "- Precision@k denominator is matched labels only; unlabeled tops do not dilute it.",
            "- Re-run: `uv run python scripts/eval_discovery.py --ablations --write-report "
            + rerun_path
            + "`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_arg_parser(
    pin: NorthStarConfig | None = None,
) -> argparse.ArgumentParser:
    """CLI parser with North Star–pinned defaults (RFC-0005)."""
    cfg = pin if pin is not None else load_north_star_config()
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
        default=DEFAULT_PROMPT,
        help="Mission prompt (North Star default: Fearless & Far family; see RFC-0005)",
    )
    p.add_argument("--mode", default=cfg.default_mode)
    p.add_argument("--interpreter", default="rules", choices=["rules", "ollama", "auto"])
    p.add_argument("--k", type=int, default=cfg.k)
    p.add_argument("--match-radius-km", type=float, default=cfg.match_radius_km)
    p.add_argument("--popularity-threshold", type=float, default=cfg.popularity_threshold)
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
        help="Run fixture preset ablations (all / water / dem_terrain / access / osm)",
    )
    p.add_argument(
        "--write-report",
        type=Path,
        default=None,
        help="Write markdown comparison table (implies --ablations unless filters set)",
    )
    p.add_argument("--json", action="store_true", help="Print metrics JSON only")
    p.add_argument(
        "--duckdb-join",
        action="store_true",
        help="Also report catalog↔label join counts via derived query.duckdb (RFC-0004)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    # Runtime pin (YAML) wins over module constants when they ever diverge.
    pin = load_north_star_config()
    args = build_arg_parser(pin).parse_args(argv)

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
        duckdb_join=args.duckdb_join,
    )

    custom_filters = bool(args.include_generators or args.exclude_generators)
    runs: list[dict[str, Any]]
    if args.ablations or (args.write_report and not custom_filters):
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
            if payload.get("duckdb_join"):
                print(f"  duckdb_join={payload['duckdb_join']}")
            print("  top:", ", ".join(payload["ranked_candidate_ids"]))
            if len(runs) > 1:
                print()
        if args.write_report:
            print(f"wrote {args.write_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
