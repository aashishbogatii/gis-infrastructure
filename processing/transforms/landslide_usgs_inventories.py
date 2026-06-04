"""USGS US Landslide Inventory v3 — nationwide.

Reads the polygon layer ``us_ls_v3_poly`` straight from the shapefile *inside
the zip*, in place, via GDAL's ``/vsizip/`` virtual filesystem.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "US_Landslide_*.zip"
SHP = "us_ls_v3_poly.shp"


KEEP = [
    "USGS_ID",      # inventory feature id
    "Date_Min",     # earliest possible event date
    "Date_Max",     # latest possible event date
    "Fatalities",
    "Confidence",   # mapping confidence
    "LS_Type",      # slide / flow / fall / ...
    "Inventory",    # contributing source inventory
    "Inv_URL",
]


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    inner = f"{Path(zip_name).stem}/{SHP}"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {SHP} from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    keep = [c for c in KEEP if c in gdf.columns]
    logger.debug(f"kept {len(keep)} of {len(KEEP)} columns")
    return gdf[keep + [gdf.geometry.name]]
