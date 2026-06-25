# `proximityProfile/`: on-demand parcel risk-profile service

Given a parcel **APN**, looks up its geometry and returns — in one JSON
document — every risk factor near or over the parcel: the distance to each
risk source and the source's evidence attributes. **One engine** reads
`registry.yaml` and runs a spatial query per source against the curated
Parquet in S3. There are no per-source query files.

Adding a source = **one registry row**. Everything else (vintage resolution,
the spatial SQL, JSON assembly) is runner-owned.

## Quickstart

```bash
# from the repo root (the package is imported as `proximityProfile`)
pip install -r proximityProfile/requirements.txt

python -m proximityProfile.runner 5426020012     # one APN -> risk profile JSON

# or serve it over HTTP (FastAPI)
fastapi dev proximityProfile/server.py           # GET /risk-profile/5426020012
```

## Configuration

Read by [backends.py](backends.py); set via environment variables (or `.env` in dev).

| Variable | Default | Meaning |
|---|---|---|
| `ENV` | `dev` | `dev` = local disk; `prod` = S3 |
| `CURATED_PROD_BASE` | `s3://low-appeal-agents-us-gis-data/curated` | where curated sources live |
| `PARCEL_PROD` |  `s3://…/parcels/California/ca_parcels.parquet` | the parcel store looked up by APN |
| `DUCKDB_EXTENSION_DIR` | `/opt/python` | where the Lambda layer drops the bundled `.duckdb_extension` files |

`spatial` extension is `LOAD`ed from the layer (offline); `httpfs`/`aws` + an S3
secret load only when the data is on S3.

## How a request works

`runner.proximity(apn)` ([runner.py](runner.py)):

1. **Connect** (`backends.connect`): load `spatial`; if reading S3, also
   `httpfs` + `aws` and create the `credential_chain` S3 secret.
2. **Fetch the parcel** (`fetch_parcel_row`): the parcel geometry (WKB) for the
   **normalized** APN (dashes stripped), or 404 if not found.
3. **Probe each source**: for every registry row, build a `source_relation`
   ([backends.py](backends.py)) and run the per-source `proximity_sql`
   ([query.py](query.py)) with the parcel geometry as the bind parameter.
4. **Assemble** `{apn, county_name, fullstreetaddress, matches[]}`.

Every source returns the **same envelope** — `source, contained, distance_m,
attributes` — so the runner collects them uniformly; the source-specific
evidence rides inside the `attributes` JSON.

## Registry (`registry.yaml`)

One row per source; loaded into typed `Source` specs by [registry.py](registry.py).

| Key | Meaning |
|---|---|
| `schema`, `table` | locate the curated source |
| `attributes` | columns returned in each match's `attributes` JSON |
| `type` | `proximity` (contained **or** within radius) \| `containment` (only the polygon the parcel is in) |
| `radius_m` | proximity search radius (ignored for `containment`) |
| `mode` | `feature` (default, a row per match) \| `count` (per-category counts) \| `nearest` (closest only) |
| `group_by` | category column for `count`, or the key kept per group for `nearest` |
| `filter` | SQL `WHERE` applied to the source before the spatial test |

## Output shape

A nested JSON document — heterogeneous sources keep their own attribute set:

```json
{
  "apn": "5426020012",
  "county_name": "LOS ANGELES",
  "fullstreetaddress": "...",
  "matches": [
    {"source": "flood_fema_nfhl", "contained": true,  "distance_m": 0.0,
     "attributes": {"fld_zone": "A", "sfha_tf": "T"}},
    {"source": "crime_ca", "contained": null, "distance_m": null,
     "attributes": {"total": 412, "by_category": {"theft": 120}}}
  ]
}
```

Each element of `matches[]` maps 1:1 to a `risk_score.fact_parcel_risk` row
downstream (grain = parcel × source).

## CRS & distance

Sources and the parcel are stored **EPSG:4326**. Distance is computed in
**EPSG:3310** (CA Albers, meters) via `ST_DWithin`/`ST_Distance`; containment is
topological in 4326 (`ST_Intersects`). A cheap bbox prefilter discards far
features before the exact spatial test.

## Layout

```
proximityProfile/
  runner.py          # proximity(apn); CLI: python -m proximityProfile.runner <APN>
  backends.py        # connect + ENV switch + vintage resolution + source_relation (the swap point)
  query.py           # per-source spatial SQL builders (feature/count/nearest/collapse)
  registry.py        # registry.yaml -> typed Source specs
  registry.yaml      # one row per source (the source catalog)
  server.py          # FastAPI wrapper (GET /risk-profile/{apn}, /healthz)
  lambda_handler.py  # Lambda entry points: handler (direct) + api (Mangum/HTTP)
  logging_config.py  # setup_logging (shared with processing's pattern)
  build_layer.sh     # build the Lambda deps layer (duckdb + extensions + fastapi + mangum + PyYAML)
  requirements.txt
```

## Prod / Lambda

Build + publish the deps layer with [build_layer.sh](build_layer.sh), bundle the
package as the function code, attach the layer, and set `ENV=prod`.

Two handlers — point the Lambda **Handler** at whichever you need:

| Handler | Invocation |
|---|---|
| `proximityProfile.lambda_handler.handler` | direct invoke / Test event `{"apn": "..."}` |
| `proximityProfile.lambda_handler.api` | HTTP via Mangum + a **Function URL** (`GET /risk-profile/{apn}`) |

