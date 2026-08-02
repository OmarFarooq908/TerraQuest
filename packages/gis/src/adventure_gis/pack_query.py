"""Derived DuckDB query layer over Region Pack GeoJSON (RFC-0004 / issue #20).

GeoJSON under ``layers/`` remains the source of truth. ``query.duckdb`` is
regenerated from those files and pinned to ``pack_content_hash``.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from adventure_core.config import load_pack_manifest

from adventure_gis.pack_hash import pack_content_hash

DUCKDB_SCHEMA_VERSION = "1"
QUERY_DB_NAME = "query.duckdb"
_META_TABLE = "_pack_meta"

# Soft deny-list for statement leads (read-only connection is the hard guarantee).
_BLOCKED_SQL_LEADS = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "COPY",
        "ATTACH",
        "DETACH",
        "TRUNCATE",
        "REPLACE",
        "MERGE",
        "VACUUM",
        "EXPORT",
        "IMPORT",
        "LOAD",
        "INSTALL",
        "FORCE",
        "CHECKPOINT",
    }
)


class PackQueryError(RuntimeError):
    """Derived query DB missing, stale, or SQL failed."""


def query_db_path(pack_dir: Path) -> Path:
    return pack_dir / QUERY_DB_NAME


def pack_fingerprint_for_db(pack_dir: Path) -> str:
    """Hash used to decide whether ``query.duckdb`` is stale."""
    layers = pack_dir / "layers"
    stats_path = pack_dir / "build_stats.json"
    stats: dict[str, Any] | None = None
    if stats_path.is_file():
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
    return pack_content_hash(layers, stats)


def _strip_leading_sql_comments(sql: str) -> str:
    s = sql.strip()
    while s:
        if s.startswith("--"):
            s = s.split("\n", 1)[1].strip() if "\n" in s else ""
            continue
        if s.startswith("/*"):
            end = s.find("*/")
            if end < 0:
                return ""
            s = s[end + 2 :].strip()
            continue
        break
    return s


def _assert_readonly_sql(sql: str) -> str:
    """Normalize SQL and reject obvious writes / multi-statements."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise PackQueryError("empty SQL")
    # Disallow multi-statement batches (second statement could be a write).
    if ";" in stripped:
        raise PackQueryError("multi-statement SQL is not allowed via pack query")
    body = _strip_leading_sql_comments(stripped)
    if not body:
        raise PackQueryError("empty SQL")
    lead = body.split(None, 1)[0].upper()
    # WITH … INSERT/DELETE/etc.
    if lead == "WITH" and re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|MERGE|COPY)\b",
        body,
        flags=re.IGNORECASE,
    ):
        raise PackQueryError("write/DDL statements are not allowed via pack query (WITH … write)")
    if lead in _BLOCKED_SQL_LEADS:
        raise PackQueryError(f"write/DDL statements are not allowed via pack query ({lead})")
    return stripped


def _load_feature_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    features = raw.get("features") or []
    rows: list[dict[str, Any]] = []
    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        geom = feat.get("geometry") or {}
        gtype = str(geom.get("type") or "")
        coords = geom.get("coordinates")
        lon: float | None = None
        lat: float | None = None
        if gtype == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
            try:
                lon = float(coords[0])
                lat = float(coords[1])
            except (TypeError, ValueError):
                lon, lat = None, None
        elif (
            gtype == "LineString"
            and isinstance(coords, list)
            and coords
            and isinstance(coords[0], (list, tuple))
            and len(coords[0]) >= 2
        ):
            # Representative vertex (first) for line layers — not a centroid.
            try:
                lon = float(coords[0][0])
                lat = float(coords[0][1])
            except (TypeError, ValueError, IndexError):
                lon, lat = None, None
        fid = str(props.get("id") or f"{path.stem}_{i}")
        rows.append(
            {
                "id": fid,
                "name": str(props.get("name") or fid),
                "lon": lon,
                "lat": lat,
                "generator": str(props.get("generator") or "") or None,
                "properties": json.dumps(props, sort_keys=True),
                "geometry_type": gtype or None,
            }
        )
    return rows


def materialize_pack_db(
    pack_ref: str,
    *,
    force: bool = False,
) -> Path:
    """Build or refresh ``query.duckdb`` for a pack. Returns the DB path."""
    manifest, pack_dir = load_pack_manifest(pack_ref)
    db_path = query_db_path(pack_dir)
    fingerprint = pack_fingerprint_for_db(pack_dir)

    if db_path.is_file() and not force:
        try:
            meta = read_pack_db_meta(db_path)
            if (
                meta.get("content_hash") == fingerprint
                and meta.get("duckdb_schema_version") == DUCKDB_SCHEMA_VERSION
            ):
                return db_path
        except PackQueryError:
            pass

    layers_dir = pack_dir / "layers"
    if not layers_dir.is_dir():
        raise PackQueryError(f"missing layers directory: {layers_dir}")

    tmp_path = db_path.with_suffix(".duckdb.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    con = duckdb.connect(str(tmp_path))
    try:
        for geojson in sorted(layers_dir.glob("*.geojson")):
            table = geojson.stem
            # Guard against odd filenames
            if not table.isidentifier() or table.startswith("_"):
                continue
            rows = _load_feature_rows(geojson)
            con.execute(f'DROP TABLE IF EXISTS "{table}"')
            con.execute(
                f"""
                CREATE TABLE "{table}" (
                  id VARCHAR,
                  name VARCHAR,
                  lon DOUBLE,
                  lat DOUBLE,
                  generator VARCHAR,
                  properties JSON,
                  geometry_type VARCHAR
                )
                """
            )
            if rows:
                con.executemany(
                    f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [
                        (
                            r["id"],
                            r["name"],
                            r["lon"],
                            r["lat"],
                            r["generator"],
                            r["properties"],
                            r["geometry_type"],
                        )
                        for r in rows
                    ],
                )

        con.execute(f'DROP TABLE IF EXISTS "{_META_TABLE}"')
        con.execute(
            f"""
            CREATE TABLE "{_META_TABLE}" (
              pack_id VARCHAR,
              content_hash VARCHAR,
              feature_schema_version VARCHAR,
              materialized_at VARCHAR,
              duckdb_schema_version VARCHAR
            )
            """
        )
        con.execute(
            f'INSERT INTO "{_META_TABLE}" VALUES (?, ?, ?, ?, ?)',
            [
                manifest.pack_id,
                fingerprint,
                manifest.feature_schema_version,
                datetime.now(UTC).isoformat(),
                DUCKDB_SCHEMA_VERSION,
            ],
        )
    except Exception:
        con.close()
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    else:
        con.close()
        tmp_path.replace(db_path)
    return db_path


def read_pack_db_meta(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        raise PackQueryError(f"missing query db: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        try:
            row = con.execute(f'SELECT * FROM "{_META_TABLE}" LIMIT 1').fetchone()
            cols = [c[0] for c in con.description]
        except duckdb.Error as exc:
            raise PackQueryError(f"query db missing {_META_TABLE}: {exc}") from exc
        if not row:
            raise PackQueryError(f"query db {_META_TABLE} is empty")
        return dict(zip(cols, row, strict=True))
    finally:
        con.close()


def connect_pack_db(pack_ref: str, *, force_materialize: bool = False) -> duckdb.DuckDBPyConnection:
    """Materialize if needed and return a read-only DuckDB connection."""
    _, pack_dir = load_pack_manifest(pack_ref)
    db_path = materialize_pack_db(pack_ref, force=force_materialize)
    # Re-check staleness after concurrent writers
    fingerprint = pack_fingerprint_for_db(pack_dir)
    meta = read_pack_db_meta(db_path)
    if meta.get("content_hash") != fingerprint:
        db_path = materialize_pack_db(pack_ref, force=True)
    return duckdb.connect(str(db_path), read_only=True)


def execute_pack_sql(
    pack_ref: str,
    sql: str,
    *,
    force_materialize: bool = False,
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Run read-only SQL against the pack DB. Returns (column_names, rows)."""
    stripped = _assert_readonly_sql(sql)
    con = connect_pack_db(pack_ref, force_materialize=force_materialize)
    try:
        result = con.execute(stripped)
        cols = [c[0] for c in result.description] if result.description else []
        rows = result.fetchall()
        return cols, rows
    except duckdb.Error as exc:
        msg = str(exc)
        if "read-only" in msg.lower():
            raise PackQueryError(
                "pack query connections are read-only; rebuild with "
                "`adventurectl pack materialize` if the DB is stale"
            ) from exc
        raise PackQueryError(msg) from exc
    finally:
        con.close()


def catalog_label_join_counts(
    pack_ref: str,
    labels: list[dict[str, Any]],
) -> dict[str, int]:
    """Join in-DB catalog ids to label dicts that carry ``catalog_id``.

    Returns counts: matched, interesting_matched, catalog_rows, label_rows_with_id.
    """
    label_rows = [
        (str(lab["catalog_id"]), bool(lab.get("interesting")))
        for lab in labels
        if lab.get("catalog_id")
    ]
    con = connect_pack_db(pack_ref)
    try:
        con.execute("DROP TABLE IF EXISTS _eval_labels")
        con.execute("CREATE TEMP TABLE _eval_labels (catalog_id VARCHAR, interesting BOOLEAN)")
        if label_rows:
            con.executemany("INSERT INTO _eval_labels VALUES (?, ?)", label_rows)
        catalog_n = con.execute("SELECT count(*) FROM catalog").fetchone()[0]
        label_n = con.execute("SELECT count(*) FROM _eval_labels").fetchone()[0]
        matched = con.execute(
            """
            SELECT count(*) FROM catalog c
            INNER JOIN _eval_labels l ON c.id = l.catalog_id
            """
        ).fetchone()[0]
        interesting = con.execute(
            """
            SELECT count(*) FROM catalog c
            INNER JOIN _eval_labels l ON c.id = l.catalog_id
            WHERE l.interesting
            """
        ).fetchone()[0]
        return {
            "catalog_rows": int(catalog_n),
            "label_rows_with_id": int(label_n),
            "matched": int(matched),
            "interesting_matched": int(interesting),
        }
    finally:
        con.close()
