# CLI (`adventurectl`)

```bash
uv run adventurectl --help
uv run adventurectl pack build --config skardu_v1
uv run adventurectl pack info skardu_v1
uv run adventurectl mission run --pack fixtures/karakoram_mini --interpreter rules -p "..."
```

## Mission options

| Flag | Meaning |
|------|---------|
| `--pack` | Pack id or `fixtures/...` |
| `--interpreter` | `auto` \| `rules` \| `ollama` |
| `--model` | Ollama model (default `llama3.2`) |
| `--strict-llm` | With `auto`, do not fall back to rules |
| `--json` | Machine-readable `MissionResult` |

## Honesty banners

- **SYNTHETIC PACK** — fixtures / CI
- **REAL PACK** — OSM + DEM sources listed
