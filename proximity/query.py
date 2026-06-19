"""Proximity SQL — one probe, per-source query, parameterized by mode.

`proximity_sql(source, src_relation)` dispatches on the source's mode:

  feature (default) — a row per feature within radius, with containment +
                      edge-to-edge distance and the source's attributes JSON.
  count             — aggregate: count features per `group_by` category within
                      radius (e.g. crimes per category). distance/contained null.

Both modes return the SAME columns — `source, contained, distance_m, attributes`
— so the runner can collect them uniformly.

CRS: sources and the parcel are stored EPSG:4326; distance is computed in
EPSG:3310 (CA Albers, meters). Containment is topological, done in 4326.
The single `?` parameter is the parcel geometry as WKB.
"""
from __future__ import annotations

from .registry import Source

_TO_3310 = "ST_Transform({g}, 'EPSG:4326','EPSG:3310', always_xy:=true)"


def _attributes_json(source: Source) -> str:
    """json_object('attr', s.attr, ...) from the registry attrs (trusted)."""
    pairs = ", ".join(f"'{a}', s.{a}" for a in source.attributes)
    return f"json_object({pairs})"


def _deg_margin(radius_m: int) -> float:
    """Radius in degrees for the bbox prefilter. Conservative for CA latitudes
    (1 lon-deg ~ 87 km at 38N) so it over-includes; the exact ST_DWithin trims."""
    return radius_m / 80000.0


def _probe_cte() -> str:
    """The parcel decoded once (? is its WKB), with its bbox in 4326 degrees."""
    return f"""
    WITH probe AS (
        SELECT g4326, {_TO_3310.format(g="g4326")} AS g3310,
               ST_XMin(g4326) AS pminx, ST_XMax(g4326) AS pmaxx,
               ST_YMin(g4326) AS pminy, ST_YMax(g4326) AS pmaxy
        FROM (SELECT ST_GeomFromWKB(?) AS g4326)
    )"""


def _spatial_predicate(source: Source) -> str:
    """The spatial match test, by source type:
      containment -> only the polygon the parcel is in (ST_Intersects)
      proximity   -> contained OR within radius (ST_Intersects OR ST_DWithin)
    """
    feat_3310 = _TO_3310.format(g="s.geom")
    within = f"ST_DWithin(probe.g3310, {feat_3310}, {source.radius_m})"
    contains = "ST_Intersects(s.geom, probe.g4326)"
    if source.type == "containment":
        return contains
    return f"({contains} OR {within})"   # proximity: in it OR near it


def _from_where(source: Source, src_relation: str) -> str:
    """FROM + bbox prefilter + the type's spatial predicate, shared by modes."""
    # containment needs no radius margin; proximity/hybrid expand by the radius.
    ddeg = 0.0 if source.type == "containment" else _deg_margin(source.radius_m)
    return f"""FROM {src_relation} s, probe
    WHERE ST_XMax(s.geom) >= probe.pminx - {ddeg}
      AND ST_XMin(s.geom) <= probe.pmaxx + {ddeg}
      AND ST_YMax(s.geom) >= probe.pminy - {ddeg}
      AND ST_YMin(s.geom) <= probe.pmaxy + {ddeg}
      AND {_spatial_predicate(source)}"""


def _feature_sql(source: Source, src_relation: str, *,
                 nearest_by: str | None = None, single: bool = False) -> str:
    feat_3310 = _TO_3310.format(g="s.geom")
    dist = f"ST_Distance(probe.g3310, {feat_3310})"
    qualify = ""
    if nearest_by:                       # nearest match per group (e.g. per pollutant)
        qualify = (f"\n    QUALIFY row_number() OVER "
                   f"(PARTITION BY s.{nearest_by} ORDER BY {dist}) = 1")
    limit = "\n    LIMIT 1" if single else ""
    return f"""{_probe_cte()}
    SELECT
        '{source.key}'                              AS source,
        ST_Intersects(s.geom, probe.g4326)          AS contained,
        round({dist}, 1)                            AS distance_m,
        {_attributes_json(source)}                  AS attributes
    {_from_where(source, src_relation)}{qualify}
    ORDER BY distance_m{limit}
    """


def _count_sql(source: Source, src_relation: str) -> str:
    """ONE row: total + per-category counts as a {category: n} map. No row if 0."""
    gb = source.group_by
    return f"""{_probe_cte()},
    counts AS (
        SELECT s.{gb} AS category, count(*) AS n
        {_from_where(source, src_relation)}
        GROUP BY s.{gb}
    )
    SELECT
        '{source.key}'  AS source,
        NULL            AS contained,
        NULL            AS distance_m,
        json_object('total', sum(n),
                    'by_category', json_group_object(category, n)) AS attributes
    FROM counts
    HAVING sum(n) > 0
    """


def _nearest_collapsed_sql(source: Source, src_relation: str) -> str:
    """ONE row: nearest match per group, packed into a {group: {reading}} map."""
    gb = source.group_by
    feat_3310 = _TO_3310.format(g="s.geom")
    dist = f"ST_Distance(probe.g3310, {feat_3310})"
    value_attrs = [a for a in source.attributes if a != gb]   # group is the map key
    pairs = ", ".join(f"'{a}', s.{a}" for a in value_attrs)
    value_obj = f"json_object({pairs}, 'distance_m', round({dist}, 1))"
    return f"""{_probe_cte()},
    nearest AS (
        SELECT s.{gb} AS grp, {value_obj} AS val
        {_from_where(source, src_relation)}
        QUALIFY row_number() OVER (PARTITION BY s.{gb} ORDER BY {dist}) = 1
    )
    SELECT
        '{source.key}'  AS source,
        NULL            AS contained,
        NULL            AS distance_m,
        json_group_object(grp, val) AS attributes
    FROM nearest
    HAVING count(*) > 0
    """


def proximity_sql(source: Source, src_relation: str) -> str:
    """SQL for one source's matches. Bind one param: parcel geometry (WKB)."""
    if source.mode == "count":
        return _count_sql(source, src_relation)
    if source.mode == "nearest":
        if source.group_by:
            # collapse=True -> one row, {group: reading} map; else one row per group
            if source.collapse:
                return _nearest_collapsed_sql(source, src_relation)
            return _feature_sql(source, src_relation, nearest_by=source.group_by)
        return _feature_sql(source, src_relation, single=True)
    return _feature_sql(source, src_relation)


if __name__ == "__main__":
    from .registry import get_source

    for key in ("flood_fema_nfhl", "crime_ca"):
        s = get_source(key)
        print(f"===== {key} (mode={s.mode}) =====")
        print(proximity_sql(s, "(SELECT <cols>, geom FROM <src>)"))
