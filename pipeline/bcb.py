"""Banco Central SGS: IPCA, used to turn nominal FIPE prices into real ones.

Series 433 is the monthly IPCA change in percent. SGS caps a single request at
ten years of data for some series, so we ask in windows and stitch them.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import polars as pl

from .http import fetch, log

SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
IPCA_MENSAL = 433


def _serie(serie: int, inicio: int) -> pl.DataFrame:
    rows = []
    hoje = date.today().year
    for ano in range(inicio, hoje + 1, 10):
        params = {"formato": "json", "dataInicial": f"01/01/{ano}", "dataFinal": f"31/12/{min(ano + 9, hoje)}"}
        rows += json.loads(fetch(SGS.format(serie=serie), params=params, suffix=".json", max_age=timedelta(days=1)))
    return pl.DataFrame(
        {
            "mes": [datetime.strptime(r["data"], "%d/%m/%Y").date() for r in rows],
            "valor": [float(r["valor"]) for r in rows],
        },
        schema={"mes": pl.Date, "valor": pl.Float64},
    ).unique("mes").sort("mes")


def ipca(inicio: int = 2000) -> pl.DataFrame:
    """Monthly IPCA as ``variacao`` (%) and a cumulative ``indice`` (= 1 at the last published month).

    Multiplying a nominal price of month *m* by ``indice[m]`` gives it in reais of
    the last month with IPCA published.
    """
    log("BCB: IPCA (SGS 433)")
    df = _serie(IPCA_MENSAL, inicio).rename({"valor": "variacao"})
    acumulado = (1 + df["variacao"] / 100).cum_prod()
    return df.with_columns((acumulado[-1] / acumulado).alias("indice"))


def ipca_12m(inicio: int = 2000) -> pl.DataFrame:
    """IPCA accumulated over the 12 months up to and including each month."""
    df = ipca(inicio)
    return df.select("mes", ((1 + pl.col("variacao") / 100).log().rolling_sum(12).exp() - 1).alias("ipca_12m")).drop_nulls()


def deflator(meses: pl.Series) -> pl.DataFrame:
    """``mes`` -> ``deflator`` for the distinct months in ``meses``.

    Months after the last IPCA release get 1 (no inflation measured yet).
    """
    idx = ipca(meses.min().year - 1).select("mes", "indice")
    return (
        pl.DataFrame({"mes": meses.unique()})
        .join(idx, on="mes", how="left")
        .select("mes", pl.col("indice").fill_null(pl.when(pl.col("mes") > idx["mes"].max()).then(1.0)).alias("deflator"))
    )
