"""The price panel: latest FIPE table for the sampled versions, plus each flagship's January prices since launch.

Rows of the latest month also carry ``retencao`` (price / estimated new price of
the same version) and ``preco_novo_est``.
"""

import polars as pl

from pipeline import curvas, frames
from pipeline.io import emit_parquet

atual = frames.atual()
atual = curvas.com_retencao(atual, ["familia"], curvas.ajuste(atual, ["familia"]))

cols = [
    "familia", "marca", "segmento", "modelo_code", "combustivel_code", "ano_modelo", "zero_km",
    "mes", "idade", "preco", "preco_real", "retencao", "preco_novo_est", "rank",
]
passado = (
    frames.precos()
    .filter(pl.col("mes") < atual["mes"].max())
    .with_columns(pl.lit(None, pl.Float64).alias("retencao"), pl.lit(None, pl.Float64).alias("preco_novo_est"))
)
precos = pl.concat([atual.select(cols), passado.select(cols)])
emit_parquet(precos.sort("familia", "modelo_code", "combustivel_code", "mes", "ano_modelo", nulls_last=True))
