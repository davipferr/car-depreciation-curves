"""From FIPE's free-text version names to model families and attributes.

FIPE has no "model family" field: each row is a *version* such as
"ONIX HATCH LT 1.0 12V Flex 5p Mec." or "Onix Plus Premier 1.0 Turbo Aut.".
Grouping versions into families (Onix vs Onix Plus, Corolla vs Corolla Cross,
HB20 vs HB20S, Gol vs Golf, Ka vs Ka Sedan...) is a name-matching problem,
solved here with an ordered list of patterns on the normalised name: the first
pattern that matches wins, so more specific families come first.

The same names carry the attributes we compare depreciation by: engine size,
turbo, transmission (manual, automatic or *automated manual*, which the market
punishes) and powertrain (hybrids are usually filed under "Gasolina").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import polars as pl

from .clean import COMBUSTIVEIS, norm_expr, normalize_name


@dataclass(frozen=True)
class Familia:
    nome: str  # display name
    marca: str  # FIPE brand label, exactly as in ConsultarMarcas
    padrao: str  # regex on the normalised version name (anchored at the start)
    segmento: str  # Hatch, Sedã, SUV, Picape, Minivan, Esportivo


# Order matters within a brand: specific patterns before generic ones.
FAMILIAS: list[Familia] = [
    # Chevrolet
    Familia("Onix Plus", "GM - Chevrolet", r"ONIX (PLUS|SEDAN|SED\b)", "Sedã"),
    Familia("Onix", "GM - Chevrolet", r"ONIX\b", "Hatch"),
    Familia("Prisma", "GM - Chevrolet", r"PRISMA\b", "Sedã"),
    Familia("Tracker", "GM - Chevrolet", r"TRACKER\b", "SUV"),
    Familia("Cruze", "GM - Chevrolet", r"CRUZE (?!SPORT)", "Sedã"),
    Familia("Spin", "GM - Chevrolet", r"SPIN\b", "Minivan"),
    Familia("Montana", "GM - Chevrolet", r"MONTANA\b", "Picape"),
    Familia("S10", "GM - Chevrolet", r"S10\b", "Picape"),
    # Volkswagen
    Familia("Gol", "VW - VolksWagen", r"GOL\b", "Hatch"),
    Familia("Voyage", "VW - VolksWagen", r"VOYAGE\b", "Sedã"),
    Familia("Fox", "VW - VolksWagen", r"(CROSS)?FOX\b", "Hatch"),
    Familia("up!", "VW - VolksWagen", r"(CROSS )?UP\b", "Hatch"),
    Familia("Polo", "VW - VolksWagen", r"POLO\b(?! SEDAN)", "Hatch"),
    Familia("Virtus", "VW - VolksWagen", r"VIRTUS\b", "Sedã"),
    Familia("Jetta", "VW - VolksWagen", r"JETTA\b", "Sedã"),
    Familia("T-Cross", "VW - VolksWagen", r"T CROSS\b", "SUV"),
    Familia("Nivus", "VW - VolksWagen", r"NIVUS\b", "SUV"),
    Familia("Taos", "VW - VolksWagen", r"TAOS\b", "SUV"),
    Familia("Saveiro", "VW - VolksWagen", r"SAVEIRO\b", "Picape"),
    Familia("Amarok", "VW - VolksWagen", r"AMAROK\b", "Picape"),
    # Fiat
    Familia("Mobi", "Fiat", r"MOBI\b", "Hatch"),
    Familia("Uno", "Fiat", r"UNO\b", "Hatch"),
    Familia("Argo", "Fiat", r"ARGO\b", "Hatch"),
    Familia("Cronos", "Fiat", r"CRONOS\b", "Sedã"),
    Familia("Pulse", "Fiat", r"PULSE\b", "SUV"),
    Familia("Fastback", "Fiat", r"FASTBACK\b", "SUV"),
    Familia("Strada", "Fiat", r"STRADA\b", "Picape"),
    Familia("Toro", "Fiat", r"TORO\b", "Picape"),
    # Hyundai
    Familia("HB20S", "Hyundai", r"HB20S\b", "Sedã"),
    Familia("HB20", "Hyundai", r"HB20\b(?! ?[SX]\b)", "Hatch"),
    Familia("Creta", "Hyundai", r"CRETA\b", "SUV"),
    # Toyota
    Familia("Corolla Cross", "Toyota", r"COROLLA CROSS\b", "SUV"),
    Familia("Corolla", "Toyota", r"COROLLA\b", "Sedã"),
    Familia("Yaris Cross", "Toyota", r"YARIS CROSS\b", "SUV"),
    Familia("Yaris", "Toyota", r"YARIS\b", "Hatch"),
    Familia("Etios", "Toyota", r"ETIOS\b", "Hatch"),
    Familia("SW4", "Toyota", r"HILUX SW4\b|SW4\b", "SUV"),
    Familia("Hilux", "Toyota", r"HILUX\b", "Picape"),
    # Honda
    Familia("Fit", "Honda", r"FIT\b", "Hatch"),
    Familia("City Hatchback", "Honda", r"CITY HATCH", "Hatch"),
    Familia("City", "Honda", r"CITY\b", "Sedã"),
    Familia("Civic", "Honda", r"CIVIC\b", "Sedã"),
    Familia("WR-V", "Honda", r"WR V\b", "SUV"),
    Familia("HR-V", "Honda", r"HR V\b", "SUV"),
    # Jeep
    Familia("Renegade", "Jeep", r"RENEGADE\b", "SUV"),
    Familia("Compass", "Jeep", r"COMPASS\b", "SUV"),
    Familia("Commander", "Jeep", r"COMMANDER\b", "SUV"),
    # Renault
    Familia("Kwid", "Renault", r"KWID\b", "Hatch"),
    Familia("Sandero", "Renault", r"SANDERO\b", "Hatch"),
    Familia("Logan", "Renault", r"LOGAN\b", "Sedã"),
    Familia("Oroch", "Renault", r"(DUSTER )?OROCH\b", "Picape"),
    Familia("Duster", "Renault", r"DUSTER\b", "SUV"),
    Familia("Captur", "Renault", r"CAPTUR\b", "SUV"),
    # Nissan
    Familia("March", "Nissan", r"MARCH\b", "Hatch"),
    Familia("Versa", "Nissan", r"VERSA\b", "Sedã"),
    Familia("Kicks", "Nissan", r"KICKS\b", "SUV"),
    Familia("Frontier", "Nissan", r"FRONTIER\b", "Picape"),
    # Ford
    Familia("Ka Sedan", "Ford", r"KA (\+|SEDAN)|KA\+", "Sedã"),
    Familia("Ka", "Ford", r"KA\b", "Hatch"),
    Familia("Fiesta", "Ford", r"FIESTA\b(?! SEDAN)", "Hatch"),
    Familia("EcoSport", "Ford", r"ECOSPORT\b", "SUV"),
    Familia("Ranger", "Ford", r"RANGER\b", "Picape"),
    # Peugeot
    Familia("208", "Peugeot", r"208\b", "Hatch"),
    Familia("2008", "Peugeot", r"2008\b", "SUV"),
    # Mitsubishi
    Familia("L200", "Mitsubishi", r"L200\b", "Picape"),
    # BYD (2023 onwards: few model years, but the only sizeable EV sample)
    Familia("Dolphin Mini", "BYD", r"DOLPHIN MINI\b", "Hatch"),
    Familia("Dolphin", "BYD", r"DOLPHIN\b", "Hatch"),
    Familia("Song Plus", "BYD", r"SONG PLUS\b", "SUV"),
    # Caoa Chery
    Familia("Tiggo 5x", "Caoa Chery", r"TIGGO 5X\b", "SUV"),
    Familia("Tiggo 7", "Caoa Chery", r"TIGGO 7\b", "SUV"),
    Familia("Tiggo 8", "Caoa Chery", r"TIGGO 8\b", "SUV"),
    # GWM
    Familia("Haval H6", "GWM", r"HAVAL H6\b", "SUV"),
    # ---- Premium brands. Names are written differently here: "C-180", "GLA-200",
    # "XC 60" (with a space), "Range R.EVOQUE", "NX-350h", "320iA" (A = automatic).
    # BMW
    Familia("320i", "BMW", r"320I", "Sedã"),
    Familia("X1", "BMW", r"X1\b", "SUV"),
    # Mercedes-Benz (most of its FIPE catalogue is Sprinter vans, left out)
    Familia("Classe C", "Mercedes-Benz", r"C \d{2,3}\b", "Sedã"),
    Familia("GLA", "Mercedes-Benz", r"GLA \d", "SUV"),
    # Audi
    Familia("A3", "Audi", r"A3\b", "Sedã"),
    Familia("Q3", "Audi", r"Q3\b", "SUV"),
    # Volvo
    Familia("S60", "Volvo", r"S60\b", "Sedã"),
    Familia("XC40", "Volvo", r"XC ?40\b", "SUV"),
    Familia("XC60", "Volvo", r"XC ?60\b", "SUV"),
    # Land Rover
    Familia("Evoque", "Land Rover", r"RANGE R(OVER)? ?EVOQUE\b", "SUV"),
    Familia("Discovery Sport", "Land Rover", r"DISC(OVERY)? SP(ORT)?\b", "SUV"),
    # Porsche
    Familia("Macan", "Porsche", r"MACAN\b", "SUV"),
    Familia("Cayenne", "Porsche", r"CAYENNE\b", "SUV"),
    Familia("911", "Porsche", r"911\b", "Esportivo"),
    # Lexus
    Familia("NX", "Lexus", r"NX \d", "SUV"),
    # RAM (FIPE has no RAM 1500 since 2014: the 2500 and the mid-size Rampage instead)
    Familia("RAM 2500", "RAM", r"2500\b", "Picape"),
    Familia("Rampage", "RAM", r"RAMPAGE\b", "Picape"),
    # MINI: the Cooper hatch, not the Countryman ("COUNTRY.", "COU."), Cabrio, Clubman or Paceman
    Familia("Cooper", "MINI", r"COOPER\b(?!.*\b(COU|COUNTRY\w*|CABRIO|PACEMAN|CLUBMAN|ACEMAN)\b)", "Hatch"),
]

MARCAS = sorted({f.marca for f in FAMILIAS})

PREMIUM = {"BMW", "Mercedes-Benz", "Audi", "Volvo", "Land Rover", "Porsche", "Lexus", "RAM", "MINI"}

# Short brand labels for the site ("GM - Chevrolet" -> "Chevrolet").
MARCA_CURTA = {"GM - Chevrolet": "Chevrolet", "VW - VolksWagen": "Volkswagen", "Caoa Chery": "Chery"}


def familia_de(marca: str, versao: str) -> Familia | None:
    """The first family of ``marca`` whose pattern matches the normalised ``versao``."""
    nome = normalize_name(versao) or ""
    for f in FAMILIAS:
        if f.marca == marca and re.match(f.padrao, nome):
            return f
    return None


# -------------------------------------------------------------------- attributes

_TURBO = r"\b(TURBO\w*|TB|TSI|TFSI|THP|T ?GDI|TGDI|T200|T270|CGI|\d\.\dT|\d{3} TSI)\b"
# Automated manuals: a robot pressing the clutch of a manual box. Cheaper than a
# real automatic and notorious in the used market, so they get their own class.
_AUTOMATIZADO = r"\b(DUALOGIC|EASYTRONIC|I ?MOTION|GSR|AMT|ASG|AUTOMATIZADO|EASY R)\b"
_AUTOMATICO = (
    r"\b(AUT|AUTO|AUTOM|AUTOMATICO|AT|AT6|CVT|X ?TRONIC|DCT|DSG|TIPTRONIC|POWERSHIFT|EAT6|EAT8|STEPTRONIC"
    r"|MULTIDRIVE|S ?TRONIC|S TR|PDK|\d{3}IA)\b"
)
_MANUAL = r"\b(MEC|MECANICO|MANUAL|MT)\b"
# Premium brands abbreviate hybrids as "(Híb.)" or "(Hib.)".
_HIBRIDO = r"\b(HYBRID|HIBRIDO|HIB|HEV|PHEV|DM I|E HYBRID|MHEV)\b"
_ELETRICO = r"\b(EV|ELETRICO|ELECTRIC|E TECH ELETRICO)\b"


def atributos(versoes: pl.DataFrame) -> pl.DataFrame:
    """Add engine, turbo, transmission and powertrain columns parsed from ``versao``.

    Expects ``versao`` and ``combustivel_code`` (and optionally ``categoria``).
    When the name doesn't say, transmission defaults to manual for mainstream
    brands (FIPE almost always flags "Aut." but often omits "Mec.") and to
    automatic for premium ones, whose names often omit it ("Macan 2.0 Turbo") and
    which have sold practically no manuals in Brazil since 2014.
    """
    n = norm_expr(pl.col("versao"))
    combustivel = pl.col("combustivel_code").replace_strict(COMBUSTIVEIS, default="Outro", return_dtype=pl.String)
    premium = pl.col("categoria") == "Premium" if "categoria" in versoes.columns else pl.lit(False)
    return versoes.with_columns(
        n.str.extract(r"\b(\d\.\d)").cast(pl.Float32).alias("motor"),
        n.str.contains(_TURBO).alias("turbo"),
        pl.when(n.str.contains(_AUTOMATIZADO))
        .then(pl.lit("Automatizado"))
        .when(n.str.contains(_AUTOMATICO))
        .then(pl.lit("Automático"))
        .when(premium & ~n.str.contains(_MANUAL))
        .then(pl.lit("Automático"))
        .otherwise(pl.lit("Manual"))
        .alias("cambio"),
        pl.when((pl.col("combustivel_code") == 4) | n.str.contains(_ELETRICO))
        .then(pl.lit("Elétrico"))
        .when((pl.col("combustivel_code") == 6) | n.str.contains(_HIBRIDO))
        .then(pl.lit("Híbrido"))
        .otherwise(combustivel)
        .alias("propulsao"),
    )


def classificar(catalogo: pl.DataFrame, marca_por_code: dict[int, str]) -> pl.DataFrame:
    """Attach family, segment and attributes to a catalogue; rows of no family get null ``familia``."""
    nomes = catalogo.select("marca_code", "versao").unique()
    fam = nomes.with_columns(
        pl.struct("marca_code", "versao")
        .map_elements(
            lambda r: (f := familia_de(marca_por_code[r["marca_code"]], r["versao"])) and f.nome,
            return_dtype=pl.String,
        )
        .alias("familia")
    )
    meta = pl.DataFrame(
        [
            {
                "familia": f.nome,
                "marca": MARCA_CURTA.get(f.marca, f.marca),
                "segmento": f.segmento,
                "categoria": "Premium" if f.marca in PREMIUM else "Generalista",
            }
            for f in FAMILIAS
        ]
    )
    return atributos(catalogo.join(fam, on=["marca_code", "versao"], how="left").join(meta, on="familia", how="left"))
