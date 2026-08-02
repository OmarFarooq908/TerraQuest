# Evaluation methodology

## Two layers

| Layer | Path | Question |
|-------|------|----------|
| Intent / ranking regression | `eval/golden_prompts.yaml`, `tests/test_golden_mission.py` | Is interpretation + scoring deterministic and sign-correct? |
| **Discovery quality** | `evaluation/` + RFC-0002 | Did we surface places an explorer would actually care about? |

North Star metric (for now): **`recall_at_k`** on labels with `interesting=true` (default k=5), with **`popularity_trap_at_k`** as a guardrail.

## Offline golden missions

`tests/test_golden_mission.py` asserts:

- Rules interpreter emits expected preference signs for rich prompts
- Fearless & Far mode does not rank near-town controls first
- Preference alignment prefers matching candidate dimensions

## Discovery-quality harness (RFC-0002)

```bash
uv run python scripts/eval_discovery.py \
  --pack fixtures/karakoram_mini \
  --labels evaluation/fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds." \
  --k 5
```

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

See `eval/golden_prompts.yaml` for rules-interpreter property checks (extended over time).

## What “pass” means

- **CI / golden:** Deterministic ranking given the same `MissionIntent` + catalog. LLM intent quality is evaluated separately and is not required for CI green.
- **North Star:** Improving `recall_at_k` (and not inflating popularity trap) on labeled regions — starting with the synthetic fixture slice, then real Skardu labels.
