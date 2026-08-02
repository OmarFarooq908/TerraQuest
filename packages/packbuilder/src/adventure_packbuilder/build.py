"""Orchestrate OSM + DEM → discovery catalog Region Pack on disk."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from adventure_core.catalog import CATALOG_SCHEMA_VERSION, DiscoveryConfig
from adventure_core.config import configs_dir, load_yaml, repo_root
from adventure_core.pack_manifest import PackManifest, PackSource
from adventure_gis.pack_hash import pack_content_hash

from adventure_packbuilder.dem import dem_source_meta, download_dem_tiles
from adventure_packbuilder.discovery.pipeline import run_discovery, write_geojson
from adventure_packbuilder.geofabrik import fetch_geofabrik_layers
from adventure_packbuilder.osm import fetch_overpass, overpass_to_layers


def load_build_config(pack_id_or_path: str) -> PackManifest:
    path = Path(pack_id_or_path)
    if path.suffix in {".yaml", ".yml"} and path.exists():
        data = load_yaml(path)
        return PackManifest.model_validate(data)
    cfg = configs_dir() / "packs" / f"{pack_id_or_path}.yaml"
    if not cfg.exists():
        cfg = configs_dir() / "packs" / f"{pack_id_or_path}"
    if not cfg.exists():
        raise FileNotFoundError(f"Pack build config not found: {pack_id_or_path}")
    return PackManifest.model_validate(load_yaml(cfg))


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def build_pack(
    config: PackManifest,
    *,
    skip_dem: bool = False,
) -> Path:
    """Build a production pack under data/packs/<id>/."""
    root = repo_root()
    out = root / (config.output_dir or f"data/packs/{config.pack_id}")
    raw = out / "raw"
    layers_dir = out / "layers"
    raw.mkdir(parents=True, exist_ok=True)
    layers_dir.mkdir(parents=True, exist_ok=True)

    sources: list[PackSource] = []

    # --- OSM ---
    osm_cfg = config.osm or {}
    method = str(osm_cfg.get("method", "geofabrik")).lower()
    if method in {"geofabrik", "osmium", "pbf"}:
        pbf_url = osm_cfg.get(
            "geofabrik_url",
            "https://download.geofabrik.de/asia/pakistan-latest.osm.pbf",
        )
        cache_dir = root / osm_cfg.get("cache_dir", "data/cache")
        cache_name = osm_cfg.get("cache_pbf", "pakistan-latest.osm.pbf")
        cache_pbf = cache_dir / cache_name
        layers, artifacts = fetch_geofabrik_layers(
            config.bbox,
            raw / "osmium",
            pbf_url=pbf_url,
            cache_pbf=cache_pbf,
        )
        meta = layers.pop("meta")
        osm_provider = "OpenStreetMap via Geofabrik + osmium"
        osm_url = pbf_url
        osm_hash = _hash_file(artifacts["filtered_pbf"])
    else:
        overpass_url = osm_cfg.get("overpass_url", "https://overpass-api.de/api/interpreter")
        timeout_s = float(osm_cfg.get("timeout_s", 180))
        if not osm_cfg.get("allow_degraded_overpass"):
            raise RuntimeError(
                "Overpass OSM ingest is a degraded development path (no road_lines). "
                "Use osm.method: geofabrik (requires osmium-tool), or set "
                "osm.allow_degraded_overpass: true to acknowledge incomplete discovery."
            )
        payload = fetch_overpass(config.bbox, url=overpass_url, timeout_s=timeout_s)
        raw_osm = raw / "overpass.json"
        raw_osm.write_text(json.dumps(payload), encoding="utf-8")
        layers = overpass_to_layers(payload)
        layers.setdefault("road_lines", {"type": "FeatureCollection", "features": []})
        layers.setdefault("water_geoms", {"type": "FeatureCollection", "features": []})
        meta = layers.pop("meta")
        meta["degraded"] = True
        meta["degraded_reason"] = "overpass_no_road_lines"
        osm_provider = "OpenStreetMap via Overpass (degraded)"
        osm_url = overpass_url
        osm_hash = _hash_file(raw_osm)

    write_geojson(layers_dir / "settlements.geojson", layers["settlements"])
    write_geojson(layers_dir / "water.geojson", layers["water"])
    write_geojson(layers_dir / "road_nodes.geojson", layers["road_nodes"])
    write_geojson(
        layers_dir / "road_lines.geojson",
        layers.get("road_lines", {"type": "FeatureCollection", "features": []}),
    )
    write_geojson(
        layers_dir / "peaks.geojson",
        layers.get("peaks", {"type": "FeatureCollection", "features": []}),
    )
    write_geojson(
        layers_dir / "viewpoints.geojson",
        layers.get("viewpoints", {"type": "FeatureCollection", "features": []}),
    )
    sources.append(
        PackSource(
            kind="osm",
            provider=osm_provider,
            retrieved_at=meta.get("retrieved_at"),
            license="ODbL 1.0",
            attribution="© OpenStreetMap contributors",
            url=osm_url,
            content_hash=osm_hash,
            extra=meta,
        )
    )

    # --- DEM ---
    dem_paths: list[Path] = []
    if not skip_dem:
        dem_dir = raw / "dem"
        dem_paths = download_dem_tiles(config.bbox, dem_dir)
        dem_meta = dem_source_meta(dem_paths)
        sources.append(
            PackSource(
                kind="dem",
                provider=dem_meta["provider"],
                retrieved_at=dem_meta["retrieved_at"],
                license=dem_meta["license"],
                attribution=dem_meta["attribution"],
                content_hash=_hash_bytes(b"".join(_hash_file(p).encode() for p in dem_paths)),
                extra={"tiles": dem_meta["tiles"]},
            )
        )

    # --- Discovery catalog ---
    discovery_cfg = DiscoveryConfig.model_validate(config.discovery or {})
    discovered = run_discovery(
        layers,
        bbox=config.bbox,
        dem_paths=dem_paths,
        discovery=discovery_cfg,
    )
    write_geojson(layers_dir / "catalog.geojson", discovered["catalog"])
    write_geojson(layers_dir / "elevation.geojson", discovered["elevation"])
    # Remove deprecated dual-path alias if a prior build left it behind
    legacy_seeds = layers_dir / "seeds.geojson"
    if legacy_seeds.exists():
        legacy_seeds.unlink()

    # Production OSM path must retain road geometries for access generators
    road_lines = layers.get("road_lines") or {"features": []}
    osm_method = str((config.osm or {}).get("method", "geofabrik")).lower()
    access_gens_enabled = any(
        discovery_cfg.quota_for(g, 0) > 0 for g in ("track_terminus", "road_spur")
    )
    if (
        osm_method in {"geofabrik", "osmium", "pbf"}
        and access_gens_enabled
        and len(road_lines.get("features", [])) == 0
    ):
        raise RuntimeError(
            "Production pack build produced empty road_lines but access generators "
            "are enabled. Ensure osmium export kept LineStrings, or set those "
            "generator quotas to 0. Overpass is a degraded path — use method: geofabrik."
        )

    built_at = datetime.now(UTC).isoformat()
    stats = discovered["stats"]
    content_hash = pack_content_hash(layers_dir, stats)
    manifest = config.model_copy(
        update={
            "synthetic": False,
            "feature_schema_version": CATALOG_SCHEMA_VERSION,
            "sources": sources,
            "built_at": built_at,
            "content_hash": content_hash,
            "notes": (config.notes or "")
            + f" | catalog={stats['catalog_count']}"
            + f" dem_elev={stats['with_dem_elevation']}"
            + f" generators={stats['selected_by_generator']}",
        }
    )
    pack_yaml = {
        **manifest.model_dump(
            exclude={"osm", "dem", "discovery", "candidate_limits", "output_dir", "fixtures_dir"}
        ),
        "layers": {
            "settlements": "layers/settlements.geojson",
            "water": "layers/water.geojson",
            "road_nodes": "layers/road_nodes.geojson",
            "road_lines": "layers/road_lines.geojson",
            "catalog": "layers/catalog.geojson",
            "elevation": "layers/elevation.geojson",
        },
    }
    (out / "pack.yaml").write_text(yaml.safe_dump(pack_yaml, sort_keys=False), encoding="utf-8")

    notice = f"""Adventure AI Region Pack: {manifest.pack_id}
Built: {built_at}
BBox: {manifest.bbox}
Catalog schema: {CATALOG_SCHEMA_VERSION}

OpenStreetMap data © OpenStreetMap contributors, ODbL 1.0
https://www.openstreetmap.org/copyright

Copernicus DEM © DLR / Airbus — provided under COPERNICUS by the European Union and ESA
https://spacedata.copernicus.eu/

Candidates are produced by named deterministic generators (track_terminus,
road_spur, isolation_maximum, dem_local_max, …). Redistribute OSM-derived
products under ODbL share-alike obligations.
"""
    (out / "NOTICE").write_text(notice, encoding="utf-8")
    (out / "build_stats.json").write_text(
        json.dumps(
            {
                "osm": meta,
                "discovery": stats,
                "dem_tiles": [p.name for p in dem_paths],
                "content_hash": content_hash,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out
