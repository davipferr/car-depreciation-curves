"""The same model fitted on pooled versions, grouped by segment, brand, transmission, powertrain, turbo and price band."""

import polars as pl

from pipeline import curvas, frames
from pipeline.io import emit_parquet

atual = frames.atual()
pooled = curvas.ajuste(atual, [])["b_novo"][0]

# Price band of each version by its estimated new price (the same for all its model years).
FAIXAS = [
    (0, 100_000, "até R$ 100 mil"),
    (100_000, 150_000, "R$ 100–150 mil"),
    (150_000, 250_000, "R$ 150–250 mil"),
    (250_000, float("inf"), "acima de R$ 250 mil"),
]
faixa = pl.lit(None, pl.String)
for lo, hi, nome in reversed(FAIXAS):
    faixa = pl.when((pl.col("preco_novo_est") >= lo) & (pl.col("preco_novo_est") < hi)).then(pl.lit(nome)).otherwise(faixa)

atual = curvas.com_retencao(atual, ["familia"], curvas.ajuste(atual, ["familia"])).with_columns(
    faixa.alias("faixa_preco"),
    pl.when(pl.col("turbo")).then(pl.lit("Turbo")).otherwise(pl.lit("Aspirado")).alias("motor_tipo"),
)

DIMENSOES = {
    "segmento": "Segmento",
    "marca": "Marca",
    "cambio": "Câmbio",
    "propulsao": "Combustível",
    "motor_tipo": "Motor",
    "faixa_preco": "Preço de novo",
}
partes = []
for col, nome in DIMENSOES.items():
    fit = curvas.ajuste(atual, [col])
    partes.append(
        fit.with_columns(curvas.retencao_em(fit, 5, pooled).alias("retencao_5"))
        .rename({col: "grupo"})
        .with_columns(pl.lit(nome).alias("dimensao"))
    )

ordem = {nome: i for i, (*_, nome) in enumerate(FAIXAS)}
out = pl.concat(partes).with_columns(pl.col("grupo").replace_strict(ordem, default=None, return_dtype=pl.Int32).alias("ordem"))
emit_parquet(out.select("dimensao", "grupo", "ordem", "taxa_anual", "perda_imediata", "retencao_5", "n_series", "n_precos"))
