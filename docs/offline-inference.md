# Offline inference

Adventure AI is **local-first**. Default mission interpretation never calls
cloud LLM APIs and never requires `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or
similar credentials.

## Supported runtime (today)

| Runtime | Role | Status |
|---------|------|--------|
| **Ollama** | Mission Interpreter (`MissionIntent` only) | Supported |
| Rules interpreter | Deterministic offline fallback / CI | Always available |
| Cloud LLM APIs | — | **Out of scope** as defaults (see `ROADMAP.md`) |

Pins live in [`configs/models.yaml`](https://github.com/OmarFarooq908/TerraQuest/blob/main/configs/models.yaml)
(`default_model`, `fallback`, approximate `hardware_floors`).

Default model: **`llama3.2`**. Fallbacks: `llama3.2`, `llama3.1:8b`, `qwen3:8b`,
`llama3.2:3b`.

### Hardware floors (approximate free RAM)

| Model | RAM |
|-------|-----|
| `llama3.2` / `llama3.2:3b` | ≈ 4 GB |
| `llama3.1:8b` / `qwen3:8b` | ≈ 8 GB |

These are guidance only — not hard gates in code.

## Setup

```bash
# Install Ollama, then:
ollama serve          # if not already running as a service
ollama pull llama3.2

uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter ollama \
  --model llama3.2 \
  -p "Three days, rivers and forests, hate crowds."
```

Base URL resolution (first match wins):

1. `--` / API `base_url` argument (library)
2. `ADVENTURE_OLLAMA_BASE_URL`
3. `OLLAMA_HOST` (Ollama’s own env; `host:port` or full URL)
4. `configs/models.yaml` → `default_base_url` (`http://127.0.0.1:11434`)

## Interpreter modes

| `--interpreter` | Behavior |
|-----------------|----------|
| `rules` | Offline; no Ollama. Prefer this in CI and scripts. |
| `ollama` | Requires a reachable Ollama + installed model. Clear exit on failure. |
| `auto` (default) | Try Ollama; fall back to rules unless `--strict-llm`. |

## Missing model / daemon UX

Failures raise `adventure_inference.InferenceError` with recovery steps
(`ollama serve`, `ollama pull …`, or `--interpreter rules`). The CLI prints the
message and exits with code **2**.

## Cache layout

| Path | Contents | Gitignored? |
|------|----------|-------------|
| Ollama store (e.g. `~/.ollama`) | Model weights | Outside repo |
| `data/cache/` | Geofabrik PBF downloads | Yes |
| `data/cache/inference/` | Adventure-managed inference artifacts (future embeddings / pack-time VLM) | Yes (under `data/cache/`) |

Override Adventure’s inference cache with `ADVENTURE_INFERENCE_CACHE=/path`.

Do **not** commit model weights or `data/cache/**`.

## CI stays offline

Default GitHub Actions runs **without** Ollama and without models:

- Tests use `--interpreter rules` / fixtures
- Opt-in Ollama goldens: `ADVENTURE_OLLAMA_GOLDENS=1` or workflow_dispatch `intent-ollama`

```bash
uv run pytest -q   # no cloud keys, no local models required
```

## Library entry points

```python
from adventure_inference import (
    InferenceError,
    inference_cache_dir,
    interpret_mission,
    load_models_config,
    ollama_available,
)
```
