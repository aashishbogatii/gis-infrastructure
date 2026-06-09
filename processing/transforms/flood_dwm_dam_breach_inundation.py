"""CA DWR dam-breach inundation boundaries. Pattern A (containment).

Approved inundation maps showing the area flooded if a dam fails — a parcel
inside a boundary carries the risk. Polygon shapefile read in place from inside
the zip via GDAL's /vsizip/; keeps the dam identity (NID id, name), the failure
scenario/loading, hazard class, and publication date.
"""
from __future__ import annotations

import geopandas as gpd

import logging

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "Approved_InundationBoundaries*.zip"

KEEP = {
    "Nid": "nid",
    "DamName": "dam_name",
    "FailedStr": "failure_structure",
    "Scenario": "scenario",
    "LoadingScn": "loading_scenario",
    "PubDate": "pub_date",
    "HazardCl": "hazard_class",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    uri = storage.gdal_uri(raw_root, as_of, zip_name)
    logger.info(f"reading from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)

