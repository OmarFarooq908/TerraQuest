# Skardu evaluation labels

Curator-authored place labels for measuring discovery quality around Skardu.

## Status

Empty on purpose for the first merge of RFC-0002. Add `*.json` arrays of place labels
(`schema_version: "0.1.0"`) as field knowledge is digitized.

Target for the North Star milestone: **≥ 30** `interesting=true` places plus **≥ 15** controls
(`interesting=false` and/or high `google_maps_popularity`), with per-record `license` and
`synthetic: false`.

See `../README.md` and `RFC/0002-evaluation-dataset.md`.

## Suggested files (when ready)

- `hidden_lakes.json`
- `alpine_passes.json`
- `shepherd_routes.json`
- `forgotten_tracks.json`
