"""CA SWRCB GAMA groundwater quality. Pattern B (distance decay).

Per-sample chemical results at monitoring wells from the Groundwater Ambient
Monitoring & Assessment program — proximity to a well with detections is the
value signal. Published as a flat CSV with no native geometry, so POINT geometry
is built from the gm_longitude / gm_latitude columns by tabular.read_points.
"""
from __future__ import annotations

import geopandas as gpd

import logging

from .. import storage
from .. import tabular

logger = logging.getLogger(__name__)

FILE_GLOB = "gama*.csv"

KEEP = {
    "gm_county_name": "county",
    "gm_well_category": "well_category",
    "gm_well_id": "well_id",
    "gm_chemical_name": "chemical_name",
    "gm_result": "result",
    "gm_chemical_units": "result_units",
    "gm_result_modifier": "result_modifier",
    "gm_reporting_limit": "reporting_limit",
    "gm_samp_collection_date": "sample_date"
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    files = storage.list_vintage_files(raw_root, as_of, FILE_GLOB)
    if not files:
        raise FileNotFoundError(f"No {FILE_GLOB} in {source_uri}")
    
    csv = sorted(files)[0]

    uri = storage.gdal_uri(raw_root, as_of, csv)
    logger.info(f"reading from {csv}")

    return tabular.read_points(
        uri,
        keep=KEEP,
        lon_col="gm_longitude",
        lat_col="gm_latitude",
    )
