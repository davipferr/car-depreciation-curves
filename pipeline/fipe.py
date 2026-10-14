"""Tabela FIPE: reference months, brands, the (version x model year) catalogue and prices.

These are the JSON endpoints behind FIPE's own consultation page
(veiculos.fipe.org.br). They need no key and, unlike the free tier of the
third-party Parallelum API, they serve every reference month back to 2001.
Everything is a form POST, and a miss is a 200 with ``{"erro": "nadaencontrado"}``
rather than a 404.

Request budget is the main design constraint: there is one request per
(version, model year, reference month). Two tricks keep it small:

* ``ConsultarModelosAtravesDoAno`` lists every version sold in a given model
  year and fuel, so the whole catalogue of a brand costs ~1 request per
  (model year, fuel) instead of one per version;
* a price for a past reference month never changes, so every price response
  is cached forever and later builds only fetch the newest month.
"""

from __future__ import annotations

import json
import os
import time
from datetime import timedelta

import polars as pl

from .clean import parse_brl, parse_mes, split_ano_code
from .http import RateLimiter, cached, fetch, log
from .schema import require_keys

API = "https://veiculos.fipe.org.br/api/veiculos"
HEADERS = {"Referer": "https://veiculos.fipe.org.br/", "Accept": "application/json"}
CARROS = 1  # codigoTipoVeiculo: 1 cars, 2 motorcycles, 3 trucks

# FIPE answers short bursts at ~3 req/s but starts sending 429s within a few
# hundred requests at 150/min. Start at 90/min (override with FIPE_RPM); the
# limiter slows itself down further on every 429.
LIMITER = RateLimiter(int(os.environ.get("FIPE_RPM", "90")))


def _post(endpoint: str, form: dict, *, max_age: timedelta | None) -> object:
    body = fetch(f"{API}/{endpoint}", data=form, headers=HEADERS, max_age=max_age, suffix=".json", limiter=LIMITER)
    return json.loads(body)


def _is_miss(payload: object) -> bool:
    return isinstance(payload, dict) and "erro" in payload


# ------------------------------------------------------------------- references


def referencias() -> pl.DataFrame:
    """Every published reference table: ``ref`` (FIPE's code, e.g. 338) and ``mes`` (first day of the month)."""
    rows = require_keys(_post("ConsultarTabelaDeReferencia", {}, max_age=timedelta(days=1)), ["Codigo", "Mes"], "FIPE ConsultarTabelaDeReferencia")
    return pl.DataFrame(
        [{"ref": int(r["Codigo"]), "mes": parse_mes(r["Mes"])} for r in rows],
        schema={"ref": pl.Int32, "mes": pl.Date},
    ).sort("mes")


def ultima_referencia() -> int:
    return int(referencias()["ref"][-1])


# ------------------------------------------------------------------- catalogue
# Lists are requested against a specific reference code, so a new month means a
# new cache key; within a month they can be cached forever.


def marcas(ref: int) -> pl.DataFrame:
    rows = _post("ConsultarMarcas", {"codigoTabelaReferencia": ref, "codigoTipoVeiculo": CARROS}, max_age=None)
    require_keys(rows, ["Value", "Label"], f"FIPE ConsultarMarcas (ref {ref})")
    return pl.DataFrame(
        [{"marca_code": int(r["Value"]), "marca": r["Label"].strip()} for r in rows],
        schema={"marca_code": pl.Int32, "marca": pl.String},
    )


def _anos_da_marca(ref: int, marca_code: int) -> list[str]:
    payload = _post(
        "ConsultarModelos",
        {"codigoTabelaReferencia": ref, "codigoTipoVeiculo": CARROS, "codigoMarca": marca_code},
        max_age=None,
    )
    anos = require_keys(payload, ["Anos"], f"FIPE ConsultarModelos (ref {ref}, marca {marca_code})")["Anos"]
    return [a["Value"] for a in require_keys(anos, ["Value"], f"FIPE ConsultarModelos (ref {ref}, marca {marca_code}) Anos")]


def catalogo_marca(ref: int, marca_code: int, ano_min: int) -> pl.DataFrame:
    """Every (version, model year, fuel) of a brand with model year >= ``ano_min`` (zero km included).

    Columns: marca_code, modelo_code, versao, ano_modelo, combustivel_code.
    """
    out = []
    for code in _anos_da_marca(ref, marca_code):
        ano, comb = split_ano_code(code)
        if ano < ano_min:
            continue
        rows = _post(
            "ConsultarModelosAtravesDoAno",
            {
                "codigoTabelaReferencia": ref,
                "codigoTipoVeiculo": CARROS,
                "codigoMarca": marca_code,
                "ano": code,
                "codigoTipoCombustivel": comb,
                "anoModelo": ano,
            },
            max_age=None,
        )
        if _is_miss(rows):
            continue
        require_keys(rows, ["Value", "Label"], f"FIPE ConsultarModelosAtravesDoAno (ref {ref}, marca {marca_code}, ano {code})", min_rows=0)
        out.extend(
            {"modelo_code": int(r["Value"]), "versao": r["Label"], "ano_modelo": ano, "combustivel_code": comb} for r in rows
        )
    schema = {"modelo_code": pl.Int32, "versao": pl.String, "ano_modelo": pl.Int32, "combustivel_code": pl.Int8}
    return pl.DataFrame(out, schema=schema).with_columns(pl.lit(marca_code, pl.Int32).alias("marca_code"))


# ----------------------------------------------------------------------- prices


def _preco_form(ref: int, marca_code: int, modelo_code: int, ano_modelo: int, combustivel_code: int) -> dict:
    return {
        "codigoTabelaReferencia": ref,
        "codigoMarca": marca_code,
        "codigoModelo": modelo_code,
        "codigoTipoVeiculo": CARROS,
        "anoModelo": ano_modelo,
        "codigoTipoCombustivel": combustivel_code,
        "tipoVeiculo": "carro",
        "tipoConsulta": "tradicional",
    }


def preco(ref: int, marca_code: int, modelo_code: int, ano_modelo: int, combustivel_code: int) -> dict | None:
    """One FIPE price, or None if that version/year wasn't in that month's table."""
    payload = _post(
        "ConsultarValorComTodosParametros",
        _preco_form(ref, marca_code, modelo_code, ano_modelo, combustivel_code),
        max_age=None,
    )
    if _is_miss(payload):
        return None
    require_keys(payload, ["Valor", "CodigoFipe"], f"FIPE ConsultarValorComTodosParametros (ref {ref}, modelo {modelo_code}, ano {ano_modelo})")
    return {"preco": parse_brl(payload["Valor"]), "codigo_fipe": payload["CodigoFipe"]}


def precos(consultas: pl.DataFrame) -> pl.DataFrame:
    """Price every row of ``consultas`` (ref, marca_code, modelo_code, ano_modelo, combustivel_code).

    Returns the same rows plus ``preco`` and ``codigo_fipe`` (null when FIPE had no price).
    """
    keys = ["ref", "marca_code", "modelo_code", "ano_modelo", "combustivel_code"]
    todo = consultas.select(keys).unique().sort(keys)
    novos = sum(
        not cached(f"{API}/ConsultarValorComTodosParametros", data=_preco_form(*r), suffix=".json")
        for r in todo.iter_rows()
    )
    if novos:
        log(f"FIPE: {todo.height:,} prices, {novos:,} not cached yet (~{novos / LIMITER.per_minute:.0f} min at {LIMITER.per_minute:.0f} req/min)")

    out, t0, feitos = [], time.time(), 0
    for row in todo.iter_rows(named=True):
        novo = not cached(f"{API}/ConsultarValorComTodosParametros", data=_preco_form(*row.values()), suffix=".json")
        p = preco(*row.values())
        out.append(row | (p or {"preco": None, "codigo_fipe": None}))
        if novo:
            feitos += 1
            if feitos % 250 == 0:
                log(f"  {feitos:,}/{novos:,} new prices ({time.time() - t0:.0f}s, now {LIMITER.per_minute:.0f} req/min)")
    schema = {k: consultas.schema[k] for k in keys} | {"preco": pl.Float64, "codigo_fipe": pl.String}
    return pl.DataFrame(out, schema=schema)
