"""Derived DuckDB pack query layer (RFC-0004 / issue #20)."""

from __future__ import annotations

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
    if db.exists():
        db.unlink()
    yield
    if db.exists():
        db.unlink()


def test_materialize_and_query_fixture(_clean_fixture_db: None) -> None:
    path = materialize_pack_db(FIXTURE, force=True)
    assert path.is_file()
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
