# RFC-0009: Deterministic ranking explanations

- Status: Draft
- Authors: Omar Farooq
- Created: 2026-08-02
- Tracking issue / discussion: https://github.com/OmarFarooq908/TerraQuest/issues/27

## Summary

Add **deterministic, non-LLM** ranking explanations on each `RankedMission`
so users and evaluators can see *why* a place scored high — from mode priors,
preference alignment, hard-constraint penalties, goals, and catalog evidence —
without inventing new candidates or rewriting scores.

## Motivation

Confidence `reasons` explain *how sure* we are (pack kind, evidence channels).
They do **not** explain *why this place beat others*. Feature breakdowns exist
in JSON but are opaque in the CLI. Issue #27’s near-term policy: ship P3 pieces
that improve **trust** (deterministic explanations) before embeddings/KG.

## Detailed design

### 1. Schema (additive)

`RankedMission.explanations: list[ReasonCode]` where each item is
`{code, detail}` (same shape as confidence reasons).

| Code prefix | Meaning |
|-------------|---------|
| `mode.*` | Discovery-mode weighted GIS prior |
| `pref.*` | Preference↔dimension contribution (signed) |
| `goal.*` | Goal boost |
| `constraint.*` | Hard logistics penalty / nudge |
| `evidence.*` | Catalog generator / ontology ids (context, not score) |

Explanations are **derived** from already-computed `feature_breakdown`,
`preference_adjustments`, and `evidence`. They never change the score.

### 2. Builder

`adventure_scoring.explanations.build_ranking_explanations(...)` → ≤6 reasons.
Selection is **category-aware** (constraints → prefs → goals → mode → evidence)
so large discovery-mode priors cannot hide intent drivers. Within a category,
lines are ordered by absolute contribution.

Rules:

1. No LLM / no free-text generation beyond fixed templates.
2. Skip near-zero contributions (`|x| < 0.02` for prefs; tiny mode terms).
3. Preference copy must respect **sign of the preference weight**:
   avoid-dims (`weight < 0`) with low feature → “honors avoid-*”; never treat
   `contrib = weight × feature < 0` alone as “conflicts”.
4. Evidence lines are informational when present (`generator`, `ontology_ids`);
   reserve up to two evidence slots so ontology is not dropped behind mode lines.

### 3. CLI

Human mode: after the ranked table, print **Why** for each shown mission
(explanations). JSON mode includes the new field via `model_dump`.

### 4. Out of scope

- LLM narrative polish of explanations
- Counterfactuals (“would win if remoteness +0.2”)
- Changing score formulas

## Impact on contracts

- [ ] MissionIntent schema
- [ ] Catalog schema / generators
- [ ] Pack manifest
- [x] CLI UX (Why section)
- [x] `RankedMission` additive field

## Alternatives considered

1. **Reuse `confidence.reasons`** — wrong semantics (certainty ≠ ranking why).
2. **LLM “explain this score”** — violates hard rule: intelligence explains from
   facts; must not invent places. Deferred as optional presentation later.
3. **Raw dump of breakdown dict only** — insufficient for field/eval trust.

## Reproducibility & attribution

No new data sources. Explanations are pure functions of scored missions.

## Unresolved questions

1. Whether eval harness should assert explanation codes for golden missions.
2. Localization of detail strings.
