"""The one layer that knows *where* data lives — local disk or S3.

Every function checks `config.IS_CLOUD` and does the right thing for that
backend, so the rest of the code doesn't care which one is active:

    dev  -> local files under RAW_BASE / CURATED_BASE
    prod -> S3 (read in place via GDAL /vsis3/, written with s3fs)

Folder layout is the same in both:

    <base>/<raw_root>/<as_of>/<files>          # local
    s3://<bucket>/<prefix>/<raw_root>/<as_of>/...  # cloud
"""
import logging

logger = logging.getLogger(__name__)

import fnmatch
import json
import re
from datetime import date
from pathlib import Path

from . import config

# Vintage folder names we understand.
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")        # 2026-04-29
_YEAR = re.compile(r"^\d{4}$")                     # 2026


def parse_partition(name: str) -> date | None:
    """Turn a vintage folder name into a date for sorting, or None if it
    doesn't look like a date."""
    if _ISO.match(name):
        try:
            return date.fromisoformat(name)
        except ValueError:
            return None
    if _YEAR.match(name):
        return date(int(name), 1, 1)
    return None


# S3 client. Imported lazily so local dev doesn't need s3fs installed.
def _fs():
    import s3fs

    return s3fs.S3FileSystem()


def _raw_key(raw_root: str, as_of: str | None = None) -> str:
    parts = [p for p in (config.S3_RAW_PREFIX, raw_root.strip("/")) if p]
    key = "/".join(parts)
    return f"{key}/{as_of}" if as_of else key


def _curated_key(schema: str, table: str, as_of: str, filename: str) -> str:
    parts = [
        p
        for p in (config.S3_CURATED_PREFIX, schema, table, as_of, filename)
        if p
    ]
    return "/".join(parts)


def raw_uri(raw_root: str, as_of: str) -> str:
    """Where a vintage lives, as a readable string (used in log lines)."""
    if config.IS_CLOUD:
        return f"s3://{config.S3_RAW_BUCKET}/{_raw_key(raw_root, as_of)}"
    return str(config.RAW_BASE / raw_root / as_of)


def list_partitions(raw_root: str) -> list[str]:
    if config.IS_CLOUD:
        prefix = f"{config.S3_RAW_BUCKET}/{_raw_key(raw_root)}"
        return [Path(p).name for p in _fs().ls(prefix)]
    base = config.RAW_BASE / raw_root
    if not base.exists():
        raise FileNotFoundError(f"Raw root not found: {base}")
    return [p.name for p in base.iterdir() if p.is_dir()]


def resolve_as_of(raw_root: str, *, pin: str | None = None) -> str:
    """Pick which vintage to use: the pinned one if given, else the newest
    date-like folder found."""
    if pin:
        logger.debug(f"using pinned as_of={pin} for {raw_root}")
        return pin
    parts = list_partitions(raw_root)
    dated = [(parse_partition(n), n) for n in parts]
    dated = [(d, n) for d, n in dated if d is not None]
    if not dated:
        raise FileNotFoundError(
            f"No date-like partitions under {raw_uri(raw_root, '')} "
            f"(found: {sorted(parts)})"
        )
    dated.sort()
    chosen = dated[-1][1]
    logger.debug(
        f"resolved as_of={chosen} from {len(parts)} dir(s) in {raw_root}"
    )
    return chosen


def list_vintage_files(
    raw_root: str, as_of: str, glob: str = "*"
) -> list[str]:
    """List file names in a vintage folder, optionally filtered by a pattern
    like ``NFHL_*.zip``."""
    if config.IS_CLOUD:
        prefix = f"{config.S3_RAW_BUCKET}/{_raw_key(raw_root, as_of)}"
        names = [Path(p).name for p in _fs().ls(prefix)]
    else:
        d = config.RAW_BASE / raw_root / as_of
        names = [p.name for p in d.iterdir()]
    matched = fnmatch.filter(names, glob)
    logger.debug(
        f"{len(matched)} file(s) match '{glob}' in {raw_root}/{as_of}"
    )
    return matched


def read_manifest(raw_root: str, as_of: str) -> dict:
    """Read a vintage's ``_manifest.json``, or return {} if there isn't one."""
    if config.IS_CLOUD:
        key = (
            f"{config.S3_RAW_BUCKET}/"
            f"{_raw_key(raw_root, as_of)}/_manifest.json"
        )
        fs = _fs()
        if not fs.exists(key):
            return {}
        with fs.open(key) as f:
            return json.load(f)
    path = config.RAW_BASE / raw_root / as_of / "_manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def open_binary(raw_root: str, as_of: str, filename: str):
    """Open a raw file as a binary file-like object in either backend.

    For formats GDAL's vsi layer can't usefully expose (e.g. a KMZ whose
    attributes live in per-placemark description HTML), a transform needs the
    bytes directly. Returns a context-manager file object: a local handle in
    dev, an s3fs handle in prod.
    """
    if config.IS_CLOUD:
        key = f"{config.S3_RAW_BUCKET}/{_raw_key(raw_root, as_of)}/{filename}"
        return _fs().open(key, "rb")
    return open(config.RAW_BASE / raw_root / as_of / filename, "rb")


def gdal_uri(
    raw_root: str, as_of: str, filename: str, inner: str = ""
) -> str:
    """Build a path GDAL can open in either backend. On S3 it uses ``/vsis3/``
    to stream the file (no download); a ``.zip`` is wrapped in ``/vsizip/`` so
    a file ``inner`` the zip is read in place. Works for any GDAL format,
    including .csv/.xlsx, when read via gpd.read_file/pyogrio."""
    if config.IS_CLOUD:
        base = (
            f"/vsis3/{config.S3_RAW_BUCKET}/"
            f"{_raw_key(raw_root, as_of)}/{filename}"
        )
    else:
        base = str(config.RAW_BASE / raw_root / as_of / filename)

    if filename.lower().endswith(".zip"):
        p = base.replace("\\", "/")
        uri = f"/vsizip/{p}"
        return f"{uri}/{inner.strip('/')}" if inner else uri

    if inner:
        sep = base.replace("\\", "/")
        return f"{sep.rstrip('/')}/{inner.strip('/')}"
    return base


def curated_target(
    schema: str, table: str, as_of: str, filename: str | None = None
) -> str:
    """Where to write the curated output: a local path (dev) or s3:// uri
    (prod). Defaults the file name to ``<table>.parquet`` so it's named after
    the source, not something generic."""
    if filename is None:
        filename = f"{table}.parquet"
    if config.IS_CLOUD:
        key = _curated_key(schema, table, as_of, filename)
        return f"s3://{config.S3_CURATED_BUCKET}/{key}"
    return str(config.CURATED_BASE / schema / table / as_of / filename)


def ensure_parent(target: str) -> None:
    """Make sure the local output folder exists. Does nothing on S3, which
    has no real folders."""
    if not config.IS_CLOUD:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
