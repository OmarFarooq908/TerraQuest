"""Content hash for Region Pack layer directories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def discovery_stats_for_hash(stats_or_blob: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize discovery stats for ``pack_content_hash``.

    Accepts either:
    - the discovery stats dict (has ``selected_by_generator``), or
    - a full ``build_stats.json`` blob (uses ``.discovery``).

    When a blob looks like ``build_stats.json`` (has ``discovery`` plus
    ``osm`` / ``dem_tiles`` / ``content_hash``), prefer ``.discovery`` even if a
    misleading top-level ``selected_by_generator`` key is present.
    """
    if not stats_or_blob:
        return {}
    discovery = stats_or_blob.get("discovery")
    looks_like_build_stats = isinstance(discovery, dict) and (
        "osm" in stats_or_blob or "dem_tiles" in stats_or_blob or "content_hash" in stats_or_blob
    )
    if looks_like_build_stats:
        return discovery
    if "selected_by_generator" in stats_or_blob:
        return stats_or_blob
    if isinstance(discovery, dict):
        return discovery
    return {}


def pack_content_hash(layers_dir: Path, stats: dict[str, Any] | None = None) -> str:
    """Hash all layer GeoJSON bytes + selected generator counts.

    ``stats`` may be discovery stats or a full ``build_stats.json`` blob
    (see ``discovery_stats_for_hash`` / RFC-0003).
    """
    discovery = discovery_stats_for_hash(stats)
    h = hashlib.sha256()
    for path in sorted(layers_dir.glob("*.geojson")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    h.update(json.dumps(discovery.get("selected_by_generator", {}), sort_keys=True).encode())
    return h.hexdigest()[:16]
