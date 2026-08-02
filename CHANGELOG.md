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

### Changed

- Canonical candidate file is `catalog.geojson` (`seeds.geojson` deprecated alias)
- Default Ollama model unified to `llama3.2`
- Overpass ingest requires explicit `allow_degraded_overpass`
- `CandidateFeatures.dist_*_km` may be `null` when the pack layer is empty

## [0.2.0] — 2026-08-02

### Added

- Initial public-ready scaffolding for Adventure AI monorepo
