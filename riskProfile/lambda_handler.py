"""AWS Lambda entry point for the proximity service.

Set the Lambda Handler to:  proximity.lambda_handler.handler
Invoke with: {"apn": "..."}

Deps (duckdb + spatial/httpfs extensions + PyYAML) come from the attached
layer; set the function env var ENV=prod so backends reads from S3.
"""
from __future__ import annotations

import logging

from .logging_config import setup_logging
from .runner import proximity

setup_logging()
logger = logging.getLogger(__name__)


def handler(event, context):
    logger.info("event=%s", event)
    try:
        return proximity(event["apn"])
    except Exception:
        logger.exception("proximity failed")
        raise
