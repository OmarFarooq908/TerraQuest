# Evaluation methodology

## Two layers

| Layer | Path | Question |
|-------|------|----------|
| Intent / ranking regression | `eval/golden_prompts.yaml`, `tests/test_intent_regression.py` | Is interpretation + scoring deterministic and sign-correct? |
| **Discovery quality** | `evaluation/` + RFC-0002 | Did we surface places an explorer would actually care about? |

North Star metric (for now): **`recall_at_k`** on labels with `interesting=true` (default k=5), with **`popularity_trap_at_k`** as a guardrail.

## Offline golden missions

`tests/test_intent_regression.py` loads `eval/golden_prompts.yaml` (≥20 cases) and asserts:

- Preference **signs** via `dim_gt` / `dim_lt` (not exact floats)
- Hard constraints when declared (`days`, `origin`, `vehicle_*`, `party_size`)
- Near-neutral prompts stay near zero (`near_neutral: true`)
- All `inv_*` polarity cases remain covered

Default CI uses `--interpreter rules` only. Opt-in Ollama goldens (local or
manual workflow):

```bash
ADVENTURE_OLLAMA_GOLDENS=1 uv run pytest -q tests/test_intent_regression.py -k ollama
```

On GitHub: Actions → CI → Run workflow → enable **run_ollama_goldens**
(`intent-ollama` job; not a required check).

### Adding a golden case

1. Append an entry under `prompts:` in `eval/golden_prompts.yaml`.
2. Prefer **sign** expectations (`water_gt: 0.5`) over brittle exact values.
3. Set `expect.interpreter: rules` for CI; use `ollama` only for opt-in cases.
4. Run `uv run pytest -q tests/test_intent_regression.py` and confirm the new id appears.
5. Keep `inv_*` ids for polarity regressions; use descriptive ids for constraint/regional cases.

`tests/test_golden_mission.py` still covers end-to-end ranking smoke (Fearless & Far vs river/forest prompts).

## Discovery-quality harness (RFC-0002 / issue #24)

```bash
uv run python scripts/eval_discovery.py \
  --pack fixtures/karakoram_mini \
  --labels evaluation/fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds." \
  --k 5
```

Generator ablations + pinned pack hash + markdown report:

```bash
uv run python scripts/eval_discovery.py --ablations \
  --write-report evaluation/reports/karakoram_mini_baseline.md
```

Single-family filter:

```bash
uv run python scripts/eval_discovery.py \
  --include-generators named_waterbody,unnamed_waterbody --json
```

Metrics include `recall_at_k`, `precision_at_k`, `ndcg_at_k` (graded via `human_rating`;
ablations use a **pool-relative** ideal so family comparisons are fair),
`popularity_trap_at_k`, and `rating_spearman`. Reports record `pack_content_hash`.

Filters rank among **existing catalog features** from selected generators; they do
not re-run packbuilder discovery.

Checked-in fixture baseline:
[`evaluation/reports/karakoram_mini_baseline.md`](https://github.com/OmarFarooq908/TerraQuest/blob/main/evaluation/reports/karakoram_mini_baseline.md).

- Schema: `evaluation/schema/place_label.schema.json` and `adventure_core.evaluation.PlaceLabel`
- CI uses **synthetic** labels under `evaluation/fixtures/karakoram_mini/`
- Real regional labels live under `evaluation/skardu/` (etc.); start empty and grow with curator licenses

See `evaluation/README.md` and `RFC/0002-evaluation-dataset.md`.

## Pack validation

```bash
uv run python scripts/check_pack.py fixtures/karakoram_mini
uv run python scripts/hash_fixture_catalog.py --check
```

## Eval prompts

See `eval/golden_prompts.yaml` for rules-interpreter property checks, including
**preference-inversion** cases (`inv_*`). Polarity repair runs in
`interpret_mission` (`adventure_core.polarity`) so LLM sign flips like
“hate crowds” → `human_activity=+…` are corrected before scoring.

## What “pass” means

- **CI / golden:** Deterministic ranking given the same `MissionIntent` + catalog. LLM intent quality is evaluated separately and is not required for CI green.
- **North Star:** Improving `recall_at_k` (and not inflating popularity trap) on labeled regions — starting with the synthetic fixture slice, then real Skardu labels.
