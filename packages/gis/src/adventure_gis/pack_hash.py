"""Content hash for Region Pack layer directories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def pack_content_hash(layers_dir: Path, stats: dict | None = None) -> str:
    """Hash all layer GeoJSON bytes + selected generator counts."""
    stats = stats or {}
    h = hashlib.sha256()
    for path in sorted(layers_dir.glob("*.geojson")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    h.update(json.dumps(stats.get("selected_by_generator", {}), sort_keys=True).encode())
    return h.hexdigest()[:16]
