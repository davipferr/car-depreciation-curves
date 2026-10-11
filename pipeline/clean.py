"""Cleaning helpers for FIPE's text fields.

FIPE is tidy compared with most Brazilian public data, but it still has:

* prices as Brazilian currency strings ("R$ 1.234.567,00");
* reference months as Portuguese text with trailing spaces ("outubro/2026 ",
  "outubro de 2026 ");
* the magic model year 32000, which means "zero km" (a new car of the current
  line-up), not a year;
* version names written by hand over decades, with inconsistent case, spacing
  and abbreviations ("ONIX HATCH 1.0 12V TB Flex 5p Aut.", "Onix  Lollapalooza
  1.0 F.Power 5p Mec."). Those are handled in ``catalogo``.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

import polars as pl

# FIPE's placeholder model year for brand-new cars.
ZERO_KM = 32000

MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

# Fuel codes, as used in FIPE's year codes ("2020-5" = model year 2020, flex).
COMBUSTIVEIS = {1: "Gasolina", 2: "Álcool", 3: "Diesel", 4: "Elétrico", 5: "Flex", 6: "Híbrido", 7: "Gás natural"}


# --------------------------------------------------------------------------- text


def strip_accents(text: str) -> str:
    """'Citroën Aircross' -> 'Citroen Aircross'."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_name(text: str | None) -> str | None:
    """Canonical key for matching names: no accents, uppercase, punctuation -> space.

    Dots between digits are kept, because "1.0" and "10" are different engines.
    """
    if text is None:
        return None
    out = strip_accents(text).upper()
    out = re.sub(r"(?<=\d)\.(?=\d)", "\0", out)  # protect "1.0"
    out = "".join(c if c.isalnum() or c in "\0+" else " " for c in out).replace("\0", ".")
    return " ".join(out.split()) or None


def norm_expr(expr: pl.Expr) -> pl.Expr:
    """Vectorised ``normalize_name``."""
    return (
        expr.str.normalize("NFD")
        .str.replace_all(r"\p{Mn}", "")
        .str.to_uppercase()
        .str.replace_all(r"(\d)\.(\d)", "${1}\x00${2}")
        .str.replace_all(r"[^A-Z0-9\x00+]+", " ")
        .str.replace_all("\x00", ".", literal=True)
        .str.strip_chars()
        .replace("", None)
    )


# ------------------------------------------------------------------------ numbers


def parse_brl(text: str | None) -> float | None:
    """'R$ 1.234.567,89' -> 1234567.89; anything unparseable -> None."""
    if not text:
        return None
    digits = re.sub(r"[^\d,]", "", text).replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


# ------------------------------------------------------------------------- dates


def parse_mes(text: str) -> date:
    """FIPE reference month -> first day of the month.

    Accepts 'outubro/2026 ', 'outubro de 2026 ' and 'Março/2019'.
    """
    m = re.match(r"\s*([^\s/]+)(?:\s+de\s+|/)(\d{4})\s*$", strip_accents(text).lower())
    if not m or m.group(1) not in MESES:
        raise ValueError(f"unrecognised FIPE month: {text!r}")
    return date(int(m.group(2)), MESES[m.group(1)], 1)


def split_ano_code(code: str) -> tuple[int, int]:
    """FIPE year code '2020-5' -> (model year 2020, fuel code 5); '32000-1' -> (32000, 1)."""
    ano, combustivel = code.split("-")
    return int(ano), int(combustivel)
