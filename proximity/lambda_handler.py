"""AWS Lambda entry point for the proximity service.

Set the Lambda Handler to:  proximity.handler.handler
Invoke with: {"apn": "..."}

Deps (duckdb + spatial/httpfs extensions + PyYAML) come from the attached
layer; set the function env var ENV=prod so backends reads from S3.
"""
from __future__ import annotations

from .runner import proximity


def handler(event, context):
    return proximity(event["apn"])
