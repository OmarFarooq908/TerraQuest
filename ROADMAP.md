# Roadmap

Adventure AI is in **`0.x`**: APIs and schemas may change with RFCs. Maintainability and reproducible packs land before large product features.

## Near term — OSS foundation (0.2)

- [x] Deterministic discovery catalog (named generators)
- [x] Synthetic fixtures + offline golden missions
- [x] Community docs, CI quality gates, MkDocs
- [x] Canonical catalog contract (deprecate seeds dual-path)
- [x] Honest OSM backends (Geofabrik production; Overpass degraded)
- [x] Reproducible pack hashing + release workflow stubs

## Next — Reproducible packs (0.3)

- Pinned Geofabrik dated extracts where practical
- Stronger content hashes across all layers (in progress via layer byte hash)
- Eval suite for rules interpreter
- Benchmark smoke for discovery

## Then — Public beta (0.4)

- Intent validation / repair for LLM interpreters
- Calibrated confidence (real vs synthetic packs)
- Documented known limits (haversine travel, party_size)

## Later (post-invite)

- Real routing / access graphs
- Sentinel-2 indices in packs
- Mission-time local densification (Phase C) without changing `MissionIntent`
- PyPI publish of selected packages

## Good first issues (after v0.2.0)

- Docs typos / examples polish
- Unit tests for individual discovery generators
- Fixture catalog expansion (still synthetic, clearly marked)
- CLI help text / error message clarity
- Enable Discussions categories (see `.github/SETTINGS.md`)

## Out of scope for drive-by PRs

- Replacing the preference-vector scorer with an LLM ranker
- Calling external closed model APIs (OpenAI/Anthropic/Google) as defaults
- Committing built `data/packs/` or raw PBF/DEM tiles
