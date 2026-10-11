"""The depreciation model must recover known rates from synthetic FIPE-like data."""

import math
from datetime import date

import polars as pl
import pytest

from pipeline.curvas import ajuste, com_retencao, perdas_por_idade, variacao_anual

MES = date(2026, 1, 1)


def _painel(familias: dict[str, tuple[float, float]], versoes: int = 3, anos: int = 8) -> pl.DataFrame:
    """Each family: (annual depreciation, loss leaving the dealership). Versions differ in price level only."""
    rows = []
    for i, (fam, (taxa, saida)) in enumerate(familias.items()):
        for v in range(versoes):
            code = 1000 * (i + 1) + v
            base = 80_000 * (1 + 0.3 * v)
            rows.append({"familia": fam, "modelo_code": code, "ano_modelo": None, "idade": 0.0, "zero_km": True, "preco": base})
            for k in range(anos):
                preco = base * (1 - saida) * (1 - taxa) ** k
                rows.append({"familia": fam, "modelo_code": code, "ano_modelo": 2026 - k, "idade": float(k), "zero_km": False, "preco": preco})
    return pl.DataFrame(rows).with_columns(
        pl.lit(1, pl.Int32).alias("marca_code"), pl.lit(5, pl.Int8).alias("combustivel_code"), pl.lit(MES).alias("mes")
    )


def test_ajuste_recovers_rates():
    df = _painel({"A": (0.05, 0.10), "B": (0.12, 0.02)})
    fit = ajuste(df, ["familia"]).sort("familia")
    assert fit["taxa_anual"].to_list() == pytest.approx([0.05, 0.12])
    assert fit["perda_imediata"].to_list() == pytest.approx([0.10, 0.02])
    assert fit["n_series"].to_list() == [3, 3]


def test_ajuste_without_zero_km_still_estimates_slope():
    df = _painel({"A": (0.07, 0.10)}).filter(~pl.col("zero_km"))
    fit = ajuste(df, ["familia"])
    assert fit["taxa_anual"][0] == pytest.approx(0.07)
    assert fit["b_novo"][0] is None


def test_retencao_is_share_of_new_price():
    df = _painel({"A": (0.05, 0.10)})
    out = com_retencao(df, ["familia"], ajuste(df, ["familia"]))
    zero = out.filter(pl.col("zero_km"))["retencao"]
    assert zero.to_list() == pytest.approx([1.0] * 3)
    five = out.filter(pl.col("idade") == 5)["retencao"]
    assert five.to_list() == pytest.approx([0.9 * 0.95**5] * 3)


def test_perdas_por_idade():
    df = _painel({"A": (0.08, 0.15)})
    out = perdas_por_idade(df, ["familia"])
    saida = out.filter(pl.col("idade") == -1)
    assert saida["perda_mediana"][0] == pytest.approx(0.15)
    assert out.filter(pl.col("idade") >= 0)["perda_mediana"].to_list() == pytest.approx([0.08] * 7)


def test_variacao_anual_follows_the_same_car():
    rows = []
    for ano, fator in [(2020, 1.0), (2021, 1.10), (2022, 1.21)]:
        rows.append({"ano_modelo": 2019, "zero_km": False, "mes": date(ano, 1, 1), "preco": 50_000 * fator})
        rows.append({"ano_modelo": None, "zero_km": True, "mes": date(ano, 1, 1), "preco": 90_000 * fator})
    df = pl.DataFrame(rows).with_columns(
        pl.lit(1, pl.Int32).alias("marca_code"),
        pl.lit(7, pl.Int32).alias("modelo_code"),
        pl.lit(5, pl.Int8).alias("combustivel_code"),
        (pl.col("preco") / 2).alias("preco_real"),
    )
    out = variacao_anual(df)
    assert out["ano_ref"].to_list() == [2021, 2022, 2021, 2022]
    assert out["var_nominal"].to_list() == pytest.approx([0.10] * 4)
    assert all(math.isclose(v, 0.10) for v in out["var_real"])
