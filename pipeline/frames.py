"""Cleaned, shared frames, memoised as Parquet in the cache directory.

Every loader needs the same catalogue and price panel. Rebuilding them reads
thousands of cached JSON responses, so each frame is built once and reused for
``max_age``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import timedelta

import polars as pl

from . import fipe, painel
from .http import CACHE_DIR, log

FRAMES = CACHE_DIR / "frames"


def memo(name: str, build: Callable[[], pl.DataFrame], max_age: timedelta = timedelta(hours=12)) -> pl.DataFrame:
    path = FRAMES / f"{name}.parquet"
    if path.exists() and time.time() - path.stat().st_mtime < max_age.total_seconds():
        return pl.read_parquet(path)
    t0 = time.time()
    df = build()
    FRAMES.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.part")
    df.write_parquet(tmp)
    tmp.replace(path)
    log(f"frame {name}: {df.height:,} rows in {time.time() - t0:.1f}s")
    return df


def referencias() -> pl.DataFrame:
    return memo("referencias", fipe.referencias, timedelta(hours=12))


def catalogo() -> pl.DataFrame:
    return memo(f"catalogo-{painel.TAG}", lambda: painel.catalogo_completo(int(referencias()["ref"][-1])))


def precos() -> pl.DataFrame:
    return memo(f"precos-{painel.TAG}", lambda: painel.precos(catalogo(), referencias()))


def atual() -> pl.DataFrame:
    """The cross-section: prices in the latest reference month only."""
    p = precos()
    return p.filter(pl.col("mes") == p["mes"].max())


def historico() -> pl.DataFrame:
    """The flagship series in every reference month (the part of the panel that follows cars over time)."""
    return precos().filter(pl.col("rank") == 0)
