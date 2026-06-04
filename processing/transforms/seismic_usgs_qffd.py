"""USGS Quaternary Faults and Fold Database

Reads the nationwide line layer ``SHP/Qfaults_US_Database.shp`` straight from
*inside the zip*, in place, via GDAL's ``/vsizip/`` virtual filesystem.
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "Qfaults*.zip"
INNER = "SHP/Qfaults_US_Database.shp"

# Fault identity + activity (age = recency, slip_rate/sense = activity);
# drop section bookkeeping, mapping scale, citation and symbology columns.
KEEP = [
    "fault_name",
    "fault_id",
    "age",          # Quaternary age class — recency
    "slip_rate",    # activity rate
    "slip_sense",
]


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

    keep = [c for c in KEEP if c in gdf.columns]
    logger.debug(f"kept {len(keep)} of {len(KEEP)} columns")
    return gdf[keep + [gdf.geometry.name]]
