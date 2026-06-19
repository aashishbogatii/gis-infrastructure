"""Proximity runner — APN -> probe every registry source -> {apn, matches[]}.

Looks up the parcel once by normalized APN, then probes each source with that
constant geometry and collects the matches into one response.

Run:  python -m proximity.runner <APN>
"""
from __future__ import annotations

import json
import sys
import time

from . import backends, query
from .registry import list_sources

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
    con = backends.connect()
    parcel_row = fetch_parcel_row(con, apn)

    matches: list[dict] = []
    for source in list_sources():
        rel = backends.source_relation(con, source)
        rows = con.execute(query.proximity_sql(source, rel), [parcel_row[0]]).fetchall()
        for r in rows:
            d = dict(zip(_COLS, r))
            d["attributes"] = json.loads(d["attributes"]) if d["attributes"] else {}
            matches.append(d)

    return {
        "apn": apn,
        "county_name": parcel_row[2],
        "fullstreetaddress": parcel_row[3],
        "matches": matches
    }


if __name__ == "__main__":
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
