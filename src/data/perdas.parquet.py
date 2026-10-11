"""Share of value lost in each year of a car's life (adjacent model years, latest table): per family, per segment and overall."""

import polars as pl

from pipeline import curvas, frames
from pipeline.io import emit_parquet

atual = frames.atual().with_columns(pl.lit("Todos").alias("todos"))
partes = [
    curvas.perdas_por_idade(atual, [col]).rename({col: "grupo"}).with_columns(pl.lit(col).alias("nivel"))
    for col in ("familia", "segmento", "todos")
]
emit_parquet(pl.concat(partes).select("nivel", "grupo", "idade", "perda_mediana", "n_pares"))
