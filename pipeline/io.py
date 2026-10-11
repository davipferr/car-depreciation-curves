"""Write loader output to stdout in browser-friendly shapes."""

from __future__ import annotations

import io
import json
import sys

import polars as pl

INT32_MIN, INT32_MAX = -(2**31), 2**31 - 1


def js_safe(df: pl.DataFrame) -> pl.DataFrame:
    """Avoid 64-bit integers, which arrive in JavaScript as BigInt and break Plot/D3.

    Integer columns that fit become Int32; anything larger becomes Float64
    (exact up to 2^53, plenty for codes and counts).
    """
    casts = {}
    for name, dtype in df.schema.items():
        if dtype.is_integer() and dtype not in (pl.Int8, pl.Int16, pl.Int32, pl.UInt8, pl.UInt16):
            col = df[name]
            fits = col.null_count() == len(col) or (col.min() >= INT32_MIN and col.max() <= INT32_MAX)
            casts[name] = pl.Int32 if fits else pl.Float64
        elif dtype == pl.Float32:
            casts[name] = pl.Float64
    return df.cast(casts) if casts else df


def emit_parquet(df: pl.DataFrame) -> None:
    buf = io.BytesIO()
    js_safe(df).write_parquet(buf, compression="zstd", statistics=True)
    sys.stdout.buffer.write(buf.getvalue())
    sys.stdout.buffer.flush()


def emit_json(obj: object) -> None:
    sys.stdout.buffer.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sys.stdout.buffer.flush()


def emit_bytes(data: bytes) -> None:
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
