"""Proximity runner — APN -> probe every registry source -> {apn, matches[]}.

Looks up the parcel once by normalized APN, then probes each source with that
constant geometry and collects the matches into one response.

Run:  python -m proximity.runner <APN>
"""
from __future__ import annotations

import json
import logging
import sys
import time

from . import backends, query
from .logging_config import setup_logging
from .registry import list_sources

logger = logging.getLogger(__name__)

_COLS = ["source", "contained", "distance_m", "attributes"]


def normalize_apn(apn: str) -> str:
    return apn.replace("-", "").strip()


def fetch_parcel_row(con, apn: str) -> bytes:
    """The parcel geometry (WKB) for a normalized APN, or raise if not found."""
    row = con.execute(
        f"SELECT geometry, parcel_apn, countyname, fullstreetaddress FROM read_parquet('{backends.PARCEL_PATH}') "
        f"WHERE parcel_apn = ? LIMIT 1",
        [normalize_apn(apn)],
    ).fetchone()
    if row is None:
        raise KeyError(f"APN {apn!r} not found in parcel store")
    return row


def proximity(apn: str) -> dict:
    t0 = time.perf_counter()
    logger.info("proximity start apn=%s env=%s base=%s", apn, backends.ENV, backends.CURATED_BASE)

    con = backends.connect()
    parcel_row = fetch_parcel_row(con, apn)
    logger.info("parcel found apn=%s county=%s", apn, parcel_row[2])

    matches: list[dict] = []
    for source in list_sources():
        ts = time.perf_counter()
        rel = backends.source_relation(con, source)
        rows = con.execute(query.proximity_sql(source, rel), [parcel_row[0]]).fetchall()
        for r in rows:
            d = dict(zip(_COLS, r))
            d["attributes"] = json.loads(d["attributes"]) if d["attributes"] else {}
            matches.append(d)
        logger.info("source=%s rows=%d %.2fs", source.key, len(rows), time.perf_counter() - ts)

    logger.info("proximity done apn=%s matches=%d %.1fs", apn, len(matches), time.perf_counter() - t0)
    return {
        "apn": apn,
        "county_name": parcel_row[2],
        "fullstreetaddress": parcel_row[3],
        "matches": matches
    }


if __name__ == "__main__":
    setup_logging()
    apn = sys.argv[1]
    t = time.perf_counter()
    result = proximity(apn)
    print(json.dumps(result, indent=2, default=str))
    print(
        f"\n{len(result['matches'])} matches across "
        f"{len({m['source'] for m in result['matches']})} sources "
        f"in {time.perf_counter() - t:.1f}s",
        file=sys.stderr,
    )
