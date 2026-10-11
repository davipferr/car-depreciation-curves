"""Build metadata and data-quality report: catalogue coverage, family matching, request counts, misses."""

import json
from datetime import datetime, timezone

import polars as pl

from pipeline import catalogo, fipe, frames, painel
from pipeline.clean import ZERO_KM
from pipeline.io import emit_json

refs = frames.referencias()
ref = int(refs["ref"][-1])
cat = frames.catalogo()
precos = frames.precos()
atual = frames.atual()
consultas = painel.consultas(cat, refs)

# Every version of the tracked brands (all cached by now), to show what the family patterns leave out.
marcas = fipe.marcas(ref)
codes = marcas.filter(pl.col("marca").is_in(catalogo.MARCAS))["marca_code"]
bruto = pl.concat([fipe.catalogo_marca(ref, c, painel.ANO_MIN) for c in codes])
sem = catalogo.classificar(bruto, dict(marcas.iter_rows())).filter(pl.col("familia").is_null())
sem_familia = (
    sem.drop("marca").join(marcas, on="marca_code")
    .with_columns(
        pl.col("marca").replace(catalogo.MARCA_CURTA),pl.col("versao").str.extract(r"^(\S+)").str.to_uppercase().alias("modelo"))
    .group_by("marca", "modelo")
    .agg(pl.col("modelo_code").n_unique().alias("versoes"))
    .sort("versoes", "marca", "modelo", descending=[True, False, False])
    .head(20)
)


def contagem(col: str) -> list[dict]:
    return atual.group_by(col).agg(pl.len().alias("precos")).sort("precos", descending=True).rename({col: "grupo"}).to_dicts()


report = {
    "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "referencia": {
        "codigo": ref,
        "mes": refs["mes"][-1],
        "primeira": refs["mes"][0],
        "meses": refs.height,
    },
    "parametros": {"ano_min": painel.ANO_MIN, "versoes_por_familia": painel.VERSOES},
    "catalogo": {
        "familias": cat["familia"].n_unique(),
        "marcas": cat["marca"].n_unique(),
        "linhas_marcas": bruto.height,
        "linhas_familias": cat.height,
        "versoes_marcas": bruto["modelo_code"].n_unique(),
        "versoes_familias": cat["modelo_code"].n_unique(),
        "zero_km": cat.filter(pl.col("ano_modelo") == ZERO_KM).height,
        "sem_familia": sem_familia.to_dicts(),
    },
    "consultas": {"total": consultas.height, "com_preco": precos.height, "sem_preco": consultas.height - precos.height},
    "painel": {
        "precos_atual": atual.height,
        "series_atual": atual.select(painel.SERIE).n_unique(),
        "precos_historico": precos.filter(pl.col("mes") < atual["mes"].max()).height,
        "cambio": contagem("cambio"),
        "propulsao": contagem("propulsao"),
    },
}
emit_json(json.loads(json.dumps(report, default=str)))
