"""NOAA Sea Level Rise Viewer

Ships as 7 regional GeoPackages, each holding inundation polygons for 21 water
levels (0.0–10.0 ft, 0.5 ft steps) in two flavours: ``slr`` (hydrologically
connected inundation) and ``low`` (low-lying, disconnected areas). This
transform reads every layer across all 7 files, derives
``region`` / ``scenario_type`` / ``scenario_ft`` from the layer
name, and concatenates them into one table.
"""
from __future__ import annotations

import logging
import re

import geopandas as gpd
import pandas as pd
import pyogrio

from .. import storage

logger = logging.getLogger(__name__)

GPKG_GLOB = "*.gpkg"

# CA_<Region>_<type>_<d>_<f>ft  e.g. CA_SFBay_slr_6_0ft, CA_North1_low_0_5ft
LAYER_RE = re.compile(
    r"^CA_(?P<region>.+?)_(?P<type>slr|low)_(?P<d>\d+)_(?P<f>\d+)ft$"
)


def _read_layer(
    uri: str, layer: str, region: str, scenario: str, depth: float
) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(uri, layer=layer, engine="pyogrio", columns=[])
    gdf = gdf.to_crs(4326)
    gdf["region"] = region
    gdf["scenario_type"] = scenario
    gdf["scenario_ft"] = depth
    return gdf


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    gpkg_files = storage.list_vintage_files(raw_root, as_of, GPKG_GLOB)
    if not gpkg_files:
        raise FileNotFoundError(f"No {GPKG_GLOB} in {source_uri}")

    frames = []
    for gpkg in sorted(gpkg_files):
        uri = storage.local_file(raw_root, as_of, gpkg)
        for name, _geom in pyogrio.list_layers(uri):
            m = LAYER_RE.match(name)
            if not m:
                logger.debug(f"skip unrecognized layer {name}")
                continue
            depth = float(f'{m["d"]}.{m["f"]}')
            logger.info(f"reading {name} from {gpkg}")
            frames.append(
                _read_layer(uri, name, m["region"], m["type"], depth)
            )

    if not frames:
        raise ValueError("no SLRV layers matched the selection")
    
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)