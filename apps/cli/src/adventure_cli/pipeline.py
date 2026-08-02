"""End-to-end mission pipeline — interpreter → GIS → vector scorer."""

from __future__ import annotations

from collections.abc import Collection

from adventure_core.config import load_mode, load_pack_manifest
from adventure_core.constraints import parse_constraints
from adventure_core.schemas import Candidate, MissionRequest, MissionResult
from adventure_gis import generate_candidates, load_pack_data
from adventure_inference import interpret_mission
from adventure_scoring import build_intent_coverage, rank_missions
from adventure_scoring.confidence import CALIBRATION_VERSION

__all__ = ["run_mission", "parse_constraints", "filter_candidates_by_generator"]


def filter_candidates_by_generator(
    candidates: list[Candidate],
    *,
    include_generators: Collection[str] | None = None,
    exclude_generators: Collection[str] | None = None,
) -> list[Candidate]:
    """Filter catalog-derived candidates by discovery ``generator`` evidence.

    ``None`` means “no constraint”. An empty collection is intentional and may
    yield zero candidates (unlike a falsy skip).
    """
    include = set(include_generators) if include_generators is not None else None
    exclude = set(exclude_generators) if exclude_generators is not None else None
    out: list[Candidate] = []
    for cand in candidates:
        gen = str(cand.evidence.get("generator") or "")
        if include is not None and gen not in include:
            continue
        if exclude is not None and gen in exclude:
            continue
        out.append(cand)
    return out


def run_mission(
    *,
    pack: str,
    mode: str,
    prompt: str,
    max_results: int = 5,
    interpreter: str = "auto",
    model: str = "llama3.2",
    allow_rules_fallback: bool = True,
    include_generators: Collection[str] | None = None,
    exclude_generators: Collection[str] | None = None,
) -> MissionResult:
    intent = interpret_mission(
        prompt,
        interpreter=interpreter,  # type: ignore[arg-type]
        model=model,
        mode=mode,
        allow_rules_fallback=allow_rules_fallback,
    )
    request = MissionRequest(
        prompt=prompt,
        pack_id=pack,
        mode=mode,
        intent=intent,
        max_results=max_results,
    )

    manifest, pack_dir = load_pack_manifest(pack)
    mode_weights = load_mode(mode)
    pack_data = load_pack_data(pack_dir)
    hc = intent.constraints
    candidates = generate_candidates(
        pack_data,
        vehicle=hc.vehicle,
        vehicle_class=hc.vehicle_class,
        days=hc.days,
    )
    if include_generators is not None or exclude_generators is not None:
        candidates = filter_candidates_by_generator(
            candidates,
            include_generators=include_generators,
            exclude_generators=exclude_generators,
        )
    missions = rank_missions(
        candidates,
        mode_weights,
        intent=intent,
        max_results=request.max_results,
        pack_synthetic=manifest.synthetic,
    )
    coverage = build_intent_coverage(intent)

    src_kinds = [s.kind for s in manifest.sources] if manifest.sources else []
    pack_kind = "synthetic" if manifest.synthetic else "real"
    notes = [
        f"pack={manifest.pack_id}",
        f"synthetic={manifest.synthetic}",
        f"pack_kind={pack_kind}",
        f"pack_sources={src_kinds or ('fixture' if manifest.synthetic else 'unknown')}",
        f"catalog_evaluated={len(candidates)}",
        f"interpreter={intent.source}",
        f"schema={intent.schema_version}",
        "ranking=deterministic_preference_vector",
        f"confidence_calibration={CALIBRATION_VERSION}",
        *[f"note={n}" for n in intent.interpreter_notes],
    ]
    if include_generators:
        notes.append(f"include_generators={','.join(sorted(include_generators))}")
    if exclude_generators:
        notes.append(f"exclude_generators={','.join(sorted(exclude_generators))}")

    return MissionResult(
        request=request,
        mode=mode,
        pack_id=manifest.pack_id,
        missions=missions,
        coverage=coverage,
        notes=notes,
    )
