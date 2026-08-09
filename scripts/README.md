# Scripts

Maintainer / CI helpers.

| Script | Purpose |
|--------|---------|
| `check_pack.py` | Strict catalog schema + dual-path/`content_hash` checks (`--allow-legacy-seeds`); prefer `adventurectl pack verify` |
| `check_coverage_gates.py` | Per-module coverage floors from `configs/coverage_gates.yaml` |
| `hash_fixture_catalog.py` | Reproducibility hash for CI drift detection |
| `eo_anomaly_scout.py` | Offline GeoTIFF texture/edge scout → GeoJSON/GPX for triage (RFC-0010) |
