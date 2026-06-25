"""Minimal FastAPI wrapper over the risk-profile runner.

Then:
    GET /proximity/5426020012     -> the parcel's risk profile JSON
    GET /healthz                     -> liveness check
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .logging_config import setup_logging
from .runner import proximity

setup_logging()

app = FastAPI(title="LowPropTax Risk Profile", version="0.1.0")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/risk-profile/{apn}")
def risk_profile(apn: str) -> dict:
    """Return every risk factor affecting the parcel for this APN."""
    try:
        return proximity(apn)
    except KeyError as e:                       # APN not in the parcel store
        raise HTTPException(status_code=404, detail=str(e))
