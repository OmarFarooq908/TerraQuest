# Evaluation (intent goldens)

Golden prompts and expected **preference signs** / hard constraints for the rules
interpreter. Loaded by `tests/test_intent_regression.py` (CI).

See `eval/golden_prompts.yaml` (≥20 cases). Add new cases there — document steps
in `docs/evaluation.md`.

Optional Ollama: set `expect.interpreter: ollama` and run with
`ADVENTURE_OLLAMA_GOLDENS=1`.

For **discovery-quality place labels** (interesting vs popular), see `evaluation/`
and RFC-0002.
