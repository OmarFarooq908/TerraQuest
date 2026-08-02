"""Pack builder unit tests (offline — no network)."""

from adventure_core.pack_manifest import PackManifest
from adventure_packbuilder.dem import dem_tile_urls
from adventure_packbuilder.osm import build_overpass_query, overpass_to_layers


def test_overpass_query_contains_bbox():
    q = build_overpass_query([75.35, 35.20, 75.75, 35.50])
    assert "35.2" in q.replace("35.20", "35.2") or "35.20" in q
    assert "place" in q
    # first slice is places; peaks/water live in later slices
    assert "timeout" in q


def test_dem_tile_urls_for_skardu_bbox():
    urls = dem_tile_urls([75.35, 35.20, 75.75, 35.50])
    assert len(urls) >= 1
    assert any("N35" in name and "E075" in name for name, _ in urls)


def test_overpass_to_layers_parses_minimal_payload():
    payload = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lon": 75.5,
                "lat": 35.3,
                "tags": {"place": "town", "name": "Skardu"},
            },
            {
                "type": "way",
                "id": 2,
                "center": {"lon": 75.55, "lat": 35.32},
                "tags": {"natural": "water", "name": "Satpara"},
            },
            {
                "type": "way",
                "id": 3,
                "center": {"lon": 75.6, "lat": 35.35},
                "tags": {"highway": "track"},
            },
        ]
    }
    layers = overpass_to_layers(payload)
    assert len(layers["settlements"]["features"]) == 1
    assert len(layers["water"]["features"]) == 1
    assert len(layers["road_nodes"]["features"]) == 1


def test_skardu_config_loads():
    from adventure_packbuilder import load_build_config

    cfg = load_build_config("skardu_v1")
    assert isinstance(cfg, PackManifest)
    assert cfg.synthetic is False
    assert cfg.pack_id == "skardu_v1"
    assert cfg.osm.get("method") == "geofabrik"
    assert "generators" in (cfg.discovery or {})


def test_geofabrik_geojson_to_layers():
    from adventure_packbuilder.geofabrik import geojson_to_layers

    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [75.5, 35.3]},
                "properties": {"@id": 1, "@type": "node", "place": "town", "name": "Skardu"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[75.5, 35.3], [75.6, 35.31]],
                },
                "properties": {"@id": 2, "@type": "way", "highway": "track"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[75.55, 35.32], [75.56, 35.32], [75.56, 35.33], [75.55, 35.32]]
                    ],
                },
                "properties": {"@id": 3, "@type": "way", "natural": "water", "name": "Satpara"},
            },
        ],
    }
    layers = geojson_to_layers(fc)
    assert len(layers["settlements"]["features"]) == 1
    assert len(layers["road_nodes"]["features"]) == 1
    assert len(layers["water"]["features"]) == 1
    assert layers["water"]["features"][0]["geometry"]["type"] == "Point"
