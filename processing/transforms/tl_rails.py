"""Census TIGER/Line Rails

Reads the rail line shapefile straight from *inside the zip* via GDAL's
``/vsizip/`` virtual filesystem.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "tl_*_us_rails.zip"

KEEP = {
    "LINEARID": "linearid",
    "FULLNAME": "fullname",
    "MTFCC": "mtfcc",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # Shapefile is named like the zip stem, e.g. tl_2025_us_rails.shp
    inner = f"{Path(zip_name).stem}.shp"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {inner} from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
