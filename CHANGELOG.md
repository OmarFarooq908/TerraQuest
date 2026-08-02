# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/) while in `0.x`
(breaking changes bump the minor version and require an RFC).

## [Unreleased]

### Changed

- Pack content hash v2 (#62 / #17): domain-separated fingerprint; discovery knobs (`quotas`, global + per-generator spacing, grid, schema version, `generators_run`) included alongside layers + `selected_by_generator`; per-layer SHA-256 digests in `build_stats.json`; fixture/baseline pins retargeted
- Evidence ledger v2 (#64 / #17): non-synthetic OSM-element generators require `provenance.osm_id` (positive int / integral float); packbuilder skips element candidates lacking `osm_id`; grid/DEM generators and synthetic fixtures unchanged; `EVIDENCE_LEDGER_VERSION` → `"2"`

### Added

- Offline pack verify CLI (#70 / #28): `adventurectl pack verify` wraps catalog/layout/`content_hash` checks and prints a layer fingerprint; `--json` (pure report, no banner) / `--allow-legacy-seeds`; `hash_match` only when `build_stats.json` is readable; stale `query.duckdb` is a warning; `scripts/check_pack.py` shares the same report helper
- Markdown mission export (#68 / #28): `adventurectl mission run --export-md` writes a readable report (intent, ranks, claims, explanations) for field notes / eval logs; composable with GPX
- Schema regression pins (#66): `schemas/mission_intent.schema.json` + `schemas/catalog_feature.schema.json` kept aligned with Pydantic via `tests/test_schema_regression.py`
- Geofabrik dated extract pins (#60): `allow_latest: false` requires checksum; optional `geofabrik_md5` / `geofabrik_sha256` verify (including cache reuse); `skardu_v1` pinned to `pakistan-260801`
- GPX waypoint export (#58 / #28): `adventurectl mission run --export-gpx` writes GPX 1.1 waypoints (+ optional haversine rank-order track) for field eval; XML text sanitized; `max_results<=0` returns no missions
- Skardu evaluation seed + corpus CI (#56 / #9): provisional curator labels under `evaluation/skardu/`; `validate_place_label_corpus` gate (schema, ontology ids, unique catalog ids, opposite-interesting separation); RFC-0002 Accepted (infra; regional fill ongoing)
- Measuring “adventure” (RFC-0005 / #29): operational North Star pin — primary `recall_at_k` (k=5) + `popularity_trap_at_k` guardrail; `configs/north_star.yaml` wired into eval harness defaults; threats-to-validity note
- Pack-time VLM features (RFC-0007 / #22): optional `vlm_features` layer + evidence join; packbuilder attach from precomputed GeoJSON; never used as a ranker; `pack_vlm` pin in `configs/models.yaml`
- Sentinel-2 indices (RFC-0006 / #21): optional `sentinel_indices` pack layer + featurize path; packbuilder attach via precomputed GeoJSON; ranking weights unchanged pending eval lift
- Docs polish (#4): tighter README/docs quick-start (fixture vs real pack, default `--pack` gotcha), CLI flag table, fixed ROADMAP issue links, known-limits formatting
- Offline inference contract (#25): `configs/models.yaml` pins, `InferenceError` UX, `data/cache/inference/` layout, `docs/offline-inference.md` (Ollama-only defaults; CI stays model-free)
- GIS feature depth (#23): settlement density kernel (crowd/novelty) + road-class-aware `access_fit`; inventory in `docs/gis-features.md`
- Region Pack architecture freeze (#18): RFC-0003 + aligned pack-builder/architecture docs; hash stats normalization; production `layers:` map lists peaks/viewpoints
- DuckDB pack query layer (#20): RFC-0004; derived `query.duckdb`; `adventurectl pack materialize|query`; eval `--duckdb-join`
- Open-source foundation: CI, Ruff/mypy, MkDocs, community docs, RFC process
- Deterministic discovery catalog (named generators) with provenance
- Pack validation and fixture catalog hash scripts
- Evaluation place-label schema + discovery metrics harness (RFC-0002)
- Preference polarity detection/repair against prompt cues (anti-inversion)
- GIS feature audit: no `-1`/`999` distance sentinels; missing layers → `null` + evidence flags
- MissionIntent semantic validation + repair (`intent_repairs`) for LLM/rules paths
- Strict catalog FeatureCollection validation (`adventure_core.catalog_validate`) at pack load and in `scripts/check_pack.py`
- `adventure_gis.validate_pack` / `pack_content_hash` for CI and builder reuse
- Intent regression suite: ≥20 golden prompts with sign/constraint checks (`tests/test_intent_regression.py`)
- Opt-in Ollama intent goldens (`ADVENTURE_OLLAMA_GOLDENS=1` / CI workflow_dispatch `intent-ollama`)
- Segmented coverage gates (`configs/coverage_gates.yaml` + `scripts/check_coverage_gates.py`); global floor **70%**
- Offline unit tests for individual discovery generators (`tests/test_generators.py`)
- CLI help/error regression tests for fixture-vs-pack messaging (`tests/test_cli_help_errors.py`)
- Pack-kind confidence priors/ceiling (`heuristic-v1`) + `docs/confidence.md`; synthetic packs cannot match real-pack confidence
- Expanded `fixtures/karakoram_mini` catalog (13 features) covering all nine discovery generators; added peaks/viewpoints/road_lines support layers
- Fixture catalog coverage regression tests (`tests/test_fixture_catalog_coverage.py`)
- Evidence ledger v1 (`adventure_core.evidence_ledger`): required evidence keys per generator; enforced by catalog/`check_pack`; fixture catalog deepened
- Ranking eval harness: `ndcg_at_k`, generator ablations, `pack_content_hash` pinning, fixture report (`evaluation/reports/karakoram_mini_baseline.md`)

### Changed

- CLI help/errors clarify fixture vs production packs and point to osmium install + `fixtures/karakoram_mini` when builds fail
- `build_confidence` / `rank_missions` take `pack_synthetic`; MissionResult notes expose `pack_kind` and `confidence_calibration`
- Catalog validation rejects empty/incomplete `evidence` objects (ledger v1); synthetic sources require `evidence.fixture=true`
- `run_mission` / `eval_discovery.py` support `--include-generators` / `--exclude-generators` ablations
- Canonical candidate file is `catalog.geojson`; pack builder no longer writes deprecated `seeds.geojson`
- `check_pack` / `validate_pack` fail on dual-path catalog+seeds (waive with `--allow-legacy-seeds`) and on `content_hash` mismatch when declared
- Pack load no longer silently fills missing catalog fields (`strict=True` by default)
- Default Ollama model unified to `llama3.2`
- Overpass ingest requires explicit `allow_degraded_overpass`
- `CandidateFeatures.dist_*_km` may be `null` when the pack layer is empty

## [0.2.0] — 2026-08-02

### Added

- Initial public-ready scaffolding for Adventure AI monorepo
