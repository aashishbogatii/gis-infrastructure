"""CGS Alquist-Priolo Earthquake Fault Zones

Reads the ``CGS_Alquist_Priolo_Fault_Zones`` polygon layer straight from the
shapefile *inside the zip*, in place, via GDAL's ``/vsizip/`` virtual
filesystem. Keeps the zone identity, zone-level release/revision and
map/report-link evidence columns.
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "CGS_Alquist_Priolo_Fault_Zones*.zip"
INNER = "CGS_Alquist_Priolo_Fault_Zones.shp"

KEEP = {
    "QUAD_NAME": "quad_name",       # USGS 7.5' quadrangle
    "ZN_RELEASE": "zone_released",  # zone release date
    "ZN_REVISED": "zone_revised",   # revised flag (Y/N) — see DQ note
    "GEOPDFLINK": "geopdf_link",
    "REPORTLINK": "report_link",
    "GlobalID": "global_id",
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, ZIP_GLOB)
    if not zips:
        raise FileNotFoundError(f"No {ZIP_GLOB} in {source_uri}")
    zip_name = sorted(zips)[0]

    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=INNER)
    logger.info(f"reading {INNER} from {zip_name}")

    gdf = gpd.read_file(uri, engine="pyogrio")

    cols = [c for c in KEEP if c in gdf.columns]
    logger.debug(f"kept {len(cols)} of {len(KEEP)} columns")
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
