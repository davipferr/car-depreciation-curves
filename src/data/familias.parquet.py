"""One row per family: annual depreciation, loss when leaving the dealership, model retention after 3 and 5 years."""

import polars as pl

from pipeline import curvas, frames
from pipeline.io import emit_parquet

atual = frames.atual()
fit = curvas.ajuste(atual, ["familia"])
pooled = curvas.ajuste(atual, [])["b_novo"][0]
ret = curvas.com_retencao(atual, ["familia"], fit)

info = atual.group_by("familia").agg(
    pl.col("marca", "segmento").first(),
    pl.col("propulsao").mode().first().alias("propulsao"),
    (pl.col("cambio") == "Automático").mean().alias("parcela_automatico"),
    pl.col("zero_km").any().alias("vendido_zero_km"),
    pl.col("ano_modelo").min().alias("ano_mais_antigo"),
)
novo = ret.group_by("familia").agg(pl.col("preco_novo_est").median().alias("preco_novo_mediano"))

out = (
    fit.join(info, on="familia")
    .join(novo, on="familia")
    .with_columns(
        curvas.retencao_em(fit, 3, pooled).alias("retencao_3"),
        curvas.retencao_em(fit, 5, pooled).alias("retencao_5"),
        # The zero-km premium the curves use: the pooled one when the family has none.
        pl.col("b_novo").fill_null(pooled).alias("b_novo_efetivo"),
    )
    .sort("taxa_anual")
)
emit_parquet(out)
