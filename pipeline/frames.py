"""Cleaned, shared frames, memoised as Parquet in the cache directory.

Every loader needs the same catalogue and price panel. Rebuilding them reads
thousands of cached JSON responses, so each frame is built once and reused for
``max_age``.

File names carry a hash of the ``pipeline`` source, so editing any cleaning,
matching or model code invalidates every memoised frame at once, instead of
serving a frame built by older code until ``max_age`` runs out.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import polars as pl

from . import fipe, painel
from .http import CACHE_DIR, log

FRAMES = CACHE_DIR / "frames"


def _code_version() -> str:
    """Short hash of every module in this package (line endings normalised, so a
    Windows checkout and CI agree)."""
    h = hashlib.sha256()
    for src in sorted(Path(__file__).parent.glob("*.py")):
        h.update(src.name.encode())
        h.update(src.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


CODE_VERSION = _code_version()


def memo(name: str, build: Callable[[], pl.DataFrame], max_age: timedelta = timedelta(hours=12)) -> pl.DataFrame:
    path = FRAMES / f"{name}-{CODE_VERSION}.parquet"
    if path.exists() and time.time() - path.stat().st_mtime < max_age.total_seconds():
        return pl.read_parquet(path)
    t0 = time.time()
    df = build()
    FRAMES.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.part")
    df.write_parquet(tmp)
    tmp.replace(path)
    # Drop copies built by other code versions (and the old unversioned name).
    # Matched exactly, so "catalogo-2014-4" never deletes a partial build's
    # "catalogo-2014-4-<families hash>".
    stale = re.compile(rf"{re.escape(name)}(-[0-9a-f]{{12}})?\.parquet")
    for old in FRAMES.glob(f"{name}*.parquet"):
        if old != path and stale.fullmatch(old.name):
            old.unlink(missing_ok=True)
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
