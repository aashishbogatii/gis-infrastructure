"""AWS Lambda entry points for the proximity service.
"""

from __future__ import annotations

import logging

from mangum import Mangum

from .logging_config import setup_logging
from .runner import proximity
from .server import app

setup_logging()
logger = logging.getLogger(__name__)


def handler(event, context):
    """Direct invoke: event is the payload, e.g. {"apn": "..."}."""
    logger.info("event=%s", event)
    try:
        return proximity(event["apn"])
    except Exception:
        logger.exception("proximity failed")
        raise


api = Mangum(app)
