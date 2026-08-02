"""Deterministic GIS candidate generation from Region Pack fixtures."""

from adventure_gis.candidates import generate_candidates
from adventure_gis.pack_data import PackData, load_pack_data

__all__ = ["PackData", "load_pack_data", "generate_candidates"]
