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
| Ollama | `--interpreter ollama` | optional, local |

## Quality gates

```bash
uv run ruff check packages apps tests scripts
uv run ruff format packages apps tests scripts
uv run mypy packages/core/src/adventure_core
uv run pytest --cov=adventure_core --cov-fail-under=50
uv run python scripts/check_pack.py fixtures/karakoram_mini
uv run mkdocs build --strict
```

## Tests

Markers: `unit`, `integration`, `requires_osmium`, `requires_network`.

Default CI runs offline only (fixtures). Do not add network pack builds to the default workflow.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …). Enforced via pre-commit commit-msg hook.
