"""California municipal crime incident reports (multi-agency)

Incident-level crime from four CA police open-data portals (LA, SF, Sacramento,
Ventura), each with its own schema, merged onto one common schema with a
per-row ``source_agency``. Each agency's points are built in their native CRS
(LA/SF/Ventura EPSG:4326; Sacramento EPSG:2226) and reprojected to 4326 before
concatenation. ``category_normalized`` harmonizes the four vocabularies onto
the FBI UCR index crimes + Other/Non-Criminal buckets (see ``CATEGORY_RULES``);
raw category/description are kept for audit. (0, 0) ungeocoded placeholders are
dropped.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd

from .. import storage, tabular

logger = logging.getLogger(__name__)


CATEGORY_RULES: list[tuple[str, str]] = [
    ("Homicide", r"HOMICIDE|MURDER|MANSLAUGHTER"),
    
    ("Rape / Sexual Assault",
     r"\bRAPE\b|SODOMY|SEXUAL|\bLEWD\b|MOLEST|ORAL COPULAT|SEX OFFENSE|"
     r"SEX, UNLAWFUL|SEX ASSAULT|SEXUAL ASSAULT|SEXUAL BATTERY"),
    ("Robbery", r"ROBBERY|CARJACK"),

    ("Aggravated Assault",
     r"AGG\w*\s+ASSAULT|AGGRAVATED|DEADLY WEAPON|\bADW\b|"
     r"ASSAULT WITH A? ?DEADLY"),
    ("Arson", r"ARSON"),

    ("Motor Vehicle Theft",
     r"VEHICLE\s*-?\s*STOLEN|STOLEN\s+VEHICLE|VEHICLE THEFT|AUTO THEFT|"
     r"MOTOR VEHICLE THEFT|STOLEN\s+AUTO|\bGTA\b"),

    ("Larceny / Theft", r"FROM (?:MOTOR )?VEHICLE|BIKE\s*-?\s*STOLEN"),
    ("Burglary", r"BURGLARY|BREAKING\s*&?\s*(?:AND\s*)?ENTER|\bB ?& ?E\b"),

    ("Other Crime",
     r"IDENTITY|EMBEZZL|FORGERY|COUNTERFEIT|CREDIT CARD|\bBUNCO\b|\bFRAUD\b"),

    ("Larceny / Theft",
     r"\bTHEFT\b|\bLARCENY\b|SHOPLIFT|PICKPOCKET|PURSE SNATCH|STOLEN PROPERTY|"
     r"PETTY THEFT|GRAND THEFT"),

    ("Non-Criminal",
     r"LOST PROPERTY|FOUND PROPERTY|RECOVERED VEHICLE|TOWED|STORED VEHICLE|"
     r"MISSING PERSON|NON-?CRIMINAL|INCIDENT RPT|INCIDENT REPORT|"
     r"COURTESY REPORT|CASUALTY|CASE CLOSURE|MISC\w* INVESTIGATION|"
     r"SUSPICIOUS|WELFARE|MENTAL|TRAFFIC COLLISION|TRAFFIC ACCIDENT|"
     r"FIRE REPORT|DEATH REPORT|VEHICLE IMPOUND"),
]

_DEFAULT_CATEGORY = "Other Crime"


def _normalize_category(
    category: pd.Series, description: pd.Series
) -> pd.Series:
    """Map each row onto the harmonized taxonomy via CATEGORY_RULES."""
    text = (
        category.fillna("").astype(str)
        + " | "
        + description.fillna("").astype(str)
    ).str.upper()

    conds = [text.str.contains(pat, regex=True, na=False)
             for _label, pat in CATEGORY_RULES]
    labels = [label for label, _pat in CATEGORY_RULES]
    return pd.Series(
        np.select(conds, labels, default=_DEFAULT_CATEGORY), index=text.index
    )


SPECS = [
    {
        "agency": "los_angeles",
        "glob": "Crime_Data_*.csv",
        "lon_col": "LON",
        "lat_col": "LAT",
        "src_crs": "EPSG:4326",
        "keep": {
            "DR_NO": "record_id",
            "Part 1-2": "offense_category",
            "Crm Cd Desc": "offense_description",
            "DATE OCC": "occurred_at",
        },
    },
    {
        "agency": "ventura",
        "glob": "OpenData_Police_Crimes_*.csv",
        "lon_col": "x",
        "lat_col": "y",
        "src_crs": "EPSG:4326",
        "keep": {
            "Report_Number": "record_id",
            "Offense_Category": "offense_category",
            "Offense_Type": "offense_description",
            "Incident_Date_Start": "occurred_at",
        },
    },
    {
        "agency": "sacramento",
        "glob": "Police_Crime_3Years_*.csv",
        "lon_col": "x",
        "lat_col": "y",
        "src_crs": "EPSG:2226",
        "keep": {
            "Record_ID": "record_id",
            "Offense_Category": "offense_category",
            "Description": "offense_description",
            "Occurrence_Date_PT": "occurred_at",
        },
    },
    {
        "agency": "san_francisco",
        "glob": "Police_Department_Incident_Reports_*.csv",
        "lon_col": "Longitude",
        "lat_col": "Latitude",
        "src_crs": "EPSG:4326",
        "keep": {
            "Row ID": "record_id",
            "Incident Category": "offense_category",
            "Incident Description": "offense_description",
            "Incident Datetime": "occurred_at",
        },
    },
]


def _read_agency(spec: dict, raw_root: str, as_of: str) -> gpd.GeoDataFrame:
    matches = storage.list_vintage_files(raw_root, as_of, spec["glob"])
    if not matches:
        raise FileNotFoundError(f"No {spec['glob']} in {raw_root}/{as_of}")
    filename = sorted(matches)[0]
    uri = storage.gdal_uri(raw_root, as_of, filename)
    logger.info(f"reading {spec['agency']} from {filename}")

    gdf = tabular.read_points(
        uri,
        keep=spec["keep"],
        lon_col=spec["lon_col"],
        lat_col=spec["lat_col"],
        src_crs=spec["src_crs"],
    )
    gdf["source_agency"] = spec["agency"]
    gdf["record_id"] = gdf["record_id"].astype("string")
    gdf["occurred_at"] = pd.to_datetime(gdf["occurred_at"], errors="coerce")
    return gdf.to_crs(4326)


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    frames = [_read_agency(spec, raw_root, as_of) for spec in SPECS]
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)

    null_island = (gdf.geometry.x == 0) & (gdf.geometry.y == 0)
    dropped = int(null_island.sum())
    if dropped:
        logger.info(f"dropped {dropped:,} (0,0) null-island placeholder rows")
    gdf = gdf.loc[~null_island].reset_index(drop=True)

    gdf["category_normalized"] = _normalize_category(
        gdf["offense_category"], gdf["offense_description"]
    )
    dist = gdf["category_normalized"].value_counts()
    logger.info("category_normalized distribution:\n" + dist.to_string())

    return gpd.GeoDataFrame(gdf, crs=4326)
