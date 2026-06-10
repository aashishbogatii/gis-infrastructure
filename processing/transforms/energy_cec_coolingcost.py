"""CEC / Cal-Adapt cooling cost

Downscaled CMIP6 (LOCA2, SSP2-4.5, 3-model ensemble) summarized to one row per
tract: cooling degree-days and the modeled cooling-electricity dollar burden per
household, baseline (1981-2010) vs mid-century (2035-2064), plus deltas. The
polygon is the *tract*, so this is a containment layer (parcel in tract).
"""
from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd

from .. import storage
from .. import tabular

logger = logging.getLogger(__name__)

FILE_GLOB = "cooling_cost.parquet"

KEEP = {
    "GEOID": "geoid",
    "historical_cdd": "historical_cdd",
    "midcentury_cdd": "midcentury_cdd",
    "delta_cdd": "delta_cdd",                          # physical driver
    "historical_cooling_cost_usd": "historical_cooling_cost_usd",
    "midcentury_cooling_cost_usd": "midcentury_cooling_cost_usd",
    "delta_cooling_cost_usd": "delta_cooling_cost_usd",  # adjustment driver
}


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    files = storage.list_vintage_files(raw_root, as_of, FILE_GLOB)
    if not files:
        raise FileNotFoundError(f"No {FILE_GLOB} in {source_uri}")
    name = sorted(files)[0]

    logger.info(f"reading {name}")
    with storage.open_binary(raw_root, as_of, name) as f:
        df = pd.read_parquet(f)

    return tabular.from_wkt(df, keep=KEEP)
