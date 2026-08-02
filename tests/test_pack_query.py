"""Derived DuckDB pack query layer (RFC-0004 / issue #20)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from adventure_cli.main import app
from adventure_core.evaluation import load_place_labels
from adventure_gis.pack_query import (
    PackQueryError,
    catalog_label_join_counts,
    execute_pack_sql,
    materialize_pack_db,
    pack_fingerprint_for_db,
    query_db_path,
    read_pack_db_meta,
)
from typer.testing import CliRunner

FIXTURE = "fixtures/karakoram_mini"
runner = CliRunner()


@pytest.fixture()
def _clean_fixture_db() -> None:
    db = query_db_path(Path(FIXTURE))
    tmp = db.with_suffix(".duckdb.tmp")
    for p in (db, tmp):
        if p.exists():
            p.unlink()
    yield
    for p in (db, tmp):
        if p.exists():
            p.unlink()


def test_materialize_and_query_fixture(_clean_fixture_db: None) -> None:
    path = materialize_pack_db(FIXTURE, force=True)
    assert path.is_file()
    assert not path.with_suffix(".duckdb.tmp").exists()
    meta = read_pack_db_meta(path)
    assert meta["pack_id"] == "karakoram_mini"
    assert meta["content_hash"] == pack_fingerprint_for_db(Path(FIXTURE))
    assert meta["duckdb_schema_version"] == "1"

    cols, rows = execute_pack_sql(
        FIXTURE, "SELECT generator, count(*) AS n FROM catalog GROUP BY 1 ORDER BY n DESC"
    )
    assert "generator" in cols and "n" in cols
    assert rows
    total = sum(int(r[1]) for r in rows)
    assert total == 13


def test_materialize_skips_when_fresh(_clean_fixture_db: None) -> None:
    p1 = materialize_pack_db(FIXTURE, force=True)
    mtime1 = p1.stat().st_mtime_ns
    p2 = materialize_pack_db(FIXTURE, force=False)
    assert p1 == p2
    assert p2.stat().st_mtime_ns == mtime1


def test_query_rejects_writes(_clean_fixture_db: None) -> None:
    materialize_pack_db(FIXTURE, force=True)
    with pytest.raises(PackQueryError, match="not allowed"):
        execute_pack_sql(FIXTURE, "DELETE FROM catalog")


def test_query_rejects_with_insert_and_multistatement(_clean_fixture_db: None) -> None:
    materialize_pack_db(FIXTURE, force=True)
    with pytest.raises(PackQueryError, match="not allowed|WITH"):
        execute_pack_sql(
            FIXTURE,
            "WITH x AS (SELECT 1) INSERT INTO catalog SELECT * FROM catalog LIMIT 0",
        )
    with pytest.raises(PackQueryError, match="multi-statement"):
        execute_pack_sql(FIXTURE, "SELECT 1; DELETE FROM catalog")
    with pytest.raises(PackQueryError, match="not allowed"):
        execute_pack_sql(FIXTURE, "/* c */ DELETE FROM catalog")


def test_stale_db_rebuilds_after_layer_change(tmp_path: Path) -> None:
    """Copy fixture pack so we can mutate layers without touching the repo."""
    import shutil

    dest = tmp_path / "pack"
    shutil.copytree(FIXTURE, dest)
    db = materialize_pack_db(str(dest), force=True)
    meta1 = read_pack_db_meta(db)
    catalog = dest / "layers" / "catalog.geojson"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    data["features"].append(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [75.0, 35.5]},
            "properties": {
                "id": "extra_qa",
                "name": "QA Extra",
                "generator": "synthetic_fixture",
            },
        }
    )
    catalog.write_text(json.dumps(data), encoding="utf-8")
    assert pack_fingerprint_for_db(dest) != meta1["content_hash"]
    db2 = materialize_pack_db(str(dest), force=False)
    meta2 = read_pack_db_meta(db2)
    assert meta2["content_hash"] == pack_fingerprint_for_db(dest)
    _, rows = execute_pack_sql(str(dest), "SELECT count(*) FROM catalog")
    assert rows[0][0] == 14


def test_catalog_label_join_counts(_clean_fixture_db: None) -> None:
    labels = load_place_labels(Path("evaluation/fixtures/karakoram_mini"))
    counts = catalog_label_join_counts(FIXTURE, [lab.model_dump() for lab in labels])
    assert counts["catalog_rows"] == 13
    assert counts["label_rows_with_id"] >= 1
    assert counts["matched"] >= 1
    assert counts["interesting_matched"] >= 1


def test_cli_pack_query(_clean_fixture_db: None) -> None:
    result = runner.invoke(
        app,
        [
            "pack",
            "query",
            "--pack",
            FIXTURE,
            "--sql",
            "SELECT count(*) AS n FROM catalog",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert '"n"' in result.stdout
    assert "13" in result.stdout
