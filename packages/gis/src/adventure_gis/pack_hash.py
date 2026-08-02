"""Content hash for Region Pack layer directories (RFC-0003 / issue #62)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Domain-separated pack fingerprint. Bump when the hashed inputs change.
PACK_CONTENT_HASH_VERSION = 2
_PACK_CONTENT_DOMAIN = f"terraquest-pack-content-v{PACK_CONTENT_HASH_VERSION}\0"

# Discovery fields folded into the pack fingerprint when present.
_DISCOVERY_HASH_KEYS = (
    "selected_by_generator",
    "quotas",
    "min_spacing_km",
    "grid_res_deg",
    "catalog_schema_version",
    "generators_run",
    "spacing_by_generator",
)


def discovery_stats_for_hash(stats_or_blob: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize discovery stats for ``pack_content_hash``.

    Accepts either:
    - the discovery stats dict (any of the hashed discovery keys), or
    - a full ``build_stats.json`` blob (uses ``.discovery``).

    When a blob looks like ``build_stats.json`` (has ``discovery`` plus
    ``osm`` / ``dem_tiles`` / ``content_hash`` / ``layer_digests`` /
    ``pack_content_hash_version``), prefer ``.discovery`` even if a misleading
    top-level discovery key is present.
    """
    if not stats_or_blob:
        return {}
    discovery = stats_or_blob.get("discovery")
    looks_like_build_stats = isinstance(discovery, dict) and (
        "osm" in stats_or_blob
        or "dem_tiles" in stats_or_blob
        or "content_hash" in stats_or_blob
        or "layer_digests" in stats_or_blob
        or "pack_content_hash_version" in stats_or_blob
    )
    if looks_like_build_stats:
        assert isinstance(discovery, dict)
        return discovery
    if any(k in stats_or_blob for k in _DISCOVERY_HASH_KEYS):
        return stats_or_blob
    if isinstance(discovery, dict):
        return discovery
    return {}


def discovery_payload_for_hash(discovery: dict[str, Any]) -> dict[str, Any]:
    """Stable subset of discovery stats included in the pack fingerprint."""
    out: dict[str, Any] = {}
    for key in _DISCOVERY_HASH_KEYS:
        if key not in discovery:
            continue
        val = discovery[key]
        if key == "generators_run" and isinstance(val, list):
            out[key] = sorted(str(x) for x in val)
        else:
            out[key] = val
    return out


def layer_file_digests(layers_dir: Path) -> dict[str, str]:
    """Return ``{filename: full sha256 hex}`` for every ``*.geojson`` under layers."""
    digests: dict[str, str] = {}
    for path in sorted(layers_dir.glob("*.geojson")):
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def pack_content_hash(layers_dir: Path, stats: dict[str, Any] | None = None) -> str:
    """Hash all layer GeoJSON bytes + discovery knobs (pack-content v2).

    ``stats`` may be discovery stats or a full ``build_stats.json`` blob
    (see ``discovery_stats_for_hash`` / RFC-0003).

    Returns a 16-hex digest (SHA-256 truncated) for ``pack.yaml`` / DuckDB /
    eval pin compatibility.
    """
    discovery = discovery_stats_for_hash(stats)
    payload = discovery_payload_for_hash(discovery)
    h = hashlib.sha256()
    h.update(_PACK_CONTENT_DOMAIN.encode())
    for path in sorted(layers_dir.glob("*.geojson")):
        h.update(path.name.encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    # allow_nan=False: reject NaN/Inf so fingerprints stay portable JSON.
    h.update(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
    return h.hexdigest()[:16]
