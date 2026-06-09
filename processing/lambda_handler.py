"""AWS Lambda entry point for the processing module.

Configure the function handler as ``processing.lambda_handler.handler``.

Event:
    {"source": "<registry key>", "as_of": "<optional vintage dir>"}

Returns:
    {"source": ..., "as_of": ..., "output": "<s3:// uri written>"}
"""
from __future__ import annotations

import logging

from .logging_config import setup_logging
from .run import run_one

setup_logging()
logger = logging.getLogger(__name__)


def handler(event, context=None):
    source = event["source"]
    as_of = event.get("as_of")
    logger.info(f"received source={source} as_of={as_of}")
    output = run_one(source, as_of_override=as_of)
    logger.info(f"done source={source} -> {output}")
    result = {"source": source, "output": output}
    if as_of:
        result["as_of"] = as_of
    return result
