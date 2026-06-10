"""HUD Low- and Moderate-Income Population by Block Group

Reads the block-group polygon shapefile straight from *inside the zip* via
GDAL's ``/vsizip/`` virtual filesystem.
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "LOW_MOD_INCOME*.zip"
INNER = "Low_to_Moderate_Income_Population_by_BG.shp"

KEEP = {
    "GEOID": "geoid",
    "Countyname": "county_name",
    "County": "county_fips",
    "Tract": "tract",
    "BLKGRP": "blkgrp",
    "Lowmod": "lowmod",
    "Lowmoduniv": "lowmod_universe",
    "Lowmod_pct": "lowmod_pct",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=INNER)
    logger.info(f"reading {INNER} from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
