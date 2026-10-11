"""Depreciation statistics from the price panel.

The core model, fitted separately for each group (a family, a segment, a
brand...) on one reference month:

    log(price) = a[series] + b * age + c * zero_km

* ``a[series]`` is a fixed effect per FIPE version, so a Premier and a Joy of
  the same family aren't compared with each other - only each version with
  its own older model years;
* ``b`` is the yearly log change in price: ``1 - exp(b)`` is the **annual
  depreciation rate** of a used car;
* ``c`` is the premium of a brand-new car over a barely used one of the same
  version: ``1 - exp(-c)`` is the loss **when it leaves the dealership**.

Estimated by OLS on within-series demeaned variables (the "within"
estimator), which needs only sums and a 2x2 solve, so it runs as a plain
Polars aggregation. Families with no zero-km price left (discontinued models)
can't identify ``c``; their retention uses the pooled ``c`` of all families.
"""

from __future__ import annotations

import polars as pl

from .painel import SERIE

EPS = 1e-9


def _within(df: pl.DataFrame) -> pl.DataFrame:
    """Add y, x1 (age), x2 (zero km) and their within-series deviations."""
    d = df.with_columns(
        pl.col("preco").log().alias("y"),
        pl.col("idade").alias("x1"),
        pl.col("zero_km").cast(pl.Float64).alias("x2"),
    )
    return d.with_columns(
        *[(pl.col(c) - pl.col(c).mean().over(SERIE)).alias(f"{c}d") for c in ("y", "x1", "x2")],
        pl.len().over(SERIE).alias("n_serie"),
    )


def ajuste(df: pl.DataFrame, por: list[str]) -> pl.DataFrame:
    """Fit the model for each group in ``por`` (``[]`` = one pooled fit).

    Returns ``b_idade``, ``b_novo`` (null when no series has both a zero-km and
    a used price), ``taxa_anual``, ``perda_imediata``, ``n_series`` (series with
    2+ prices, the ones that inform the fit), ``n_precos`` and the age range.
    """
    d = _within(df)
    chave = por or [pl.lit(1).alias("_todos")]
    s = d.group_by(chave).agg(
        (pl.col("x1d") ** 2).sum().alias("s11"),
        (pl.col("x2d") ** 2).sum().alias("s22"),
        (pl.col("x1d") * pl.col("x2d")).sum().alias("s12"),
        (pl.col("x1d") * pl.col("yd")).sum().alias("s1y"),
        (pl.col("x2d") * pl.col("yd")).sum().alias("s2y"),
        pl.struct(SERIE).filter(pl.col("n_serie") > 1).n_unique().alias("n_series"),
        pl.len().alias("n_precos"),
        pl.col("idade").filter(~pl.col("zero_km")).max().alias("idade_max"),
    )
    det = pl.col("s11") * pl.col("s22") - pl.col("s12") ** 2
    com_novo = (pl.col("s22") > EPS) & (det > EPS)
    s = s.with_columns(
        pl.when(com_novo)
        .then((pl.col("s22") * pl.col("s1y") - pl.col("s12") * pl.col("s2y")) / det)
        .when(pl.col("s11") > EPS)
        .then(pl.col("s1y") / pl.col("s11"))
        .alias("b_idade"),
        pl.when(com_novo).then((pl.col("s11") * pl.col("s2y") - pl.col("s12") * pl.col("s1y")) / det).alias("b_novo"),
    )
    s = s.with_columns(
        (1 - pl.col("b_idade").exp()).alias("taxa_anual"),
        (1 - (-pl.col("b_novo")).exp()).alias("perda_imediata"),
    )
    cols = [*(por or []), "b_idade", "b_novo", "taxa_anual", "perda_imediata", "n_series", "n_precos", "idade_max"]
    return s.select(cols).sort(por) if por else s.select(cols)


def com_retencao(df: pl.DataFrame, por: list[str], ajustes: pl.DataFrame) -> pl.DataFrame:
    """Add ``retencao``: each price as a share of its version's *estimated new price*.

    The new price of a series is ``exp(a[series] + c)``; with ``a`` recovered as
    the series mean of ``y - b*age - c*zero_km``. When the group has no ``c``,
    the pooled one is used. Also adds ``preco_novo_est``.
    """
    pooled = ajuste(df, [])["b_novo"][0]
    d = df.join(ajustes.select(*por, "b_idade", "b_novo"), on=por, how="left").with_columns(
        pl.col("b_novo").fill_null(pooled)
    )
    a = (pl.col("preco").log() - pl.col("b_idade") * pl.col("idade") - pl.col("b_novo") * pl.col("zero_km").cast(pl.Float64)).mean().over(SERIE)
    novo = (a + pl.col("b_novo")).exp()
    return d.with_columns(novo.alias("preco_novo_est")).with_columns(
        (pl.col("preco") / pl.col("preco_novo_est")).alias("retencao")
    ).drop("b_idade", "b_novo")


def retencao_em(ajustes: pl.DataFrame, anos: float, pooled_b_novo: float) -> pl.Expr:
    """Model retention after ``anos`` years: exp(b*t - c)."""
    c = pl.col("b_novo").fill_null(pooled_b_novo)
    return (pl.col("b_idade") * anos - c).exp()


def perdas_por_idade(df: pl.DataFrame, por: list[str]) -> pl.DataFrame:
    """Share of value lost in each year of a car's life, from adjacent model years.

    Within each series in one reference month, the price of model year Y-1 vs Y
    is what one extra year of age costs at that age. Zero km vs the newest used
    model year is reported as age -1 ("leaving the dealership"). Returns the
    median loss per group and whole-year age, with the number of pairs.
    """
    d = df.with_columns(
        pl.when(pl.col("zero_km")).then(None).otherwise(pl.col("idade").floor()).alias("idade_int"),
    ).sort(*SERIE, pl.col("zero_km"), pl.col("idade"), descending=[False, False, False, True, False])
    usados = d.filter(~pl.col("zero_km")).with_columns(
        pl.col("preco").shift(-1).over(SERIE).alias("preco_prox"),
        pl.col("ano_modelo").shift(-1).over(SERIE).alias("ano_prox"),
    )
    anual = usados.filter(pl.col("ano_modelo") - pl.col("ano_prox") == 1).select(
        *por, "idade_int", (1 - pl.col("preco_prox") / pl.col("preco")).alias("perda")
    )
    mais_novo = usados.group_by(SERIE).agg(pl.all().sort_by("idade").first())
    saida = (
        d.filter(pl.col("zero_km"))
        .select(*SERIE, pl.col("preco").alias("preco_0km"))
        .join(mais_novo.select(*SERIE, *[c for c in por if c not in SERIE], "preco", "idade"), on=SERIE)
        .filter(pl.col("idade") < 1.5)  # only when the newest used model is this or last year's
        .select(*por, pl.lit(-1.0).alias("idade_int"), (1 - pl.col("preco") / pl.col("preco_0km")).alias("perda"))
    )
    return (
        pl.concat([saida, anual], how="vertical_relaxed")
        .group_by(*por, "idade_int")
        .agg(pl.col("perda").median().alias("perda_mediana"), pl.len().alias("n_pares"))
        .with_columns(pl.col("idade_int").cast(pl.Int32).alias("idade"))
        .drop("idade_int")
        .sort(*por, "idade")
    )


def variacao_anual(historico: pl.DataFrame, por: list[str] | None = None) -> pl.DataFrame:
    """Year-on-year change of the *same* car between consecutive Januaries.

    For used cars this is (series, model year) a year older; for zero km it is
    the new price of the same version a year later. Medians per January, in
    nominal and real terms.
    """
    por = por or []
    jan = historico.filter(pl.col("mes").dt.month() == 1).with_columns(
        pl.col("mes").dt.year().alias("ano_ref"),
        pl.when(pl.col("zero_km")).then(pl.lit("Zero km")).otherwise(pl.lit("Usado")).alias("condicao"),
    )
    carro = [*SERIE, "ano_modelo", "zero_km"]
    jan = jan.sort(*carro, "ano_ref", nulls_last=True).with_columns(
        pl.col("preco").shift().over(carro).alias("ant"),
        pl.col("preco_real").shift().over(carro).alias("ant_real"),
        pl.col("ano_ref").shift().over(carro).alias("ano_ant"),
    )
    return (
        jan.filter(pl.col("ano_ref") - pl.col("ano_ant") == 1)
        .group_by(*por, "condicao", "ano_ref")
        .agg(
            (pl.col("preco") / pl.col("ant") - 1).median().alias("var_nominal"),
            (pl.col("preco_real") / pl.col("ant_real") - 1).median().alias("var_real"),
            pl.len().alias("n_carros"),
        )
        .sort(*por, "condicao", "ano_ref")
    )
