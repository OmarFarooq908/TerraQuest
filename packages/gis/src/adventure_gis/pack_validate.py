"""Strict Region Pack layout + catalog validation (issue #13)."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from adventure_core.catalog import CATALOG_SCHEMA_VERSION
from adventure_core.catalog_validate import CatalogValidationError, validate_catalog_geojson
from adventure_core.config import load_pack_manifest

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

    if manifest.content_hash:
        stats_path = pack_dir / "build_stats.json"
        if not stats_path.exists():
            errors.append(
                "content_hash set on manifest but build_stats.json is missing "
                "(cannot verify)"
            )
        else:
            blob = json.loads(stats_path.read_text(encoding="utf-8"))
            stats = blob.get("discovery") or {}
            actual = pack_content_hash(layers, stats)
            if actual != manifest.content_hash:
                errors.append(
                    f"content_hash mismatch: manifest={manifest.content_hash} "
                    f"actual={actual}"
                )

    return errors
