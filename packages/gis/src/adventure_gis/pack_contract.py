"""Shared Region Pack on-disk contract helpers (RFC-0003)."""

from __future__ import annotations

# Canonical keys for production pack.yaml ``layers:`` maps (builder + validate).
REQUIRED_PACK_LAYER_KEYS: tuple[str, ...] = (
    "settlements",
    "water",
    "road_nodes",
    "road_lines",
    "peaks",
    "viewpoints",
    "catalog",
    "elevation",
)

# Optional layers: allowed in the map when present on disk; never required.
OPTIONAL_PACK_LAYER_KEYS: tuple[str, ...] = ("sentinel_indices", "vlm_features")


def default_layers_map() -> dict[str, str]:
    """Relative paths written by ``build_pack`` for each required layer key."""
    return {key: f"layers/{key}.geojson" for key in REQUIRED_PACK_LAYER_KEYS}
