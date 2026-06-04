"""Runner-owned raster -> vector helper.

This module turns a single-band raster into a polygon ``GeoDataFrame`` so it flows
through the same runner path as every vector source (``geom.normalize`` ->
provenance -> GeoParquet).

The work is windowed so it never loads a CONUS-scale grid at once:

    read native tile -> reclass to severity classes -> (optional) block-max
    downsample -> polygonize non-zero classes -> concat tiles.

**Reclass before downsample, on purpose.** ``reclass`` maps native values to
*severity-ordered* small ints (0 = drop / not-a-hazard). Block-max then keeps
the worst hazard in each coarse cell and because non-hazard codes map to 0
first, a "water"/"non-burnable" code can never outrank a real class.

The returned geometries are in the raster's **native CRS**; the runner's
``geom.normalize`` reprojects to EPSG:4326.
"""
from __future__ import annotations

import logging
from typing import Callable

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.transform import Affine
from rasterio.windows import Window
from shapely.geometry import shape

logger = logging.getLogger(__name__)

# Reclass: native band array -> uint8 severity classes (0 = drop; higher
# = worse hazard).
Reclass = Callable[[np.ndarray], np.ndarray]


def polygonize(
    uri: str,
    *,
    reclass: Reclass,
    downsample: int = 1,
    native_tile: int = 4096,
    connectivity: int = 4,
    class_field: str = "class",
    src_crs: str | None = None,
) -> gpd.GeoDataFrame:
    """Polygonize one raster band into class polygons.

    ``downsample`` is a block-max factor (1 = native resolution).
    ``native_tile`` bounds memory; partial edge rows/cols smaller than
    ``downsample`` are dropped.
    """
    f = max(1, int(downsample))
    nt = native_tile - (native_tile % f)

    geoms: list = []
    vals: list[int] = []

    with rasterio.open(uri) as ds:
        W, H = ds.width, ds.height
        crs = ds.crs or src_crs
        if crs is None:
            raise ValueError(f"{uri} has no CRS and no src_crs fallback given")
        logger.info(
            f"polygonize {ds.width}x{ds.height} crs={crs} "
            f"downsample={f} tile={nt}"
        )

        for y in range(0, H, nt):
            wh = min(nt, H - y)
            if f > 1:
                wh -= wh % f
            if wh < f:
                continue
            for x in range(0, W, nt):
                ww = min(nt, W - x)
                if f > 1:
                    ww -= ww % f
                if ww < f:
                    continue

                win = Window(x, y, ww, wh)
                cls = reclass(ds.read(1, window=win)).astype(np.uint8)

                if f > 1:
                    cls = cls.reshape(wh // f, f, ww // f, f).max(axis=(1, 3))
                    tr = ds.window_transform(win) * Affine.scale(f)
                else:
                    tr = ds.window_transform(win)

                mask = cls > 0
                if not mask.any():
                    continue
                for geom, val in shapes(
                    cls, mask=mask, transform=tr, connectivity=connectivity
                ):
                    geoms.append(shape(geom))
                    vals.append(int(val))

    gdf = gpd.GeoDataFrame({class_field: vals}, geometry=geoms, crs=crs)
    logger.info(f"polygonized -> {len(gdf):,} features")
    return gdf
