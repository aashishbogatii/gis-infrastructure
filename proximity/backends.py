"""S3 (file) backend — turn a registry Source into a queryable relation.

Reads curated parquet directly (s3:// in prod, local path in dev) and resolves
the latest dated vintage partition. Geometry is WKB → decoded to a `geom`
column (GEOMETRY, EPSG:4326). Emits a parenthesized SELECT of `<attributes>, geom`
that the proximity query consumes.

Single S3 backend, so this is plain module-level functions (no class).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb

from .registry import Source

# Load proximity/.env in dev (if python-dotenv is available); harmless otherwise.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"), override=False)
except ImportError:
    pass

# Environment switch: dev -> local disk, prod -> S3.
ENV = os.getenv("ENV", "dev").lower()
DEV_BASE = os.getenv("CURATED_DEV_BASE", "D:/curated")
PROD_BASE = os.getenv("CURATED_PROD_BASE", "s3://low-appeal-agents-us-gis-data/curated")
CURATED_BASE = (PROD_BASE if ENV == "prod" else DEV_BASE).rstrip("/")
IS_S3 = CURATED_BASE.startswith("s3://")

# Parcel store (the dimension every request looks up by APN).
DEV_PARCEL = os.getenv("PARCEL_DEV", "D:/parcels/california/ca_parcels.parquet")
PROD_PARCEL = os.getenv("PARCEL_PROD", "s3://low-appeal-agents-us-gis-data/parcels/California/ca_parcels.parquet")
PARCEL_PATH = PROD_PARCEL if ENV == "prod" else DEV_PARCEL

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR = re.compile(r"^(\d{4})(?:[-_].*)?$")   # year-only or YYYY_YYYY ranges (dev divergence)

# Memoized latest-vintage resolution, keyed by (schema, table).
_LATEST_CACHE: dict[tuple[str, str], str] = {}


def _cols(source: Source) -> str:
    return ", ".join(source.columns)   # attributes (feature) or group_by (count)


def _partition_key(name: str) -> str | None:
    """A comparable sort key for a partition dir. ISO dates sort as-is; non-ISO
    (year-only, YYYY_YYYY) normalize to the first day of the year — mirroring the
    dev runner's tolerance. Returns None if uninterpretable as a date."""
    if _ISO.match(name):
        return name
    m = _YEAR.match(name)
    if m:
        return f"{m.group(1)}-01-01"
    return None


# Where the Lambda layer drops the bundled .duckdb_extension files (build_layer.sh
# zips them under python/, which Lambda mounts at /opt/python). Locally this dir
# won't exist, so we fall back to INSTALL (downloads from extensions.duckdb.org).
_EXT_DIR = os.getenv("DUCKDB_EXTENSION_DIR", "/opt/python")


def _load_extension(con: duckdb.DuckDBPyConnection, name: str) -> None:
    """LOAD a bundled extension by path on Lambda; INSTALL+LOAD in local dev."""
    bundled = Path(_EXT_DIR) / f"{name}.duckdb_extension"
    if bundled.exists():
        con.execute(f"LOAD '{bundled.as_posix()}';")   # offline: signed file from the layer
    else:
        con.execute(f"INSTALL {name}; LOAD {name};")    # local dev: pull from the network


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    _load_extension(con, "spatial")
    if IS_S3:
        _load_extension(con, "httpfs")
        con.execute("CREATE SECRET (TYPE s3, PROVIDER credential_chain);")
    return con


def resolve_latest(con, schema: str, table: str) -> str:
    """Newest as_of partition under CURATED_BASE/schema/table (cached per process)."""
    key = (schema, table)
    if key in _LATEST_CACHE:
        return _LATEST_CACHE[key]

    pattern = f"{CURATED_BASE}/{schema}/{table}/*/{table}.parquet"   # canonical per-vintage file
    files = [r[0] for r in con.execute("SELECT file FROM glob(?)", [pattern]).fetchall()]
    candidates = []                            # (sort_key, as_of_dir)
    for path in files:
        as_of = path.replace("\\", "/").split("/")[-2]
        sort_key = _partition_key(as_of)
        if sort_key:
            candidates.append((sort_key, as_of))
    if not candidates:
        raise FileNotFoundError(f"no dated partitions under {CURATED_BASE}/{schema}/{table}")
    latest = max(candidates)[1]
    _LATEST_CACHE[key] = latest
    return latest


def source_path(con, source: Source) -> str:
    as_of = resolve_latest(con, source.schema, source.table)
    return f"{CURATED_BASE}/{source.schema}/{source.table}/{as_of}/{source.table}.parquet"


def source_relation(con, source: Source) -> str:
    """Parenthesized SELECT yielding `<attributes>, geom` (GEOMETRY 4326)."""
    path = source_path(con, source)
    where = f" WHERE {source.filter}" if source.filter else ""
    return (
        f"(SELECT {_cols(source)}, ST_GeomFromWKB(geometry) AS geom "
        f"FROM read_parquet('{path}'){where})"
    )


if __name__ == "__main__":
    from .registry import list_sources

    print(f"ENV={ENV}  base={CURATED_BASE}")
    con = connect()
    for s in list_sources():
        try:
            print(f"{s.key:28} latest={resolve_latest(con, s.schema, s.table)}")
        except FileNotFoundError as e:
            print(f"{s.key:28} {e}")
