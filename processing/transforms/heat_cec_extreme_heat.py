"""CEC / Cal-Adapt extreme-heat days

Downscaled CMIP6 (LOCA2, SSP2-4.5, 3-model ensemble) summarized to one row per
tract: the local extreme-heat threshold and the baseline (1981-2010) vs
mid-century (2035-2064) counts of extreme-heat days and days over 100 F, plus
their deltas. The polygon is the *tract*, so this is a containment layer (parcel
in tract), not a distance one.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd

from .. import storage
from .. import tabular

logger = logging.getLogger(__name__)

FILE_GLOB = "extreme_heat_days.parquet"

KEEP = {
    "GEOID": "geoid",
    "p98_threshold_F": "p98_threshold_f",              # local "hot day" def
    "historical_p98_days": "historical_p98_days",
    "midcentury_p98_days": "midcentury_p98_days",
    "delta_p98_days": "delta_p98_days",                # adjustment driver
    "historical_days_over_100F": "historical_days_over_100f",
    "midcentury_days_over_100F": "midcentury_days_over_100f",
    "delta_days_over_100F": "delta_days_over_100f",    # adjustment driver
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
