"""GIS package: pack load, validate, generate candidates, derived query DB."""

from adventure_gis.candidates import generate_candidates
from adventure_gis.pack_contract import (
    OPTIONAL_PACK_LAYER_KEYS,
    REQUIRED_PACK_LAYER_KEYS,
    default_layers_map,
)
from adventure_gis.pack_data import PackData, load_pack_data
from adventure_gis.pack_hash import discovery_stats_for_hash, pack_content_hash
from adventure_gis.pack_query import (
    PackQueryError,
    catalog_label_join_counts,
    connect_pack_db,
    execute_pack_sql,
    materialize_pack_db,
    query_db_path,
)
from adventure_gis.pack_validate import validate_pack
from adventure_gis.sentinel import lookup_sentinel_indices

__all__ = [
    "PackData",
    "PackQueryError",
    "OPTIONAL_PACK_LAYER_KEYS",
    "REQUIRED_PACK_LAYER_KEYS",
    "catalog_label_join_counts",
    "connect_pack_db",
    "default_layers_map",
    "discovery_stats_for_hash",
    "execute_pack_sql",
    "generate_candidates",
    "load_pack_data",
    "lookup_sentinel_indices",
    "materialize_pack_db",
    "pack_content_hash",
    "query_db_path",
    "validate_pack",
]
