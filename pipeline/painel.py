"""Which FIPE prices to fetch, and the cleaned price panel built from them.

Pricing every version of every family in every month would take hundreds of
thousands of requests, so the panel is a deliberate sample:

* **current table** - for each family, the ``VERSOES`` versions with the most
  model years in the catalogue (long-lived versions give the cleanest curves),
  priced for every model year in the latest reference month. This is the
  cross-section behind the depreciation curves and rankings.
* **history** - for each family's *flagship* (its top-ranked version), every
  model year priced in January of each year since it was launched, plus the
  zero-km price in each of those Januaries. This follows the same car through
  time, and is what shows the 2021-22 used-car boom.

A *series* is one FIPE version with one fuel: ``modelo_code`` + ``combustivel_code``.
"""

from __future__ import annotations

import hashlib
import os

import polars as pl

from . import bcb, catalogo, fipe
from .clean import ZERO_KM
from .http import log

ANO_MIN = int(os.environ.get("CDC_ANO_MIN", "2014"))
VERSOES = int(os.environ.get("CDC_VERSOES", "4"))
# Comma-separated family names for a quick partial build ("Onix,HB20,Gol"); empty = all.
FAMILIAS = [f.strip() for f in os.environ.get("CDC_FAMILIAS", "").split(",") if f.strip()]
# Memoised frames depend on the sample, so their file names carry it.
TAG = f"{ANO_MIN}-{VERSOES}" + (f"-{hashlib.sha256(','.join(sorted(FAMILIAS)).encode()).hexdigest()[:8]}" if FAMILIAS else "")

SERIE = ["marca_code", "modelo_code", "combustivel_code"]


def catalogo_completo(ref: int) -> pl.DataFrame:
    """Every (version, model year, fuel) of the tracked families since ``ANO_MIN``, classified and ranked.

    ``rank`` orders the versions of each family by number of model years (then by
    most recent model year, then code), so rank 0 is the family's flagship.
    """
    marcas = fipe.marcas(ref)
    por_nome = dict(zip(marcas["marca"], marcas["marca_code"], strict=True))
    faltando = set(catalogo.MARCAS) - set(por_nome)
    if faltando:
        log(f"FIPE: brands not found, their families are skipped: {sorted(faltando)}")
    desconhecidas = set(FAMILIAS) - {f.nome for f in catalogo.FAMILIAS}
    if desconhecidas:
        raise ValueError(f"CDC_FAMILIAS: unknown families {sorted(desconhecidas)}")
    marcas_usadas = {f.marca for f in catalogo.FAMILIAS if not FAMILIAS or f.nome in FAMILIAS}
    partes = []
    for nome in catalogo.MARCAS:
        if nome in por_nome and nome in marcas_usadas:
            log(f"FIPE: catalogue {nome}")
            partes.append(fipe.catalogo_marca(ref, por_nome[nome], ANO_MIN))
    cat = catalogo.classificar(pl.concat(partes), dict(zip(marcas["marca_code"], marcas["marca"], strict=True)))
    cat = cat.filter(pl.col("familia").is_in(FAMILIAS) if FAMILIAS else pl.col("familia").is_not_null())

    usados = pl.col("ano_modelo").filter(pl.col("ano_modelo") != ZERO_KM)
    rank = (
        cat.group_by("familia", "modelo_code")
        .agg(pl.col("ano_modelo").n_unique().alias("n_anos"), usados.max().alias("ultimo_ano"))
        .sort(["familia", "n_anos", "ultimo_ano", "modelo_code"], descending=[False, True, True, False], nulls_last=True)
        .with_columns(pl.int_range(pl.len()).over("familia").cast(pl.Int32).alias("rank"))
    )
    return cat.join(rank, on=["familia", "modelo_code"])


def consultas(cat: pl.DataFrame, refs: pl.DataFrame) -> pl.DataFrame:
    """The (ref, series, model year) requests for both parts of the panel."""
    atual = refs["ref"][-1]
    janeiros = refs.filter(pl.col("mes").dt.month() == 1, pl.col("mes").dt.year() >= ANO_MIN).select(
        "ref", pl.col("mes").dt.year().alias("ano_ref")
    )
    cols = ["ref", "marca_code", "modelo_code", "ano_modelo", "combustivel_code"]

    corte = cat.filter(pl.col("rank") < VERSOES).with_columns(pl.lit(atual, pl.Int32).alias("ref")).select(cols)

    chefe = cat.filter(pl.col("rank") == 0)
    usados = (
        chefe.filter(pl.col("ano_modelo") != ZERO_KM)
        .join(janeiros, how="cross")
        .filter(pl.col("ano_ref") >= pl.col("ano_modelo"))
        .select(cols)
    )
    # Zero km in every January the flagship was on sale (first to last model year).
    vida = chefe.filter(pl.col("ano_modelo") != ZERO_KM).group_by(SERIE).agg(
        pl.col("ano_modelo").min().alias("de"), pl.col("ano_modelo").max().alias("ate")
    )
    novos = (
        vida.join(janeiros, how="cross")
        .filter(pl.col("ano_ref").is_between(pl.col("de"), pl.col("ate")))
        .with_columns(pl.lit(ZERO_KM, pl.Int32).alias("ano_modelo"))
        .select(cols)
    )
    return pl.concat([corte, usados, novos]).unique()


def precos(cat: pl.DataFrame, refs: pl.DataFrame) -> pl.DataFrame:
    """Price panel: one row per (series, model year, reference month) with a FIPE price.

    Adds ``mes``, ``zero_km``, ``idade`` (age in years at the reference month;
    0 for zero km) and ``preco_real`` (in reais of the last month with IPCA).
    """
    q = consultas(cat, refs)
    p = fipe.precos(q).filter(pl.col("preco") > 0)

    series = cat.select(
        "marca_code", "modelo_code", "combustivel_code", "familia", "marca", "segmento", "categoria", "versao",
        "motor", "turbo", "cambio", "propulsao", "rank",
    ).unique(SERIE)
    p = p.join(refs, on="ref").join(series, on=SERIE)

    zero = pl.col("ano_modelo") == ZERO_KM
    # A model year Y car is ~0 years old in January of Y; next year's model
    # (sold from mid-year) would come out negative, so age is floored at 0.
    idade = (pl.col("mes").dt.year() - pl.col("ano_modelo")) + (pl.col("mes").dt.month() - 1) / 12
    p = p.with_columns(
        zero.alias("zero_km"),
        pl.when(zero).then(None).otherwise(pl.col("ano_modelo")).alias("ano_modelo"),
        pl.when(zero).then(0.0).otherwise(idade.clip(lower_bound=0)).cast(pl.Float64).alias("idade"),
    )
    p = p.join(bcb.deflator(p["mes"]), on="mes", how="left").with_columns(
        (pl.col("preco") * pl.col("deflator")).alias("preco_real")
    ).drop("deflator")
    log(f"panel: {p.height:,} prices for {p.select(SERIE).n_unique():,} series")
    return p.sort("familia", "modelo_code", "combustivel_code", "mes", "ano_modelo")
