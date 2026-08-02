# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/) while in `0.x`
(breaking changes bump the minor version and require an RFC).

## [Unreleased]

### Added

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

### Changed

- CLI help/errors clarify fixture vs production packs and point to osmium install + `fixtures/karakoram_mini` when builds fail
- `build_confidence` / `rank_missions` take `pack_synthetic`; MissionResult notes expose `pack_kind` and `confidence_calibration`
- Canonical candidate file is `catalog.geojson`; pack builder no longer writes deprecated `seeds.geojson`
- `check_pack` / `validate_pack` fail on dual-path catalog+seeds (waive with `--allow-legacy-seeds`) and on `content_hash` mismatch when declared
- Pack load no longer silently fills missing catalog fields (`strict=True` by default)
- Default Ollama model unified to `llama3.2`
- Overpass ingest requires explicit `allow_degraded_overpass`
- `CandidateFeatures.dist_*_km` may be `null` when the pack layer is empty

## [0.2.0] — 2026-08-02

### Added

- Initial public-ready scaffolding for Adventure AI monorepo
