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
        # Premium brands: hyphens, abbreviations and vans to leave out.
        ("Mercedes-Benz", "C-180 CGI Avant. 1.6/1.6 FlexTB 16V Aut.", "Classe C"),
        ("Mercedes-Benz", "CLA-200 Urban 1.3 TB Aut.", None),
        ("Mercedes-Benz", "GLA-200 Advance 1.6/1.6 TB 16V Flex Aut.", "GLA"),
        ("Mercedes-Benz", "Sprinter 417 Furgão 2.2 Diesel", None),
        ("Volvo", "XC 60 T-8 Plus 2.0 AWD (Híbrido)", "XC60"),
        ("Land Rover", "Range R.EVOQUE Si4 HSE Dyn. 2.0/Flex Aut", "Evoque"),
        ("Land Rover", "Range Rover EVOQUE SE 2.0 Diesel Aut.", "Evoque"),
        ("Land Rover", "Range R.Sport SE 3.0 4x4 TDV6/SDV6 Dies.", None),
        ("Land Rover", "DISC SP HSE 2.0 Aut.", "Discovery Sport"),
        ("MINI", "COOPER S 2.0 Turbo 16v 3p Aut.", "Cooper"),
        ("MINI", "COOPER Countryman S 2.0 Turbo Aut.", None),
        ("MINI", "COOPER COU. SE SHAD. ED. ALL4 1.5 (Híb.)", None),
        ("MINI", "COOPER COUPE S 1.6 Aut.", "Cooper"),
        ("BMW", "320iA 2.0 TB M Sport A.Flex/M.Sport 4p", "320i"),
        ("Lexus", "NX-350h 4x4 Luxury 2.5 16V Aut. (Híb.)", "NX"),
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


def test_atributos_premium():
    df = pl.DataFrame(
        {
            "versao": [
                "Macan 2.0 Turbo",  # no transmission in the name: premium -> automatic
                "COOPER S 2.0 Turbo 16V 3p Mec.",  # explicitly manual
                "A3 Sed.Perf. Black 2.0 TFSI S-tr. (Hib.)",  # S-tronic, abbreviated hybrid
                "320iA 2.0 Turbo/ActiveFlex 16V/GP  4p",  # "iA" = automatic
                "C-180 CGI Exc. 1.6/1.6 Flex TB 16V  Aut.",  # CGI = turbo
                "Gol 1.0 Flex 12V 5p",  # mainstream, no mention -> manual
            ],
            "combustivel_code": [1, 1, 1, 5, 5, 5],
            "categoria": ["Premium"] * 5 + ["Generalista"],
        }
    )
    out = atributos(df)
    assert out["cambio"].to_list() == ["Automático", "Manual", "Automático", "Automático", "Automático", "Manual"]
    assert out["propulsao"].to_list() == ["Gasolina", "Gasolina", "Híbrido", "Flex", "Flex", "Flex"]
    assert out["turbo"].to_list() == [True, True, True, True, True, False]
