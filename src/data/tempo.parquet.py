"""How the market moved: same-car price change between Januaries (used and zero km), with the IPCA of the same 12 months."""

import polars as pl

from pipeline import bcb, curvas, frames
from pipeline.io import emit_parquet

hist = frames.historico()

var = pl.concat(
    [curvas.variacao_anual(hist).with_columns(pl.lit("Todos").alias("segmento")), curvas.variacao_anual(hist, ["segmento"])],
    how="diagonal",
).with_columns(pl.col("ano_ref").cast(pl.Int32))
ipca = (
    bcb.ipca_12m(int(var["ano_ref"].min()) - 1)
    .filter(pl.col("mes").dt.month() == 1)
    .select(pl.col("mes").dt.year().cast(pl.Int32).alias("ano_ref"), "ipca_12m")
)
out = var.join(ipca, on="ano_ref", how="left")
cols = ["segmento", "condicao", "ano_ref", "var_nominal", "var_real", "n_carros", "ipca_12m"]
emit_parquet(out.select(cols).sort("segmento", "condicao", "ano_ref"))
