from datetime import date

import polars as pl
import pytest

from pipeline.clean import norm_expr, normalize_name, parse_brl, parse_mes, split_ano_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("R$ 60.653,00", 60653.0),
        ("R$ 1.234.567,89", 1234567.89),
        ("R$ 950,50", 950.5),
        ("", None),
        (None, None),
        ("R$ -", None),
    ],
)
def test_parse_brl(raw, expected):
    assert parse_brl(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("outubro/2026 ", date(2026, 10, 1)),
        ("outubro de 2026 ", date(2026, 10, 1)),
        ("Março/2019", date(2019, 3, 1)),
        ("janeiro/2001", date(2001, 1, 1)),
    ],
)
def test_parse_mes(raw, expected):
    assert parse_mes(raw) == expected


def test_parse_mes_rejects_garbage():
    with pytest.raises(ValueError):
        parse_mes("2026-10")


def test_split_ano_code():
    assert split_ano_code("2020-5") == (2020, 5)
    assert split_ano_code("32000-1") == (32000, 1)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ONIX HATCH 1.0 12V TB Flex 5p Mec.", "ONIX HATCH 1.0 12V TB FLEX 5P MEC"),
        ("Onix  Lollapalooza 1.0 F.Power 5p Mec.", "ONIX LOLLAPALOOZA 1.0 F POWER 5P MEC"),
        ("T-Cross 200 TSI 1.0  Flex 12V 5p Aut.", "T CROSS 200 TSI 1.0 FLEX 12V 5P AUT"),
        ("Ka+ Sedan 1.0 SE/SE PLUS TiVCT Flex 4p", "KA+ SEDAN 1.0 SE SE PLUS TIVCT FLEX 4P"),
        ("Fastback Audace 200 TB Aut (Hibrído)", "FASTBACK AUDACE 200 TB AUT HIBRIDO"),
        ("", None),
    ],
)
def test_normalize_name_python_and_polars_agree(raw, expected):
    assert normalize_name(raw) == expected
    assert pl.select(norm_expr(pl.lit(raw))).item() == expected
