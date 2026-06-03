"""FEMA National Flood Hazard Layer (NFHL) — California subset. Pattern A.

Reads the ``S_FLD_HAZ_AR`` (flood hazard areas) layer straight from the
published file geodatabase *inside the zip*, in place, via GDAL's ``/vsizip/``
virtual filesystem — no extraction, no rename. Works identically in dev (local
zip) and prod (zip on S3, streamed via ``/vsizip//vsis3/``) because file
discovery and URI building are delegated to ``storage``.

The source ships in EPSG:4269 (NAD83); the runner's ``geom.normalize``
reprojects to EPSG:4326.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .. import storage

logger = logging.getLogger(__name__)

LAYER = "S_FLD_HAZ_AR"

# Flood-zone designation + evidence fields; drop modeling/internal columns.
KEEP = [
    "DFIRM_ID",      # FIRM database id
    "FLD_AR_ID",     # flood area id
    "FLD_ZONE",      # zone code: A, AE, AH, AO, V, VE, X, ...
    "ZONE_SUBTY",    # subtype: FLOODWAY, 0.2 PCT ANNUAL CHANCE, ...
    "SFHA_TF",       # Special Flood Hazard Area true/false
    "STATIC_BFE",    # base flood elevation
    "DEPTH",
    "V_DATUM",
    "SOURCE_CIT",    # FEMA source citation key
    "GFID",          # global feature id
]


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    zips = storage.list_vintage_files(raw_root, as_of, "NFHL_*.zip")
    if not zips:
        raise FileNotFoundError(f"No NFHL_*.zip in {source_uri}")
    zip_name = sorted(zips)[0]

    # The geodatabase is named like the zip stem, e.g. NFHL_06_20260429.gdb
    gdb = f"{Path(zip_name).stem}.gdb"
    uri = storage.gdal_uri(raw_root, as_of, zip_name, inner=gdb)
    logger.info(f"reading layer {LAYER} from {zip_name}")

    gdf = gpd.read_file(uri, layer=LAYER, engine="pyogrio")

    keep = [c for c in KEEP if c in gdf.columns]
    logger.debug(f"kept {len(keep)} of {len(KEEP)} columns")
    return gdf[keep + [gdf.geometry.name]]
