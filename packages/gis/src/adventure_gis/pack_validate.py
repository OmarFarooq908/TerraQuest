"""Strict Region Pack layout + catalog validation (issue #13 / RFC-0003)."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

from adventure_core.catalog import CATALOG_SCHEMA_VERSION
from adventure_core.catalog_validate import CatalogValidationError, validate_catalog_geojson
from adventure_core.config import load_pack_manifest

from adventure_gis.pack_contract import REQUIRED_PACK_LAYER_KEYS
from adventure_gis.pack_data import load_pack_data
from adventure_gis.pack_hash import pack_content_hash


def validate_pack(pack_ref: str, *, allow_legacy_seeds: bool = False) -> list[str]:
    """Return actionable error strings (empty list = ok)."""
    errors: list[str] = []
    manifest, pack_dir = load_pack_manifest(pack_ref)
    layers = pack_dir / "layers"
    catalog_path = layers / "catalog.geojson"
    seeds_path = layers / "seeds.geojson"

    if catalog_path.exists() and seeds_path.exists() and not allow_legacy_seeds:
        errors.append(
            f"dual-path catalog: both {catalog_path.name} and deprecated "
            f"{seeds_path.name} present (pass --allow-legacy-seeds to waive)"
        )

    catalog_file: Path | None = None
    if catalog_path.exists():
        catalog_file = catalog_path
    elif seeds_path.exists() and allow_legacy_seeds:
        warnings.warn(
            f"{pack_dir}: missing {catalog_path.name}; validating legacy "
            f"{seeds_path.name} (migrate ASAP)",
            DeprecationWarning,
            stacklevel=2,
        )
        catalog_file = seeds_path
    else:
        errors.append(f"missing {catalog_path}")
        return errors

    raw = json.loads(catalog_file.read_text(encoding="utf-8"))
    errors.extend(validate_catalog_geojson(raw))

    try:
        data = load_pack_data(pack_dir, allow_legacy_seeds=True, strict=False)
    except CatalogValidationError as exc:
        errors.append(str(exc))
        return errors

    if not data.catalog:
        errors.append("catalog is empty after load")

    if manifest.feature_schema_version != CATALOG_SCHEMA_VERSION and not manifest.synthetic:
        errors.append(
            f"manifest feature_schema_version={manifest.feature_schema_version} "
            f"expected {CATALOG_SCHEMA_VERSION}"
        )

    if not manifest.synthetic:
        notice = pack_dir / "NOTICE"
        if not notice.is_file():
            errors.append("missing NOTICE (required for non-synthetic packs; see RFC-0003)")
        errors.extend(_validate_layers_map(manifest.layers, layers, allow_legacy_seeds))

    if manifest.content_hash:
        stats_path = pack_dir / "build_stats.json"
        if not stats_path.exists():
            errors.append(
                "content_hash set on manifest but build_stats.json is missing (cannot verify)"
            )
        else:
            blob = json.loads(stats_path.read_text(encoding="utf-8"))
            actual = pack_content_hash(layers, blob)
            if actual != manifest.content_hash:
                errors.append(
                    f"content_hash mismatch: manifest={manifest.content_hash} actual={actual}"
                )

    return errors


def verify_pack(pack_ref: str, *, allow_legacy_seeds: bool = False) -> dict[str, Any]:
    """Validate a pack and return a structured offline-verify report.

    ``ok`` is True iff ``errors`` is empty. Always includes a computed
    ``fingerprint`` when ``layers/`` exists (fixtures without manifest
    ``content_hash`` still get a layer fingerprint for pinning).
    """
    errors = validate_pack(pack_ref, allow_legacy_seeds=allow_legacy_seeds)
    manifest, pack_dir = load_pack_manifest(pack_ref)
    layers = pack_dir / "layers"
    stats_path = pack_dir / "build_stats.json"
    stats: dict[str, Any] | None = None
    if stats_path.is_file():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))

    fingerprint: str | None = None
    if layers.is_dir():
        fingerprint = pack_content_hash(layers, stats)

    catalog_count = 0
    try:
        data = load_pack_data(pack_dir, allow_legacy_seeds=True, strict=False)
        catalog_count = len(data.catalog)
    except CatalogValidationError:
        catalog_count = 0

    declared = manifest.content_hash
    hash_match: bool | None = None
    if declared and fingerprint:
        hash_match = declared == fingerprint

    query_db: dict[str, Any] | None = None
    db_path = pack_dir / "query.duckdb"
    if db_path.is_file() and fingerprint is not None:
        try:
            from adventure_gis.pack_query import read_pack_db_meta

            meta = read_pack_db_meta(db_path)
            db_hash = meta.get("content_hash")
            query_db = {
                "path": str(db_path),
                "content_hash": db_hash,
                "stale": db_hash != fingerprint,
            }
        except Exception as exc:  # noqa: BLE001 — report, don't fail verify
            query_db = {"path": str(db_path), "error": str(exc)}

    return {
        "ok": not errors,
        "errors": errors,
        "pack_id": manifest.pack_id,
        "synthetic": bool(manifest.synthetic),
        "dir": str(pack_dir),
        "schema": CATALOG_SCHEMA_VERSION,
        "feature_schema_version": manifest.feature_schema_version,
        "catalog_count": catalog_count,
        "content_hash": declared,
        "fingerprint": fingerprint,
        "hash_match": hash_match,
        "query_db": query_db,
    }


def _validate_layers_map(
    layers_map: dict[str, str],
    layers_dir: Path,
    allow_legacy_seeds: bool,
) -> list[str]:
    """Ensure production manifests list required keys and match on-disk GeoJSON."""
    errors: list[str] = []
    if not layers_map:
        errors.append(
            "manifest layers map missing or empty; rebuild with current packbuilder (RFC-0003)"
        )
        return errors

    missing_keys = [k for k in REQUIRED_PACK_LAYER_KEYS if k not in layers_map]
    if missing_keys:
        errors.append("manifest layers map missing required keys: " + ", ".join(missing_keys))

    mapped_names = {Path(p).name for p in layers_map.values()}
    for path in sorted(layers_dir.glob("*.geojson")):
        if path.name == "seeds.geojson" and allow_legacy_seeds:
            continue
        if path.name == "seeds.geojson":
            # Dual-path already reported separately; still a map hygiene issue.
            continue
        if path.name not in mapped_names:
            errors.append(
                f"layers/{path.name} present on disk but not listed in manifest layers map"
            )
    return errors
