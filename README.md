# Adventure AI

**Local-first exploration intelligence: missions, not itineraries.**

Adventure AI discovers extraordinary places with **deterministic GIS** (OpenStreetMap + Copernicus DEM) and uses a local LLM only to translate language into a structured [`MissionIntent`](docs/mission-intent.md). The model never invents coordinates or picks winners.

[Documentation](docs/index.md) · [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

## Status

`0.x` — APIs may change with [RFCs](RFC/README.md). Offline CI uses **synthetic** fixtures; production packs are built locally from OSM + DEM.

## Quick start (offline)

```bash
# Python 3.12+
uv sync --group dev

uv run pytest
uv run adventurectl mission run \
  --pack fixtures/karakoram_mini \
  --interpreter rules \
  -p "Three days, Suzuki Swift, rivers and forests, hate crowds."
```

Synthetic packs print a red **SYNTHETIC PACK** banner.

## Build a real Region Pack

Requires network once and [`osmium-tool`](https://osmcode.org/osmium-tool/):

```bash
brew install osmium-tool   # macOS
uv run adventurectl pack build --config skardu_v1
uv run adventurectl mission run \
  --pack skardu_v1 \
  --interpreter rules \
  -p "I'm in Skardu. Honda City, weekend, love rivers, hate crowds."
```

Real packs print a green **REAL PACK** banner with sources (`osm`, `dem`).

Optional local LLM intent:

```bash
uv run adventurectl mission run \
  --pack skardu_v1 \
  --interpreter ollama \
  --model llama3.2 \
  -p "Fearless far from Skardu: alpine lakes, 3 days, 4x4"
```

## Architecture (one screen)

```
Pack Builder (Geofabrik/OSM + Copernicus DEM)
  → named generators (track_terminus, isolation_maximum, dem_local_max, …)
  → data/packs/<id>/catalog.geojson

Prompt → Mission Interpreter → MissionIntent
  → filter + featurize catalog → preference-vector score → ranked missions
```

## License & data

- Code: [Apache-2.0](LICENSE)
- OpenStreetMap: ODbL — see [NOTICE](NOTICE) and each pack `NOTICE`
- Copernicus DEM: upstream Copernicus terms (pack `NOTICE`)
