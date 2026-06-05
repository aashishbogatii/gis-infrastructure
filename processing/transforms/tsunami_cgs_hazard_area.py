"""CGS Tsunami Hazard Areas (California). Pattern A.

Reads the ``CA_Tsunami_Hazard_Area`` polygon layer from the shapefile *inside
the zip* (nested one folder deep), in place, via GDAL's ``/vsizip/`` virtual
filesystem. The ``Evacuate`` text field is reduced to a boolean
``in_hazard_area``; the companion hazard-*line* shapefile is ignored.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "CGS_Tsunami_Hazard_Area*.zip"
INNER = "CA_Tsunami_Hazard_Area.shp"

KEEP = {
    "County": "county",
    "GIS_Link": "gis_link",
    "Map_Link": "map_link",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    inner = f"{Path(zip_name).stem}/{INNER}"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {INNER} from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")
    gdf = gdf.set_geometry(gdf.geometry.force_2d())

    gdf["in_hazard_area"] = gdf["Evacuate"].str.startswith("Yes")

    cols = [c for c in KEEP if c in gdf.columns] + ["in_hazard_area"]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
