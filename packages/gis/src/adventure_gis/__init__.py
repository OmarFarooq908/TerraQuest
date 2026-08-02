"""GIS package: pack load, validate, generate candidates."""

from adventure_gis.candidates import generate_candidates
from adventure_gis.pack_contract import REQUIRED_PACK_LAYER_KEYS, default_layers_map
from adventure_gis.pack_data import PackData, load_pack_data
from adventure_gis.pack_hash import discovery_stats_for_hash, pack_content_hash
from adventure_gis.pack_validate import validate_pack

__all__ = [
    "PackData",
    "REQUIRED_PACK_LAYER_KEYS",
    "default_layers_map",
    "load_pack_data",
    "generate_candidates",
    "discovery_stats_for_hash",
    "pack_content_hash",
    "validate_pack",
]
