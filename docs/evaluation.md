# Evaluation methodology

## Offline golden missions

`tests/test_golden_mission.py` asserts:

- Rules interpreter emits expected preference signs for rich prompts
- Fearless & Far mode does not rank near-town controls first
- Preference alignment prefers matching candidate dimensions

## Pack validation

```bash
uv run python scripts/check_pack.py fixtures/karakoram_mini
uv run python scripts/hash_fixture_catalog.py --check
```

## Eval prompts

See `eval/golden_prompts.yaml` in the repository root for rules-interpreter property checks (extended over time).

## What “pass” means

Deterministic ranking given the same `MissionIntent` + catalog. LLM intent quality is evaluated separately and is not required for CI green.
