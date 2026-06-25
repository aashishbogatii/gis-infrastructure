# LowPropTax — GIS Risk Data Infrastructure

A parcel-indexed **risk database** for property tax appeals. It proves that
environmental, climate, infrastructure, and socioeconomic factors lower a
property's market value relative to its assessment, and turns that into a
defensible percentage adjustment for the appraisal grid.

**Goal:** given an APN or a (lat, lon), return every authoritative risk factor
affecting that parcel, the distance to each risk source, and a percentage
adjustment ready for a Board of Equalization. California first; US scaffolded.

## Architecture

```
Source agencies (FEMA, EPA, USGS, CAL FIRE, …)
  → Python preprocessing (geopandas: reproject, clean, simplify → Parquet)
  → S3 (raw + curated, partitioned by as_of date)
  → Warehouse (Duckdb + S3 for now)
  → proximityProfile: APN → spatial joins over every source → risk-profile JSON
  → Adjustment model
```

## Repository layout

```
processing/        the config-driven transform runner — see processing/README.md
proximityProfile/  on-demand parcel risk-profile service — see proximityProfile/README.md
```

## Where to go next

- **Run or extend the data pipeline** → [processing/README.md](processing/README.md).
  One engine reads `registry.yaml` and dispatches per-source transforms; adding a
  source is one registry row plus one transform file.
- **Query a parcel's risk factors** → [proximityProfile/README.md](proximityProfile/README.md).
  Given an APN, runs a registry-driven spatial query per source against the curated
  Parquet and returns the parcel's risk-profile JSON.
