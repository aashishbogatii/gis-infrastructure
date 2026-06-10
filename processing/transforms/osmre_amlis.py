"""OSMRE e-AMLIS abandoned-mine problem areas

Reads the GeoJSON point layer directly via GDAL's GeoJSON driver. 
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

FILE_GLOB = "Problem_Status*.geojson"

KEEP = {
    "AMLIS_KEY": "amlis_key",
    "PROB_TY_NAME": "problem_type",
    "PROGRAM": "program",
    "PU_NAME": "planning_unit",
    "PA_NAME": "problem_area",
    "COUNTY": "county",
    "STATUS0": "reclamation_status",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    files = storage.list_vintage_files(raw_root, as_of, FILE_GLOB)
    if not files:
        raise FileNotFoundError(f"No {FILE_GLOB} in {source_uri}")
    name = sorted(files)[0]

    uri = storage.gdal_uri(raw_root, as_of, name)
    logger.info(f"reading {name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
