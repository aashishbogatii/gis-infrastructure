"""Runner-owned helper: flat table (CSV/XLSX/Parquet) -> GeoDataFrame.

``read_points`` builds POINT geometry from coordinate columns;
``from_wkt`` parses a WKT column. Both set the CRS so the rest of the path
matches a native-vector source.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd
from pyogrio import read_dataframe

logger = logging.getLogger(__name__)


def read_points(
    uri: str,
    *,
    keep: dict[str, str],
    lon_col: str,
    lat_col: str,
    layer: str | None = None,
    encoding: str | None = None,
    src_crs: str = "EPSG:4326",
) -> gpd.GeoDataFrame:
    df = read_dataframe(
        uri, layer=layer, read_geometry=False, encoding=encoding
    )

    lon = pd.to_numeric(df[lon_col], errors="coerce")
    lat = pd.to_numeric(df[lat_col], errors="coerce")
    ok = lon.notna() & lat.notna()
    dropped = int((~ok).sum())
    if dropped:
        logger.info(f"dropped {dropped:,} rows with missing/invalid lon/lat")

    df = df.loc[ok]
    cols = [c for c in keep if c in df.columns]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        logger.warning(f"expected columns not found: {missing}")

    gdf = gpd.GeoDataFrame(
        df[cols].copy(),
        geometry=gpd.points_from_xy(lon[ok], lat[ok]),
        crs=src_crs,
    )
    return gdf.rename(columns=keep)


def from_wkt(
    df: pd.DataFrame,
    *,
    keep: dict[str, str],
    wkt_col: str = "geometry",
    src_crs: str = "EPSG:4326",
) -> gpd.GeoDataFrame:
    """Flat table with a WKT geometry column -> GeoDataFrame.
    """
    cols = [c for c in keep if c in df.columns]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        logger.warning(f"expected columns not found: {missing}")

    geometry = gpd.GeoSeries.from_wkt(df[wkt_col].astype("string"))
    gdf = gpd.GeoDataFrame(df[cols].copy(), geometry=geometry, crs=src_crs)
    return gdf.rename(columns=keep)
