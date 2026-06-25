"""Runner-owned geometry normalization.

- CRS stored as EPSG:4326 (WGS84).
- Geometry column named ``geometry``; all attribute columns lowercased.
- Null/empty geometries are DROPPED
- Optional write-time layout: per-row ``bbox_*`` columns + a Hilbert-curve row
  sort, so the warehouse can prune on plain numeric columns instead of decoding
  every geometry.
"""
from __future__ import annotations

import logging

import geopandas as gpd

logger = logging.getLogger(__name__)

TARGET_CRS = "EPSG:4326"

# BBOX_COLS = ("bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy")


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


# def add_bbox_and_sort(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
#     """Materialize per-row bbox columns and reorder rows on a Hilbert curve.

#     The four ``bbox_*`` columns let a reader prefilter on plain numeric columns
#     (which carry parquet row-group min/max stats) instead of decoding every
#     geometry; the Hilbert sort clusters nearby rows into the same row group so
#     those stats are tight enough to prune. Pure write-time layout — geometry and
#     attribute values are unchanged, only row order and four added columns.
#     """
#     if len(gdf) == 0:
#         for c in BBOX_COLS:
#             gdf[c] = []
#         return gdf

#     b = gdf.bounds   # columns: minx, miny, maxx, maxy (in stored CRS, 4326)
#     gdf = gdf.copy()
#     gdf["bbox_minx"] = b["minx"].to_numpy()
#     gdf["bbox_miny"] = b["miny"].to_numpy()
#     gdf["bbox_maxx"] = b["maxx"].to_numpy()
#     gdf["bbox_maxy"] = b["maxy"].to_numpy()

#     order = gdf.hilbert_distance().to_numpy().argsort(kind="stable")
#     return gdf.iloc[order].reset_index(drop=True)
