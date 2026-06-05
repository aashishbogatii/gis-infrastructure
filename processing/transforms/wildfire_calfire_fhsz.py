"""CAL FIRE Fire Hazard Severity Zones

Ships in two jurisdictional bundles that together tile the state, SRA (State
Responsibility Area) and LRA (Local Responsibility Area). Reads the FHSZ layer
from each file geodatabase *inside its zip*, in place, via GDAL's ``/vsizip/``
virtual filesystem, then concatenates them with a ``jurisdiction`` tag.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd

from .. import storage

logger = logging.getLogger(__name__)

# (jurisdiction, zip-name glob, inner .gdb directory) for each bundle.
BUNDLES = (
    ("LRA", "FHSZLRA*.zip", "FHSZLRA25_1_All.gdb"),   # Local Responsibility Area
    ("SRA", "FHSZSRA*.zip", "FHSZSRA_23_3.gdb"),      # State Responsibility Area
)

KEEP = {
    "FHSZ": "fhsz_code",            # 1 Moderate, 2 High, 3 Very High, -3 NonWildland
    "FHSZ_Description": "fhsz_class",
}


def _read_bundle(
    raw_root: str, as_of: str, zip_name: str, inner: str, jurisdiction: str
) -> gpd.GeoDataFrame:
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=inner)
    logger.info(f"reading {inner} from {zip_name}")
    gdf = gpd.read_file(uri, engine="pyogrio")
    gdf["jurisdiction"] = jurisdiction
    return gdf


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    frames = []
    for jurisdiction, glob, inner in BUNDLES:
        zips = storage.list_vintage_files(raw_root, as_of, glob)
        if not zips:
            raise FileNotFoundError(f"No {glob} in {source_uri}")
        frames.append(
            _read_bundle(raw_root, as_of, sorted(zips)[0], inner, jurisdiction)
        )

    gdf = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True), crs=frames[0].crs
    )
    gdf = gdf.set_geometry(gdf.geometry.force_2d())

    cols = [c for c in KEEP if c in gdf.columns] + ["jurisdiction"]
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
