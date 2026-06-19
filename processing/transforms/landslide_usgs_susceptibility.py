"""USGS Landslide Susceptibility (CONUS)

Published as a raster (continuous 0-81 susceptibility index, ~87 m, EPSG:4269).
The warehouse keeps every source as a feature table, so this raster is turned
into a polygon table: the index is binned into 4 susceptibility classes and
polygonized.

Because the index is a noisy continuous surface, polygonizing at native
resolution yields ~100M slivers. We block-max downsample to ~700 m first
(factor 8) keeping the worst susceptibility in each coarse cell which gives
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np

from .. import raster, storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "lw_susc*.zip"
INNER = "lw_susc/lw_conus.tif"
DOWNSAMPLE = 8  # ~87 m native -> ~700 m cells
CLASS_FIELD = "susceptibility_class"  # 1 moderate .. 3 very high


def _reclass(a: np.ndarray) -> np.ndarray:
    # Source susceptibility index ranges 0-81
    out = np.zeros(a.shape, dtype=np.uint8)
    out[(a >= 0) & (a <= 20)] = 1  # low
    out[(a >= 21) & (a <= 40)] = 2  # moderate
    out[(a >= 41) & (a <= 60)] = 3  # high
    out[(a >= 61) & (a <= 81)] = 4  # very high
    return out


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # Extract the TIF to local disk first.
    tif = storage.local_zip_member(raw_root, as_of, zip_name, INNER)
    logger.info(f"reading {INNER} from local cache")

    return raster.polygonize(
        tif,
        reclass=_reclass,
        downsample=DOWNSAMPLE,
        class_field=CLASS_FIELD,
    )
