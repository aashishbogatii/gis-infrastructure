"""Runner-owned geometry normalization.

- CRS stored as EPSG:4326 (WGS84).
- Geometry column named ``geometry``; all attribute columns lowercased.
- Null/empty geometries are DROPPED
"""
from __future__ import annotations

import logging

import geopandas as gpd

logger = logging.getLogger(__name__)

TARGET_CRS = "EPSG:4326"


def normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        raise ValueError("Input has no CRS; set one in the transform before normalize().")

    if str(gdf.crs).upper() != TARGET_CRS:
        logger.debug(f"reprojecting {gdf.crs} -> {TARGET_CRS}")
        gdf = gdf.to_crs(TARGET_CRS)

    gdf.rename(columns=str.lower, inplace=True)
    if gdf.geometry.name != "geometry":
        gdf.rename_geometry("geometry", inplace=True)
    gdf.set_geometry("geometry", inplace=True)

    mask = gdf.geometry.notna() & ~gdf.geometry.is_empty
    dropped = int((~mask).sum())
    if dropped:
        logger.info(f"dropped {dropped:,} null/empty geometries")
    return gdf.loc[mask].reset_index(drop=True)
