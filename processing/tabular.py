"""Runner-owned helper: flat table (CSV/XLSX) -> point GeoDataFrame.

Some sources publish points as lat/lon columns in a flat table (EPA AQS, LMOP)
with no geometry of their own. This builds POINT geometry from the
coordinate columns and sets the CRS, so the rest of the path matches a
native-vector source.

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
    src_crs: str = "EPSG:4326",
) -> gpd.GeoDataFrame:
    df = read_dataframe(uri, layer=layer, read_geometry=False)

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
