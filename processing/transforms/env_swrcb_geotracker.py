"""CA SWRCB GeoTracker cleanup / LUST sites.

Point sites that impact water quality (leaking underground storage tanks,
cleanup program sites) — proximity to an open case is the value signal. Published
as a flat CSV with no native geometry, so POINT geometry is built from the
LON/LAT columns; read as ISO-8859-1 for the Latin-1 business names.
"""
from __future__ import annotations

import geopandas as gpd

import logging

from .. import storage
from .. import tabular


logger = logging.getLogger(__name__)

FILE_GLOB = "geotracker_sites*.csv"

KEEP = {
    "GLOBAL_ID": "global_id",                          # GeoTracker site key
    "BUSINESS_NAME": "business_name",
    "COUNTY": "county",
    "COORDINATE_SOURCE": "coordinate_source",          # geocoding-quality flag
    "CASE_TYPE": "case_type",                          # e.g. LUST, cleanup
    "STATUS": "status",                                # open / closed
    "STATUS_DATE": "status_date",
    "POTENTIAL_CONTAMINANTS_OF_CONCERN": "contaminants",
    "POTENTIAL_MEDIA_OF_CONCERN": "media_of_concern"   # soil / groundwater / …
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
        lon_col="LONGITUDE",
        lat_col="LATITUDE",
        encoding="ISO-8859-1",
    )
