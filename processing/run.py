"""Config-driven transform runner.

One engine reads ``registry.yaml`` and dispatches to a per-source transform
module. The backend (local dev vs S3 prod) is chosen by GIS_ENV in .env and is
fully hidden inside ``storage.py`` — the same command runs in both.

Usage:
    python -m processing.run --list
    python -m processing.run flood_fema_nfhl
    python -m processing.run flood_fema_nfhl --as-of 2026-04-29
"""
from __future__ import annotations

import argparse
import importlib
import time

import yaml

from . import config, geom, metadata, storage
from .config import REGISTRY_PATH
from .logging_config import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)


def load_registry() -> dict:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", {})


def run_one(source_key: str, *, as_of_override: str | None = None) -> str:
    registry = load_registry()
    if source_key not in registry:
        raise KeyError(
            f"'{source_key}' not in registry. Known: {sorted(registry)}"
        )

    cfg = dict(registry[source_key])
    raw_root = cfg["raw_root"]
    as_of = storage.resolve_as_of(
        raw_root, pin=as_of_override or cfg.get("pinned_as_of")
    )

    # Manifest (vintage truth) overrides the registry row where they overlap.
    manifest = storage.read_manifest(raw_root, as_of)
    cfg = {**cfg, **manifest, "source_as_of": as_of}

    logger.info(f"backend={config.backend()}")
    logger.info(f"{source_key} as_of={as_of}")
    logger.info(f"src={storage.raw_uri(raw_root, as_of)}")

    t_start = time.perf_counter()
    module = importlib.import_module(f"processing.transforms.{source_key}")
    src = storage.raw_uri(raw_root, as_of)

    t0 = time.perf_counter()
    gdf = module.transform(source_uri=src, config=cfg)
    t_transform = time.perf_counter() - t0
    logger.info(f"transform -> {len(gdf):,} rows, crs={gdf.crs}")

    gdf = geom.normalize(gdf)
    gdf = metadata.stamp(
        gdf,
        source_name=cfg["source_name"],
        source_url=cfg["source_url"],
        source_as_of=as_of,
    )
    target = storage.curated_target(cfg["schema"], cfg["table"], as_of)
    storage.ensure_parent(target)

    t0 = time.perf_counter()
    gdf.to_parquet(target, index=False)  # GeoParquet (WKB geometry)
    t_write = time.perf_counter() - t0

    t_total = time.perf_counter() - t_start
    logger.info(
        f"wrote {len(gdf):,} rows "
        f"({len(gdf.columns)} cols, WKB geom) -> {target}"
    )
    logger.info(
        f"timing {source_key}: total={t_total:.1f}s "
        f"(transform={t_transform:.1f}s, write={t_write:.1f}s)"
    )
    return target


def _transform_exists(key: str) -> bool:
    try:
        importlib.import_module(f"processing.transforms.{key}")
        return True
    except ModuleNotFoundError:
        return False


def run_all(*, as_of_override: str | None = None) -> int:
    """Run every source that has a transform, sequentially (local batch).

    Continues past a failing source and reports a summary at the end, so one
    bad source doesn't abort the whole run. This is the LOCAL convenience path
    only — in prod, Step Functions fans one Lambda per source instead (a single
    process looping all sources would blow Lambda's per-invocation limits).
    """
    registry = load_registry()
    keys = [k for k in sorted(registry) if _transform_exists(k)]
    skipped = [k for k in sorted(registry) if not _transform_exists(k)]
    if skipped:
        logger.info(f"skipping {len(skipped)} registry-only row(s): {skipped}")
    if not keys:
        logger.info("no transforms implemented yet — nothing to run.")
        return 0

    logger.info(f"running {len(keys)} source(s): {keys}\n")
    ok: list[str] = []
    failed: list[tuple[str, str]] = []
    t_start = time.perf_counter()
    for key in keys:
        try:
            run_one(key, as_of_override=as_of_override)
            ok.append(key)
        except Exception as e:  # batch run: report and keep going
            failed.append((key, repr(e)))
            logger.error(f"FAILED {key}: {e!r}")

    t_total = time.perf_counter() - t_start
    logger.info(
        f"done: {len(ok)} ok, {len(failed)} failed "
        f"in {t_total:.1f}s"
    )
    for key, err in failed:
        logger.info(f"  - {key}: {err}")
    return 1 if failed else 0


def _list() -> None:
    reg = load_registry()
    width = max((len(k) for k in reg), default=0)
    logger.info(f"backend: {config.ENV} ({config.backend()})\n")
    for key in sorted(reg):
        v = reg[key]
        flag = "x" if _transform_exists(key) else " "
        logger.info(
            f"[{flag}] {key:<{width}}  "
            f"schema={str(v.get('schema')):<14} "
            f"pattern={v.get('pattern', '?')}  {v.get('raw_root')}"
        )
    logger.info("\n[x] = transform implemented; [ ] = registry row only")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="processing.run")
    p.add_argument("source", nargs="?", help="registry source key")
    p.add_argument("--as-of", dest="as_of", help="override vintage")
    p.add_argument("--list", action="store_true", help="list sources")
    p.add_argument(
        "--all",
        action="store_true",
        help="run every implemented transform (local batch)",
    )
    args = p.parse_args(argv)

    if args.list:
        _list()
        return 0
    if args.all:
        if args.source:
            p.error("--all takes no source argument")
        return run_all(as_of_override=args.as_of)
    if not args.source:
        p.error("provide a source key, or use --list / --all")
    run_one(args.source, as_of_override=args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
