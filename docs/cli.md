# CLI (`adventurectl`)

```bash
uv run adventurectl --help
uv run adventurectl pack build --config skardu_v1
uv run adventurectl pack info skardu_v1
uv run adventurectl pack materialize --pack fixtures/karakoram_mini
uv run adventurectl pack query --pack fixtures/karakoram_mini \
  --sql "SELECT generator, count(*) AS n FROM catalog GROUP BY 1"
uv run adventurectl mission run --pack fixtures/karakoram_mini --interpreter rules -p "..."
```

## Pack query (RFC-0004)

| Command | Meaning |
|---------|---------|
| `pack materialize` | Build derived `query.duckdb` from GeoJSON layers |
| `pack query --sql …` | Read-only SQL (auto-materializes if stale) |

GeoJSON remains the source of truth; `query.duckdb` is gitignored. See [pack builder](pack-builder.md).

## Mission options

| Flag | Meaning |
|------|---------|
| `--pack` | Pack id or `fixtures/...` |
| `--interpreter` | `auto` \| `rules` \| `ollama` (unknown values exit 2) |
| `--model` | Ollama model pin; default from `configs/models.yaml` (`mission_interpreter`) |
| `--strict-llm` | With `auto`, do not fall back to rules |
| `--json` | Machine-readable `MissionResult` |

Local LLM setup, cache layout, and missing-model errors: [offline inference](offline-inference.md).

## Honesty banners

- **SYNTHETIC PACK** — fixtures / CI
- **REAL PACK** — OSM + DEM sources listed
