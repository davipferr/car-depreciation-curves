"""Every version in the sample: family, brand, segment and attributes parsed from the FIPE name."""

import polars as pl

from pipeline import frames
from pipeline.clean import ZERO_KM
from pipeline.io import emit_parquet
from pipeline.painel import SERIE, VERSOES

cat = frames.catalogo().filter(pl.col("rank") < VERSOES)
usados = pl.col("ano_modelo").filter(pl.col("ano_modelo") != ZERO_KM)
versoes = cat.group_by(SERIE).agg(
    pl.col("familia", "marca", "segmento", "versao", "motor", "turbo", "cambio", "propulsao", "rank").first(),
    usados.min().alias("primeiro_ano"),
    usados.max().alias("ultimo_ano"),
    (pl.col("ano_modelo") == ZERO_KM).any().alias("vendido_zero_km"),
)
emit_parquet(versoes.with_columns((pl.col("rank") == 0).alias("carro_chefe")).sort("familia", "rank", "combustivel_code"))
