"""USGS National Seismic Hazard Model (2023) fault sections

Reads the ``NSHM23_FSD_v3`` fault-section-database line layer straight from
the shapefile *inside the zip*, in place, via GDAL's ``/vsizip/`` virtual
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "NSHM*_FSD_*.zip"

KEEP = {
    "FaultID": "fault_id",
    "FaultName": "fault_name",
    "PrimState": "prim_state",
    "DipDeg": "dip_deg",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    # Shapefile sits at the zip root, named like the zip stem,
    # e.g. NSHM23_FSD_v3.shp
    inner = f"{Path(zip_name).stem}.shp"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {inner} from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
