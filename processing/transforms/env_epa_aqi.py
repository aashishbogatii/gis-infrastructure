"""EPA AQS annual concentration by monitor

A flat CSV of monitor-level annual air-quality statistics, read in place from
*inside the zip* via GDAL's ``/vsizip/`` virtual filesystem. The monitor point
geometry is built from the ``Latitude``/``Longitude`` columns (the CSV carries
no geometry); the runner keeps the resulting EPSG:4326 points.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage, tabular

logger = logging.getLogger(__name__)

ZIP_GLOB = "annual_conc_by_monitor*.zip"

KEEP = {
    "State Code": "state_code",
    "County Code": "county_code",
    "Site Num": "site_num",
    "Parameter Name": "parameter_name",
    "Year": "obs_year",
    "Units of Measure": "units",
    "Primary Exceedance Count": "exceedances",
    "Arithmetic Mean": "annual_mean",
    "1st Max Value": "max_value",
    "99th Percentile": "p99",
    "Local Site Name": "site_name",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # The CSV is named like the zip stem, e.g. annual_conc_by_monitor_2025.csv
    inner = f"{Path(zip_name).stem}.csv"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {inner} from {zip_name}")

    return tabular.read_points(
        uri, keep=KEEP, lon_col="Longitude", lat_col="Latitude"
    )
