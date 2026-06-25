"""Settings for the processing module, the one place that says where data lives.

Two run modes, set by `GIS_ENV`:
    dev   -> local disk, The default.
    prod  -> Amazon S3. Used by Lambda.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Environment. IS_CLOUD is the yes/no the rest of the code checks.
ENV = os.getenv("GIS_ENV", "dev").lower()
IS_CLOUD = ENV in ("prod", "production", "cloud")

# ONLY load dotenv in local dev
if not IS_CLOUD:
    load_dotenv(Path(__file__).with_name(".env"), override=False)

# Dev: local disk paths.
RAW_BASE = Path(os.getenv("GIS_RAW_BASE", r"D:\raw"))
CURATED_BASE = Path(os.getenv("GIS_CURATED_BASE", r"D:\curated"))

# Prod: S3 buckets. A prefix lets raw and curated share one bucket
S3_RAW_BUCKET = os.getenv("GIS_S3_RAW_BUCKET", "low-appeal-agents-us-gis-data")
S3_CURATED_BUCKET = os.getenv("GIS_S3_CURATED_BUCKET", "low-appeal-agents-us-gis-data")
S3_RAW_PREFIX = os.getenv("GIS_S3_RAW_PREFIX", "raw").strip().strip("/")
S3_CURATED_PREFIX = os.getenv("GIS_S3_CURATED_PREFIX", "curated").strip().strip("/")

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")


def backend() -> str:
    """'s3' or 'local' — handy for log lines."""
    return "s3" if IS_CLOUD else "local"
