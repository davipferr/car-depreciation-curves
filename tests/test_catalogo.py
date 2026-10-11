import polars as pl
import pytest

from pipeline.catalogo import atributos, familia_de

CHEV, VW, HYU, TOY, FORD, REN = "GM - Chevrolet", "VW - VolksWagen", "Hyundai", "Toyota", "Ford", "Renault"


@pytest.mark.parametrize(
    ("marca", "versao", "familia"),
    [
        # A family name that is a prefix of another must not swallow it.
        (CHEV, "ONIX HATCH 1.0 12V Flex 5p Mec.", "Onix"),
        (CHEV, "ONIX  Lollapalooza 1.0 F.Power 5p Mec.", "Onix"),
        (CHEV, "ONIX SED. Plus PREM. 1.0 12V TB Flex Aut", "Onix Plus"),
        (CHEV, "ONIX SEDAN Plus LT 1.0 12V TB Flex Aut.", "Onix Plus"),
        (CHEV, "CRUZE LT 1.4 16V Turbo Flex 4p Aut.", "Cruze"),
        (CHEV, "CRUZE SPORT6 LTZ 1.4 Turbo Flex Aut.", None),
        (VW, "Gol 1.0 Flex 12V 5p", "Gol"),
        (VW, "Golf Highline 1.4 TSI Flex Aut.", None),
        (VW, "Polo 1.0 MPI Flex 12V 5p", "Polo"),
        (VW, "POLO SEDAN 1.6 Mi Total Flex 8V 4p", None),
        (VW, "T-Cross 200 TSI 1.0  Flex 12V 5p Aut.", "T-Cross"),
        (VW, "CROSSFOX 1.6 Mi Total Flex 8V 5p", "Fox"),
        (VW, "up! Xtreme 1.0 TSI Total Flex 12V 5p", "up!"),
        (HYU, "HB20 Comfort 1.0 Flex 12V Mec.", "HB20"),
        (HYU, "HB20S Comfort 1.0  Flex 12V Mec.", "HB20S"),
        (HYU, "HB20X STYLE 1.6 Flex 16V Mec.", None),
        (TOY, "Corolla Cross XRX 1.8 16V Aut. (Híbrido)", "Corolla Cross"),
        (TOY, "Corolla Altis Prem. 1.8 Aut. (Híbrido)", "Corolla"),
        (TOY, "Hilux SW4 Diamond 2.8 TB 4x4 Die. Aut.", "SW4"),
        (TOY, "Hilux CD 4x4 2.8  Diesel Aut.", "Hilux"),
        (TOY, "YARIS Cross XRE 1.5 16V 5p Aut. (Híbrido)", "Yaris Cross"),
        (FORD, "Ka 1.0 FREESTYLE 12V Flex 5p Mec.", "Ka"),
        (FORD, "Ka+ Sedan 1.0 SE/SE PLUS TiVCT Flex 4p", "Ka Sedan"),
        (FORD, "KA Sedan SE 1.5 16V Flex 4p Aut.", "Ka Sedan"),
        (REN, "DUSTER OROCH Dyn. 2.0 Flex 16V Aut.", "Oroch"),
        (REN, "DUSTER Iconic Plus 1.3 TB 16V Flex Aut.", "Duster"),
        # Same model name, wrong brand.
        (CHEV, "HB20 Comfort 1.0 Flex 12V Mec.", None),
    ],
)
def test_familia_de(marca, versao, familia):
    f = familia_de(marca, versao)
    assert (f.nome if f else None) == familia


def test_atributos():
    df = pl.DataFrame(
        {
            "versao": [
                "ONIX HATCH 1.0 12V TB Flex 5p Aut.",
                "HB20 Comfort 1.0 Flex 12V Mec.",
                "AGILE LTZ EASYTRONIC 1.4 8V FlexPower 5p",
                "Corolla Altis Prem. 1.8 Aut. (Híbrido)",
                "Dolphin EV GS (Elétrico)",
                "Hilux CD 4x4 2.8  Diesel Aut.",
                "Nivus Comfortline 1.0 200 TSI Flex Aut.",
                "KICKS SV 1.6 16V FlexStar 5p Aut.",
            ],
            "combustivel_code": [5, 5, 5, 1, 4, 3, 5, 5],
        }
    )
    out = atributos(df)
    assert out["motor"].to_list() == pytest.approx([1.0, 1.0, 1.4, 1.8, None, 2.8, 1.0, 1.6], nan_ok=True)
    assert out["turbo"].to_list() == [True, False, False, False, False, False, True, False]
    assert out["cambio"].to_list() == [
        "Automático", "Manual", "Automatizado", "Automático", "Manual", "Automático", "Automático", "Automático",
    ]
    assert out["propulsao"].to_list() == ["Flex", "Flex", "Flex", "Híbrido", "Elétrico", "Diesel", "Flex", "Flex"]
