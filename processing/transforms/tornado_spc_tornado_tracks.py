"""NOAA SPC Tornado Tracks (1950-2025)

Reads the track line layer straight from the shapefile *inside the zip*, in
place, via GDAL's ``/vsizip/`` virtual filesystem.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "*torn-aspath.zip"

# Tornado id, date, state, magnitude (scoring) + impact evidence (casualties,
# loss, track dimensions); drop split date/time parts and the start/end
# lat-lon pairs (the track geometry already carries the path).
# Selected and renamed to STTM target names.
KEEP = {
    "om": "om",                # tornado id
    "date": "event_date",
    "st": "state",
    "mag": "magnitude",        # (E)F scale
    "inj": "injuries",
    "fat": "fatalities",
    "loss": "loss",
    "len": "track_len_mi",
    "wid": "track_wid_yd",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # The shapefile lives in a folder named like the zip stem,
    # e.g. 1950-2025-torn-aspath/1950-2025-torn-aspath.shp
    stem = Path(zip_name).stem
    inner = f"{stem}/{stem}.shp"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {stem}.shp from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
