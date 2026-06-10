"""EPA LMOP landfill database

An Excel workbook; the data lives on the ``LMOP Database`` sheet (the
workbook also has ``Summary`` and ``Field Descriptions`` sheets, which we
ignore). Read in place via GDAL's XLSX driver. Point geometry is built from
``Latitude``/``Longitude`` columns; the runner keeps the EPSG:4326 points.
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage, tabular

logger = logging.getLogger(__name__)

FILE_GLOB = "landfilllmopdata*.xlsx"
SHEET = "LMOP Database"

KEEP = {
    "Landfill ID": "landfill_id",
    "Landfill Name": "landfill_name",
    "State": "state",
    "County": "county",
    "Year Landfill Opened": "year_opened",
    "Landfill Closure Year": "closure_year",
    "Current Landfill Status": "status",
    "Design Landfill Area (acres)": "area_acres",
    "Waste in Place (tons)": "waste_in_place_tons",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    files = storage.list_vintage_files(raw_root, as_of, FILE_GLOB)
    if not files:
        raise FileNotFoundError(f"No {FILE_GLOB} in {source_uri}")
    xlsx = sorted(files)[0]

    uri = storage.gdal_uri(raw_root, as_of, xlsx)
    logger.info(f"reading sheet '{SHEET}' from {xlsx}")

    return tabular.read_points(
        uri, keep=KEEP, lon_col="Longitude", lat_col="Latitude", layer=SHEET
    )
