# Adventure AI

**Local-first exploration intelligence: missions, not itineraries.**

Adventure AI discovers extraordinary places with **deterministic GIS** (OpenStreetMap + Copernicus DEM) and uses a local LLM only to translate language into a structured [`MissionIntent`](docs/mission-intent.md). The model never invents coordinates or picks winners.

[Documentation](docs/index.md) · [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

## Status

`0.x` — APIs may change with [RFCs](RFC/README.md). Offline CI uses **synthetic** fixtures; production packs are built locally from OSM + DEM and are **never committed**.

## Quick start (offline)

Needs Python **3.12+** and [uv](https://docs.astral.sh/uv/). No network, no Ollama, no `osmium` for this path.

```bash
uv sync --group dev
uv run pytest

uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds."
```

You should see a red **SYNTHETIC PACK** banner and a short ranked list. The fixture pack is for CI and local smoke tests only — not real geography. Always pass `--pack fixtures/karakoram_mini` offline; the CLI default pack id is `skardu_v1` (a built production pack).

More detail: [CLI](docs/cli.md) · [Development](docs/development.md) · [Known limits](docs/known-limits.md)

## Build a real Region Pack

Needs network once and [`osmium-tool`](https://osmcode.org/osmium-tool/) on `PATH`:

```bash
brew install osmium-tool   # macOS; see osmcode.org for other platforms

uv run adventurectl pack build --config skardu_v1
uv run python scripts/check_pack.py data/packs/skardu_v1

uv run adventurectl mission run \
  --pack skardu_v1 \
  --interpreter rules \
  -p "I'm in Skardu. Honda City, weekend, love rivers, hate crowds."
```

Real packs print a green **REAL PACK** banner with sources (`osm`, `dem`). Built trees live under `data/packs/` (gitignored) — see [pack builder](docs/pack-builder.md).

Optional local LLM intent (Ollama only — no cloud API keys; see [offline inference](docs/offline-inference.md)):

```bash
ollama pull llama3.2
uv run adventurectl mission run \
  --pack skardu_v1 \
  --interpreter ollama \
  --model llama3.2 \
  -p "Fearless & Far from Skardu: alpine lakes, 3 days, 4x4"
```

## Architecture (one screen)

```
Pack Builder (Geofabrik/OSM + Copernicus DEM)
  → named generators (track_terminus, isolation_maximum, dem_local_max, …)
  → data/packs/<id>/catalog.geojson

Prompt → Mission Interpreter → MissionIntent
  → filter + featurize catalog → preference-vector score → ranked missions
```

Full picture: [Architecture](docs/architecture.md) · [Generators](docs/generators.md) · [Evaluation](docs/evaluation.md)

## License & data

- Code: [Apache-2.0](LICENSE)
- OpenStreetMap: ODbL — see [NOTICE](NOTICE) and each pack `NOTICE`
- Copernicus DEM: upstream Copernicus terms (pack `NOTICE`)
