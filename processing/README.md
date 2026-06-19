# `processing/`: config-driven GIS transform runner

Turns published agency data (FEMA, EPA, USGS, CAL FIRE, …) into curated,
warehouse-ready Parquet. **One engine** reads `registry.yaml` and dispatches
to a per-source transform module. There are no per-source `main.py` files.

Adding a source = **one registry row + one transform file**. Everything else
(IO, CRS normalization, provenance stamping, chunked Parquet writing) is
runner-owned.

The same code runs unchanged on a laptop (`GIS_ENV=dev`, local disk) and in AWS
Lambda (`GIS_ENV=prod`, S3 read in place via GDAL `/vsis3/`).

## Quickstart

```bash
# from the repo root (the package is imported as `processing`)
pip install -r processing/requirements.txt

python -m processing.run --list                       # what's registered + implemented
python -m processing.run flood_fema_nfhl              # run one source (latest vintage)
python -m processing.run flood_fema_nfhl --as-of 2026-04-29   # pin a vintage
python -m processing.run --all                        # every implemented transform
```

## Configuration

Settings live in `.env` (loaded only in dev) and are read by [config.py](config.py).

| Variable | Default | Meaning |
|---|---|---|
| `GIS_ENV` | `dev` | `dev` = local disk; `prod`/`cloud` = S3 |
| `GIS_S3_RAW_BUCKET` / `GIS_S3_RAW_PREFIX` | `low-appeal-agents-us-gis-data` / `raw` | prod raw location |
| `GIS_S3_CURATED_BUCKET` / `GIS_S3_CURATED_PREFIX` | `low-appeal-agents-us-gis-data` / `curated` | prod curated location |

`config.IS_CLOUD` is the single yes/no the rest of the code branches on; only
[storage.py](storage.py) actually knows whether data is on disk or in S3.

## How a run works

`run.run_one(source_key, as_of_override=None)` ([run.py](run.py)):

1. **Look up** the registry row for `source_key`.
2. **Resolve the vintage** (`storage.resolve_as_of`): the pinned date if given
   (CLI `--as-of` beats registry `pinned_as_of`), else the newest date-like
   partition dir under `raw_root`.
3. **Merge the manifest**: read `_manifest.json` from the vintage folder and
   merge it onto the config (**manifest wins on overlap**; `source_as_of` forced
   to the resolved vintage).
4. **Transform**: import `processing.transforms.<source_key>` and call its
   `transform(source_uri=…, config=…)`.
5. **Normalize** (`geom.normalize`): reproject to EPSG:4326, lowercase columns,
   rename geometry to `geometry`, drop & log null/empty geometries.
6. **Stamp provenance** (`metadata.stamp`): add `source_name`, `source_url`,
   `source_as_of`, `loaded_at`.
7. **Write** chunked Parquet (geometry as WKB) to the curated target,
   named `<table>.parquet`.

## Writing a transform

Create `transforms/<source_key>.py` exporting exactly one function. **The module
name must equal the registry key**; that's how the runner and `--list` find it.

```python
def transform(*, source_uri: str, config: dict) -> gpd.GeoDataFrame:
    ...
```

Contract:

- **Return a GeoDataFrame with a CRS set**, keeping only the evidence columns
  you care about.
- **Do not** reproject, lowercase columns, drop empty geometries, or stamp
  provenance; those are runner-owned (steps 5 and 6 above).
- Per-source validity fixes (an explicit, reviewed `make_valid` on a known-bad
  source, etc.) belong here, not in `geom.normalize`.
- Resolve raw files through `storage` helpers (below); never hardcode a path,
  so the same transform works in dev and on S3.

See [transforms/flood_fema_nfhl.py](transforms/flood_fema_nfhl.py) for the
reference (reads a layer from a file-geodatabase inside a zip, in place).

### `storage` helpers for transforms

| Need | Helper |
|---|---|
| List files in the vintage (glob) | `storage.list_vintage_files(raw_root, as_of, "NFHL_*.zip")` |
| GDAL-openable URI (handles `/vsizip/` + `/vsis3/`) | `storage.gdal_uri(raw_root, as_of, filename, inner=…)` |
| Open a raw file as a binary stream | `storage.open_binary(...)` |
| Materialize a file/zip member to local disk | `storage.local_file(...)` / `storage.local_zip_member(...)` |

### Helpers for non-vector sources

- **Flat tables** (CSV/XLSX) → [tabular.py](tabular.py): `read_points(...)` builds
  POINT geometry from lon/lat columns; `from_wkt(...)` parses a WKT column.
- **Rasters** → [raster.py](raster.py): `polygonize(...)` windows a single-band
  raster into severity-class polygons (reclass → optional block-max downsample →
  polygonize) in the raster's native CRS; the runner reprojects.

## `_manifest.json` (one per vintage folder)

Hand-authored by whoever drops new raw data; read-only to the runner. Supplies
the four mandatory Phase-1 metadata fields plus an audit trail:

```json
{
  "source_as_of": "2026-04-30",
  "source_as_of_observed_text": "Effective Date: April 30, 2026",
  "observed_at_url": "https://hazards.fema.gov/femaportal/NFHL/searchResult",
  "retrieved_at": "2026-05-15T14:22:00Z",
  "files": ["NFHL_06_20260429.gdb/"]
}
```

A new vintage needs **zero code change**: name a new partition dir with the
observed date, drop a `_manifest.json`, and the next run picks it up. For a
month with no day ("Last updated: April 2026"), use the first day of the period
(`2026-04-01`) in the dir name and keep the verbatim text.

## Layout

```
processing/
  run.py              # CLI + run_one / run_all / --list
  lambda_handler.py   # AWS Lambda entry point (processing.lambda_handler.handler)
  config.py           # env-driven settings; dev vs prod switch
  storage.py          # the only layer that knows local-disk vs S3
  geom.py             # runner-owned normalize (CRS, columns, drop empties)
  metadata.py         # runner-owned provenance stamp
  tabular.py          # CSV/XLSX/WKT -> GeoDataFrame helpers
  raster.py           # raster -> class-polygon helper
  registry.yaml       # one row per source (the STTM backbone)
  transforms/         # one module per source_key; the only source-specific code
```

## Paths in & out
- **Curated (prod):**
`s3://<curated_bucket>/curated/<schema>/<table>/<as_of>/<table>.parquet`

Curated output is plain Parquet with geometry as **WKB**; it carries **no CRS**.
The warehouse load re-asserts EPSG:4326 (`ST_GeomFromWKB(geom, 4326)`). Read it
back with pandas + `shapely.from_wkb`.

## Prod / Lambda

Configure the function handler as `processing.lambda_handler.handler`. Event:

```json
{"source": "flood_fema_nfhl", "as_of": "2026-04-29"}
```

(`as_of` optional). The container image is built from [Dockerfile](Dockerfile)
(AWS Lambda Python 3.13 base). One source per invocation; Lambda's 10 GB ceiling
is per-call, so it's bounded by the single biggest source.
