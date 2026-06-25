"""Proximity source registry — load `registry.yaml` into typed Source specs.

The runner iterates these to build one proximity query per source. Adding a
source is a single entry in registry.yaml; no code change here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")


@dataclass(frozen=True)
class Source:
    key: str
    schema: str
    table: str
    attributes: list[str]
    radius_m: int
    type: str = "proximity"
    mode: str = "feature"
    group_by: str | None = None
    filter: str | None = None
    collapse: bool = False

    @property
    def columns(self) -> list[str]:
        """Columns the query needs from the source relation."""
        if self.mode == "count":
            return [self.group_by] if self.group_by else []
        return self.attributes


def _load() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_sources() -> list[Source]:
    """All registered sources as Source specs (radius falls back to the default)."""
    reg = _load()
    default_r = reg.get("default_radius_m", 1000)
    out: list[Source] = []
    for key, cfg in (reg.get("sources") or {}).items():
        out.append(
            Source(
                key=key,
                schema=cfg["schema"],
                table=cfg["table"],
                attributes=list(cfg.get("attributes", [])),
                radius_m=cfg.get("radius_m", default_r),
                type=cfg.get("type", "proximity"),
                mode=cfg.get("mode", "feature"),
                group_by=cfg.get("group_by"),
                filter=cfg.get("filter"),
                collapse=cfg.get("collapse", False),
            )
        )
    return out


def get_source(key: str) -> Source:
    for s in list_sources():
        if s.key == key:
            return s
    raise KeyError(f"'{key}' not in proximity registry. Known: {[s.key for s in list_sources()]}")