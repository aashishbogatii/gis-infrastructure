"""EPA ACRES Brownfields (KMZ)

The KMZ wraps a single legacy-namespace KML whose placemarks are nested under
thousands of per-city folders. GDAL's KML driver explodes that into thousands
of layers and, worse, leaves the real EPA attributes locked inside each
placemark's ``description`` HTML table. So this transform parses the KML XML
directly (stdlib only): the placemark ``name`` is the facility name, the
``Point`` gives lon/lat (already WGS84), and REGISTRY ID / LOCATION ADDRESS /
COUNTY NAME / COLLECTION METHOD are pulled out of the description table.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
import zipfile

import geopandas as gpd
import pandas as pd

from .. import storage

logger = logging.getLogger(__name__)

FILE_GLOB = "*.kmz"

# description-table label=
FIELDS = {
    "REGISTRY ID": "registry_id",
    "LOCATION ADDRESS": "address",
    "COUNTY NAME": "county",
    "COLLECTION METHOD": "collection_method",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _cell(label: str, html: str) -> str | None:
    """Pull the value cell that follows a ``<td>LABEL</td>`` in the HTML table,
    stripping any inner tags (e.g. the REGISTRY ID's <a> link)."""
    m = re.search(
        rf"<td[^>]*>\s*{re.escape(label)}\s*</td>\s*<td[^>]*>(.*?)</td>",
        html,
        re.I | re.S,
    )
    if not m:
        return None
    val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return val or None


def _parse_placemark(el) -> dict | None:
    name = desc = coords = None
    for c in el.iter():
        ln = _local(c.tag)
        if ln == "name" and name is None:
            name = c.text
        elif ln == "description" and desc is None:
            desc = c.text
        elif ln == "coordinates" and coords is None:
            coords = c.text
    if not coords:
        return None
    lon, lat, *_ = coords.strip().split(",")

    rec = {"facility_name": name, "lon": float(lon), "lat": float(lat)}
    rec.update({tgt: None for tgt in FIELDS.values()})
    if desc:
        for label, tgt in FIELDS.items():
            rec[tgt] = _cell(label, desc)
    return rec


def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    raw_root = config["raw_root"]
    as_of = config["source_as_of"]

    files = storage.list_vintage_files(raw_root, as_of, FILE_GLOB)
    if not files:
        raise FileNotFoundError(f"No {FILE_GLOB} in {source_uri}")
    kmz_name = sorted(files)[0]
    logger.info(f"parsing placemarks from {kmz_name}")

    records: list[dict] = []
    with storage.open_binary(raw_root, as_of, kmz_name) as fh:
        zf = zipfile.ZipFile(fh)
        kml = next(n for n in zf.namelist() if n.lower().endswith(".kml"))
        with zf.open(kml) as f:
            for _, el in ET.iterparse(f, events=("end",)):
                if _local(el.tag) == "Placemark":
                    rec = _parse_placemark(el)
                    if rec:
                        records.append(rec)
                    el.clear()

    df = pd.DataFrame.from_records(records)
    logger.info(f"parsed {len(df):,} placemarks")
    return gpd.GeoDataFrame(
        df.drop(columns=["lon", "lat"]),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )
