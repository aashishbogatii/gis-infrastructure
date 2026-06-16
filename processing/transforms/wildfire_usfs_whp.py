"""USFS Wildfire Hazard Potential (CONUS)

Published as a class raster (270 m, EPSG:5070). The warehouse keeps every
source as a feature table, so this raster is polygonized into a hazard-class
polygon table.

The ``cls`` product codes: 1 Very low, 2 Low, 3 Moderate, 4 High, 5 Very high,
6 Non-burnable, 7 Water, 255 nodata. We keep the five hazard classes (1-5) as
severity-ordered values and drop non-burnable/water/nodata.

A modest block-max downsample to ~540 m (factor 2) keeps the polygon count in
line with the other tables while preserving the hazard gradient.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np

from .. import raster, storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "RDS-2015-0047-4*.zip"
INNER = "Data/whp2023_GeoTIF/whp2023_cls_conus.tif"
DOWNSAMPLE = 2  # 270 m native -> ~540 m cells
CLASS_FIELD = "hazard_class"  # 1 very low .. 5 very high


def _reclass(a: np.ndarray) -> np.ndarray:
    # Keep hazard classes 1-5 as-is (already severity-ordered); drop 6/7/255.
    return np.where((a >= 1) & (a <= 5), a, 0).astype(np.uint8)


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    tif = storage.local_zip_member(raw_root, as_of, zip_name, INNER)
    logger.info(f"reading {INNER} from local cache")

    return raster.polygonize(
        tif,
        reclass=_reclass,
        downsample=DOWNSAMPLE,
        class_field=CLASS_FIELD,
    )
