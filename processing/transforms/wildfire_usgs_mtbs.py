"""MTBS burn severity (CONUS)

Published as a severity class raster (30 m, EPSG:5070). The warehouse keeps
every source as a feature table, so burned areas are polygonized into a
severity-class polygon table.

MTBS thematic codes: 0 background/nodata, 1 unburned-to-low, 2 low,
3 moderate, 4 high, 5 increased greenness, 6 non-mapping area. We keep the
real burn-severity classes (2 low, 3 moderate, 4 high) and drop the rest.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np

from .. import raster, storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "mtbs_CONUS*.zip"
DOWNSAMPLE = 1  # 30 m native; burned pixels are sparse
CLASS_FIELD = "severity_class"  # 2 low, 3 moderate, 4 high


def _reclass(a: np.ndarray) -> np.ndarray:
    # Keep burn-severity 2/3/4 (already severity-ordered); drop 0/5/6.
    return np.where((a >= 1) & (a <= 4), a, 0).astype(np.uint8)


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # The GeoTIFF sits at the zip root, named like the zip stem,
    # e.g. mtbs_CONUS_2026.tif
    inner = f"{Path(zip_name).stem}.tif"
    
    tif = storage.local_zip_member(raw_root, as_of, zip_name, inner)
    logger.info(f"reading {inner} from local cache")

    return raster.polygonize(
        tif,
        reclass=_reclass,
        downsample=DOWNSAMPLE,
        class_field=CLASS_FIELD,
    )
