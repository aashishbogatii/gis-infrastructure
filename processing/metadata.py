"""Runner-owned provenance stamping.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import geopandas as gpd

logger = logging.getLogger(__name__)


def stamp(
    gdf: gpd.GeoDataFrame,
    *,
    source_name: str,
    source_url: str,
    source_as_of: str,
) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["source_name"] = source_name
    gdf["source_url"] = source_url
    gdf["source_as_of"] = source_as_of
    gdf["loaded_at"] = datetime.now(timezone.utc).isoformat()
    logger.debug(
        f"stamped provenance: {source_name} (as_of={source_as_of})"
    )
    return gdf
