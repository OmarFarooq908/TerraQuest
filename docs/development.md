# Development

## Setup

```bash
uv sync --group dev --group docs
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
uv run pytest
```

### System dependencies

| Tool | Required for | Install |
|------|----------------|---------|
| Python 3.12+ | everything | — |
| uv | workspace | astral.sh/uv |
| osmium-tool | `pack build` (Geofabrik) | `brew install osmium-tool` |
| Ollama | `--interpreter ollama` | optional, local — see [offline inference](offline-inference.md) |

## Quality gates

```bash
uv run ruff check packages apps tests scripts
uv run ruff format packages apps tests scripts
uv run mypy packages/core/src/adventure_core
uv run pytest -q \
  --cov=adventure_core --cov=adventure_gis --cov=adventure_scoring \
  --cov-report=json:coverage.json --cov-fail-under=70
uv run python scripts/check_coverage_gates.py
uv run python scripts/check_pack.py fixtures/karakoram_mini
uv run mkdocs build --strict
```

Per-module floors live in `configs/coverage_gates.yaml` (see `CONTRIBUTING.md`).

## Tests

Markers: `unit`, `integration`, `requires_osmium`, `requires_network`.

Default CI runs offline only (fixtures). Do not add network pack builds to the default workflow.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …). Enforced via pre-commit commit-msg hook.
