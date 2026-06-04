"""NIFC WFIGS incident locations (year-to-date)

Reads the ``Incidents`` point layer straight from the shapefile *inside the
zip*, in place, via GDAL's ``/vsizip/`` virtual filesystem.
"""
from __future__ import annotations

import logging

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

ZIP_GLOB = "WFIGS_Incident_Locations*.zip"
INNER = "Incidents.shp"

KEEP = {
    "IrwinID": "irwin_id",
    "UniqueFire": "unique_fire_id",
    "IncidentNa": "incident_name",
    "IncidentTy": "incident_type",
    "FinalAcres": "final_acres",
    "FireCause": "fire_cause",
    "FireDiscov": "discovery_date",
    "POOCounty": "county",       # point-of-origin county
    "POOState": "state",         # point-of-origin state
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
    return gdf[cols + [gdf.geometry.name]].rename(columns=KEEP)
