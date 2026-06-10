"""HIFLD Petroleum Refineries

Reads the ``Petroleum_Refinery`` point shapefile straight from *inside the zip*
via GDAL's ``/vsizip/`` virtual filesystem. The native point geometry is used
directly (the redundant Latitude/Longitude attribute columns are dropped).
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "petroleum-refineries*.zip"
INNER = "Petroleum_Refinery.shp"

KEEP = {
    "site_id": "site_id",
    "Company": "company",
    "Site": "site",
    "State": "state",
    "AD_Mbpd": "atmos_dist_mbpd",  # atmos. distillation capacity = size
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
