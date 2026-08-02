"""Unit tests for evaluation place labels + discovery metrics (RFC-0002)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from adventure_core.config import repo_root
from adventure_core.evaluation import (
    PLACE_LABEL_SCHEMA_VERSION,
    PlaceLabel,
    RankedRef,
    compute_discovery_metrics,
    load_place_labels,
    match_ranked_to_labels,
    ndcg_at_k,
)
from pydantic import ValidationError

FIXTURE_LABELS = repo_root() / "evaluation" / "fixtures" / "karakoram_mini"


def test_load_fixture_labels():
    labels = load_place_labels(FIXTURE_LABELS)
    assert len(labels) >= 6
    assert all(lb.schema_version == PLACE_LABEL_SCHEMA_VERSION for lb in labels)
    assert all(lb.synthetic for lb in labels)
    assert any(lb.interesting for lb in labels)
    assert any(not lb.interesting for lb in labels)


def test_place_label_rejects_bad_rating():
    with pytest.raises(ValidationError):
        PlaceLabel(
            id="x",
            geometry={"type": "Point", "coordinates": [75.0, 35.0]},
            known=True,
            interesting=True,
            human_rating=11.0,
            license="Apache-2.0",
            synthetic=True,
        )


def test_match_by_catalog_id():
    labels = load_place_labels(FIXTURE_LABELS)
    ranked = [
        RankedRef(candidate_id="seed_turquoise_lake", score=0.9, lon=75.18, lat=35.72),
        RankedRef(candidate_id="seed_near_town_hill", score=0.2, lon=74.85, lat=35.35),
    ]
    matches = match_ranked_to_labels(ranked, labels, k=2)
    assert len(matches) == 2
    assert matches[0].label_id.endswith("turquoise_lake")
    assert matches[0].interesting is True
    assert matches[1].interesting is False


def test_metrics_recall_and_popularity_trap():
    labels = load_place_labels(FIXTURE_LABELS)
    interesting_ids = [lb.catalog_id for lb in labels if lb.interesting and lb.catalog_id]
    ranked = [
        RankedRef(candidate_id=cid, score=1.0 - 0.01 * i, lon=75.0, lat=35.7)
        for i, cid in enumerate(interesting_ids)
    ]
    ranked.append(RankedRef(candidate_id="seed_near_town_hill", score=0.01, lon=74.85, lat=35.35))
    metrics = compute_discovery_metrics(ranked, labels, k=5)
    assert metrics.n_interesting >= 5
    assert metrics.recall_at_k is not None
    assert metrics.recall_at_k >= 0.8
    assert metrics.precision_at_k == 1.0
    assert metrics.popularity_trap_at_k in (None, 0.0) or metrics.popularity_trap_at_k < 0.5


def test_ndcg_prefers_high_rated_at_top():
    labels = [
        PlaceLabel(
            id="a",
            catalog_id="a",
            geometry={"type": "Point", "coordinates": [75.0, 35.0]},
            known=True,
            interesting=True,
            human_rating=9.0,
            license="Apache-2.0",
            synthetic=True,
        ),
        PlaceLabel(
            id="b",
            catalog_id="b",
            geometry={"type": "Point", "coordinates": [75.1, 35.0]},
            known=True,
            interesting=True,
            human_rating=3.0,
            license="Apache-2.0",
            synthetic=True,
        ),
    ]
    good = [
        RankedRef(candidate_id="a", score=1.0, lon=75.0, lat=35.0),
        RankedRef(candidate_id="b", score=0.5, lon=75.1, lat=35.0),
    ]
    bad = list(reversed(good))
    assert ndcg_at_k(good, labels, k=2) > ndcg_at_k(bad, labels, k=2)
    assert ndcg_at_k(good, labels, k=2) == pytest.approx(1.0)
    metrics = compute_discovery_metrics(good, labels, k=2)
    assert metrics.ndcg_at_k is not None
    assert metrics.ndcg_at_k > 0.9


def test_ndcg_none_with_fewer_than_two_ratings():
    labels = [
        PlaceLabel(
            id="a",
            catalog_id="a",
            geometry={"type": "Point", "coordinates": [75.0, 35.0]},
            known=True,
            interesting=True,
            human_rating=9.0,
            license="Apache-2.0",
            synthetic=True,
        ),
    ]
    ranked = [RankedRef(candidate_id="a", score=1.0, lon=75.0, lat=35.0)]
    assert ndcg_at_k(ranked, labels, k=1) is None


def test_ndcg_pool_relative_ideal():
    labels = [
        PlaceLabel(
            id="hi",
            catalog_id="seed_a",
            geometry={"type": "Point", "coordinates": [75.0, 35.0]},
            known=True,
            interesting=True,
            human_rating=9.0,
            license="Apache-2.0",
            synthetic=True,
        ),
        PlaceLabel(
            id="lo",
            catalog_id="seed_b",
            geometry={"type": "Point", "coordinates": [75.1, 35.0]},
            known=True,
            interesting=True,
            human_rating=3.0,
            license="Apache-2.0",
            synthetic=True,
        ),
        PlaceLabel(
            id="out",
            catalog_id="seed_out",
            geometry={"type": "Point", "coordinates": [75.2, 35.0]},
            known=True,
            interesting=True,
            human_rating=10.0,
            license="Apache-2.0",
            synthetic=True,
        ),
    ]
    ranked = [
        RankedRef(candidate_id="seed_a", score=1.0, lon=75.0, lat=35.0),
        RankedRef(candidate_id="seed_b", score=0.5, lon=75.1, lat=35.0),
    ]
    # Global ideal wants seed_out (10) first → perfect in-pool ranking < 1
    global_ndcg = ndcg_at_k(ranked, labels, k=2)
    pool_ndcg = ndcg_at_k(ranked, labels, k=2, ideal_catalog_ids={"seed_a", "seed_b"})
    assert global_ndcg is not None and pool_ndcg is not None
    assert pool_ndcg == pytest.approx(1.0)
    assert global_ndcg < pool_ndcg


def test_filter_candidates_empty_include_is_not_noop():
    from adventure_cli.pipeline import filter_candidates_by_generator
    from adventure_core.schemas import Candidate, CandidateFeatures

    cand = Candidate(
        id="c1",
        name="c1",
        lon=75.0,
        lat=35.0,
        claim="x",
        features=CandidateFeatures(
            remoteness=0.5,
            terrain_drama=0.5,
            water=0.5,
            viewpoint=0.5,
            novelty=0.5,
            access_fit=0.5,
            camping=0.5,
            forest=0.5,
            crowd=0.5,
            risk=0.1,
            restriction=0.0,
        ),
        evidence={"generator": "named_waterbody"},
    )
    assert filter_candidates_by_generator([cand], include_generators=[]) == []
    assert len(filter_candidates_by_generator([cand], include_generators=None)) == 1
    assert len(filter_candidates_by_generator([cand], include_generators=["named_waterbody"])) == 1
    assert filter_candidates_by_generator([cand], exclude_generators=["named_waterbody"]) == []


def test_eval_discovery_script_smoke():
    script = repo_root() / "scripts" / "eval_discovery.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--pack",
            "fixtures/karakoram_mini",
            "--labels",
            str(FIXTURE_LABELS),
            "--interpreter",
            "rules",
            "--k",
            "5",
            "--json",
        ],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "recall_at_k" in proc.stdout
    assert "ndcg_at_k" in proc.stdout
    assert "pack_content_hash" in proc.stdout


def test_eval_write_report_with_exclude_stays_custom(tmp_path: Path):
    script = repo_root() / "scripts" / "eval_discovery.py"
    out = tmp_path / "custom.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--exclude-generators",
            "track_terminus,road_spur",
            "--write-report",
            str(out),
            "--json",
        ],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert '"ablation": "custom"' in proc.stdout
    assert "all_generators" not in proc.stdout
    assert out.is_file()


def test_eval_discovery_ablations_and_generator_filter():
    script = repo_root() / "scripts" / "eval_discovery.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--pack",
            "fixtures/karakoram_mini",
            "--labels",
            str(FIXTURE_LABELS),
            "--interpreter",
            "rules",
            "--include-generators",
            "named_waterbody,unnamed_waterbody",
            "--json",
        ],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "named_waterbody" in proc.stdout

    abl = subprocess.run(
        [
            sys.executable,
            str(script),
            "--ablations",
            "--json",
        ],
        cwd=repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert abl.returncode == 0, abl.stderr
    assert "all_generators" in abl.stdout
    assert "water_only" in abl.stdout
    assert "osm_landmarks" in abl.stdout
    report = Path(repo_root() / "evaluation" / "reports" / "karakoram_mini_baseline.md")
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    assert "pack_content_hash" in text
    assert "pool-relative" in text.lower() or "pool-relative" in text
