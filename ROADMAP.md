# Roadmap

Adventure AI / TerraQuest is in **`0.x`**: APIs and schemas may change with RFCs.

## North Star (current focus)

> Can we consistently discover places that an experienced explorer would genuinely add to their travel list?

Working balance: ~**80%** better data + evaluation, ~**20%** new features. Architecture for `MissionIntent` → deterministic GIS scoring stays frozen unless an RFC proves a North Star need.

Milestone: **North Star — discovery quality** (see issues). Start here:

1. [#11 Evaluation dataset](https://github.com/OmarFarooq908/TerraQuest/issues/9)
2. [#12 Formal ontology](https://github.com/OmarFarooq908/TerraQuest/issues/8)
3. [#31 Measuring “adventure”](https://github.com/OmarFarooq908/TerraQuest/issues/29)
4. P0 correctness issues (intent, inversion, schema, confidence)

Project model (three tracks + P0–P4): [#10](https://github.com/OmarFarooq908/TerraQuest/issues/8).

## Near term — OSS foundation (0.2)

- [x] Deterministic discovery catalog (named generators)
- [x] Synthetic fixtures + offline golden missions
- [x] Community docs, CI quality gates, MkDocs
- [x] Canonical catalog contract (deprecate seeds dual-path)
- [x] Honest OSM backends (Geofabrik production; Overpass degraded)
- [x] Reproducible pack hashing + release workflow stubs

## Next — Reproducible packs (0.3)

- Pinned Geofabrik dated extracts where practical
- Stronger content hashes across all layers
- Intent / schema regression suites (P0)
- Evidence ledger completeness
- [x] Region Pack architecture RFC

## Then — Public beta (0.4)

- Intent validation / repair for LLM interpreters
- Calibrated confidence (real vs synthetic packs)
- Documented known limits (haversine travel, party_size)
- Thin product UX (export/GPX) only where it helps field eval

## Later (after North Star evidence)

- Real routing / access graphs (P2 — capability, not a bug)
- Sentinel-2 indices + VLM features (P1 — judged by eval lift)
- Mission-time local densification (Phase C) without changing `MissionIntent`
- Intelligence layer (explanations first; memory/KG later)
- PyPI publish of selected packages

## Out of scope for drive-by PRs

- Replacing the preference-vector scorer with an LLM ranker
- Calling external closed model APIs (OpenAI/Anthropic/Google) as defaults
- Committing built `data/packs/` or raw PBF/DEM tiles
- Filing missing future capabilities (routing, weather, map UI) as `bug`
