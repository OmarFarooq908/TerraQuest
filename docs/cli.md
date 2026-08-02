# CLI (`adventurectl`)

Install the workspace first (`uv sync --group dev`), then:

```bash
uv run adventurectl --help
uv run adventurectl pack build --config skardu_v1
uv run adventurectl pack info skardu_v1
uv run adventurectl pack verify --pack fixtures/karakoram_mini
uv run adventurectl pack materialize --pack fixtures/karakoram_mini
uv run adventurectl pack query --pack fixtures/karakoram_mini \
  --sql "SELECT generator, count(*) AS n FROM catalog GROUP BY 1"
uv run adventurectl mission run --pack fixtures/karakoram_mini --interpreter rules -p "..."
```

Offline smoke uses **`fixtures/karakoram_mini`** (pass it explicitly). The CLI
default `--pack` is **`skardu_v1`**, which only works after a local
`pack build` (see [pack builder](pack-builder.md)).

## Pack commands

| Command | Meaning |
|---------|---------|
| `pack build` | Build a production pack (needs osmium + network) |
| `pack info` | Manifest + honesty banner |
| `pack verify` | Offline layout/catalog/`content_hash` checks (+ fingerprint) |
| `pack materialize` | Build derived `query.duckdb` from GeoJSON layers |
| `pack query --sql …` | Read-only SQL (auto-materializes if stale) |

### Pack verify (offline)

```bash
uv run adventurectl pack verify --pack fixtures/karakoram_mini
uv run adventurectl pack verify --pack data/packs/skardu_v1 --json
```

Same honesty bar as `scripts/check_pack.py` (catalog contract, dual-path seeds,
NOTICE/layers for real packs, declared `content_hash` when present). Also prints
the computed layer fingerprint for pinning. If `query.duckdb` exists, reports
whether it is stale vs that fingerprint.

## Mission options

| Flag | Meaning |
|------|---------|
| `--pack` | Pack id or `fixtures/...` path (default **`skardu_v1`** — use `fixtures/karakoram_mini` offline) |
| `--mode` | Scoring mode from `configs/modes/` (default `fearless_far`) |
| `-p` / `--prompt` | Natural-language mission prompt |
| `--interpreter` | `auto` \| `rules` \| `ollama` (unknown values exit 2) |
| `--model` | Ollama model pin; default from `configs/models.yaml` (`mission_interpreter`) |
| `--strict-llm` | With `auto`, do not fall back to rules |
| `--max-results` | How many ranked missions to print (default 5) |
| `--json` | Machine-readable `MissionResult` |
| `--export-gpx PATH` | Write GPX 1.1 waypoints (+ optional rank-order track) for phone GPS / field label checks |
| `--gpx-no-track` | With `--export-gpx`, waypoints only |
| `--export-md PATH` | Write a Markdown mission report (prompt, ranks, claims, explanations) for notes / eval logs |

### GPX field export

```bash
uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, rivers and forests, hate crowds." \
  --export-gpx /tmp/mission.gpx
```

Use this to drop ranked stops into OsmAnd / Gaia / a handheld for verifying
evaluation labels in the field ([evaluation](evaluation.md)). The optional track
is **rank order** (origin first when parsed) — haversine display only, not a
road router ([known limits](known-limits.md)).

### Markdown field notes

```bash
uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, rivers and forests, hate crowds." \
  --export-md /tmp/mission.md \
  --export-gpx /tmp/mission.gpx
```

`--export-md` writes a readable card (intent, ranked stops, claims, ranking
“why”) for eval notebooks or PR comments. Composable with GPX / `--json`.

Local LLM setup, cache layout, and missing-model errors: [offline inference](offline-inference.md).

## Honesty banners

- **SYNTHETIC PACK** — fixtures / CI
- **REAL PACK** — OSM + DEM sources listed
