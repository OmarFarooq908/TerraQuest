# RFC-0005: Measuring “adventure” (operational North Star)

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/29

## Summary

Define an **operational** meaning of “adventure” for TerraQuest science and
product claims, map candidate metrics to offline computations over Region Packs
+ place labels (RFC-0002), and **freeze one primary North Star metric for the
next 1–2 months**: `recall_at_k` on `interesting=true` labels (default **k=5**),
with `popularity_trap_at_k` as a hard guardrail.

This RFC does **not** change MissionIntent, catalog schema, or ranking code. It
binds research attention so demos and generator PRs can be judged by one number.

## Motivation

Without an operational definition, “more adventurous” is vibes. Papers, RFCs, and
pack changes need a falsifiable question:

> Given a mission prompt and a labeled region, how often do our top-k ranked
> catalog places match places a curator marked **interesting** — without simply
> resurfacing tourist-popular pins?

RFC-0002 shipped labels + metrics. Issue #29 asks which metric is the *primary*
compass for a short horizon.

## Operational definition

For measurement purposes (not philosophy):

> A system discovers “adventure” well when, for Fearless & Far–style missions on a
> labeled pack, its top-k results recover curator-`interesting` places at a high
> rate while keeping the share of high-popularity matches low.

Scope bounds:

- **In:** offline pack + labels + deterministic score (`scripts/eval_discovery.py`).
- **Out (for now):** live user return-to-list rates, LLM-as-judge, map UI A/B tests.

## Candidate metrics → offline computation

| Metric | Question | Offline computation | Status |
|--------|----------|---------------------|--------|
| **`recall_at_k` (interesting)** | Did top-k hit explorer-worthy places? | Among labels with `interesting=true`, fraction matched to a top-k mission (exact `catalog_id` else haversine ≤ `match_radius_km`, default 2 km). **Primary.** | Shipping (`adventure_core.evaluation`) |
| **`popularity_trap_at_k`** | Are we just finding Instagram pins? | Among top-k **matched** labels, fraction with `google_maps_popularity >= threshold` (default 7). **Guardrail** — must not rise as recall rises. | Shipping |
| **`precision_at_k` (interesting)** | Of matched tops, how many are interesting? | Among top-k results that match any label, fraction with `interesting=true`. Secondary; unlabeled tops do not dilute. | Shipping |
| **`ndcg_at_k`** | Are higher `human_rating` places ranked higher? | Graded relevance from `human_rating`; ablations use pool-relative ideal (RFC-0002 / #24). Secondary for ranking quality. | Shipping |
| **`rating_spearman`** | Score vs curator rating correlation | Spearman ρ on matched pairs with ratings. Diagnostic only (small-n fragile). | Shipping |
| **Interestingness–popularity gap** | Do we prefer interesting∩¬popular? | Offline: among matched top-k, count `interesting ∧ popularity < 7` vs `interesting ∧ popularity ≥ 7`. Report as commentary / future metric; not primary. | Computable from labels; not a named harness field yet |
| **Ontology diversity@k** | Are tops covering distinct adventure kinds? | Needs formal ontology (issue #10). Until then, transitional: unique `tags` / `ontology_ids` in top-k. | Deferred |
| **Return-to-list rate** | Would explorers keep a place? | Field study / product telemetry. | Deferred (P4 UX / science later) |

Pinned config: `configs/north_star.yaml` and
`adventure_core.evaluation.NORTH_STAR_*` constants must agree.
`scripts/eval_discovery.py` and metric function defaults read from that pin
(not duplicated magic numbers).

## Primary North Star (freeze window)

**Primary metric (1–2 months from RFC merge):**

`recall_at_k` on `interesting=true`, **k=5**, default Fearless & Far prompt family,
pack fingerprint recorded via `pack_content_hash`.

**Guardrail:** do not claim a win if `popularity_trap_at_k` increases materially
on the same label set (investigate; prefer holding trap flat while recall rises).

**Reporting:** every discovery eval report / PR that claims “better discovery”
must quote at least `recall_at_k` and `popularity_trap_at_k` on a named label
slice (fixture and/or regional).

### Why this one

1. Matches the product question (recover places worth adding to a list).
2. Already implemented and CI-smokeable on synthetic fixtures.
3. Does not require ontology or field apps.
4. Guardrail blocks the obvious failure mode (popularity chasing).

### Why not ndcg / spearman as primary

Graded metrics need denser `human_rating` coverage; fixture-scale Spearman is
noisy. Keep them as secondary diagnostics.

## Threats to validity

| Threat | Mitigation |
|--------|------------|
| Synthetic fixture labels ≠ real explorers | Treat fixture recall as **smoke only**; promote claims on `evaluation/skardu/` (etc.) once ≥30 interesting + ≥15 controls (region README). |
| Label leakage / circular catalog_ids | Prefer independent curator labels; document when `catalog_id` was assigned post-hoc. |
| Match-radius false merges | Default 2 km; report radius; prefer exact `catalog_id` when present. |
| Prompt / mode cherry-picking | Standardize on documented default prompt in `eval_discovery.py`; ablations must say which prompt. |
| Generator ablations changing the candidate pool | Use pool-relative nDCG; always report `pack_content_hash` and include/exclude sets. |
| Popularity proxy missing | Trap metric is `None` when popularity absent — do not treat as 0. |
| Goodharting recall | Guardrail + qualitative spot-checks; refuse to optimize only fixture labels. |

## Impact on contracts

- [ ] MissionIntent schema
- [ ] Catalog schema / generators
- [ ] Pack manifest
- [ ] CLI UX
- [x] Docs/process (RFC-0005, evaluation docs, `configs/north_star.yaml`)

## Alternatives considered

1. **Make `ndcg_at_k` primary** — better once ratings are dense; premature now.
2. **Composite score** — harder to explain; hides tradeoffs with popularity.
3. **Wait for ontology diversity** — blocks North Star progress on #10.

## Reproducibility & attribution

Metrics consume pack layers + evaluation labels under their existing licenses
(RFC-0002). No cloud APIs.

## Migration / compatibility

- Document freeze in `docs/evaluation.md` and `evaluation/README.md`.
- No harness breaking changes required.
- After ~1–2 months or when Skardu labels hit target counts, revisit primary
  metric in a short follow-up RFC if evidence warrants.

## Unresolved questions

1. Exact numeric “material” delta for popularity-trap regressions (e.g. +0.1 absolute).
2. Whether interestingness–popularity gap becomes a named metric before ontology diversity.
3. Field return-to-list protocol when P4 UX exists.
