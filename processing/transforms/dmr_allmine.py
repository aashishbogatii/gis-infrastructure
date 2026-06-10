"""CA DOC DMR All Mines

Mine sites regulated under SMARA (Dept. of Conservation, Division of Mine
Reclamation) — proximity to an active/abandoned mine is the value signal. A
polygon shapefile read in place from inside the zip via GDAL's /vsizip/; keeps
the mine identity, status, product, and disturbed/permitted acreage.
"""
from __future__ import annotations

import geopandas as gpd

import logging

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "DMR_All_Mines*.zip"
INNER = "DMR_All_Mines.shp"

KEEP = {
    "Mine_ID": "mine_id",
    "Mine_Name": "mine_name",
    "Acres_Dist": "acres_disturbed",
    "MineStatus": "mine_status",
    "Operator": "operator",
    "PriProduct": "primary_product",
    "PermitAcre": "permit_acres",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=INNER)
    logger.info(f"reading from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)