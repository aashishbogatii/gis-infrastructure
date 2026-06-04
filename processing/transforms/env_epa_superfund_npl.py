"""EPA Superfund National Priorities List boundaries — nationwide. Pattern B.

Reads the ``SITE_BOUNDARIES_SF`` polygon layer from the published file
geodatabase *inside the zip*, in place, via GDAL's ``/vsizip/`` virtual
filesystem (the gdb also ships line/point/IC/OU layers, which we ignore — the
site boundary polygons are the evidentiary geometry).

Columns are selected and renamed to the STTM target names. The source ships
in EPSG:4326; the runner's ``geom.normalize`` re-asserts the CRS (no-op).
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "NPL_Boundaries*.zip"
LAYER = "SITE_BOUNDARIES_SF"

KEEP = {
    "EPA_ID": "epa_id",
    "SITE_NAME": "site_name",
    "SITE_FEATURE_CLASS": "site_feature_class",
    "SITE_FEATURE_TYPE": "site_feature_type",
    "FEATURE_INFO_URL": "feature_info_url",
    "NPL_STATUS_CODE": "npl_status_code",
    "COUNTY": "county",
    "STATE_CODE": "state_code",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # The gdb is named like the zip stem, e.g. NPL_Boundaries.gdb
    gdb = f"{Path(zip_name).stem}.gdb"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=gdb)
    logger.info(f"reading layer {LAYER} from {zip_name}")

    gdf = gpd.read_file(uri, layer=LAYER, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
