import pytest

from pipeline.schema import SchemaError, require_keys


def test_passes_through_when_keys_present():
    rows = [{"Value": "1", "Label": "GM - Chevrolet", "extra": 0}]
    assert require_keys(rows, ["Value", "Label"], "test") is rows
    obj = {"Valor": "R$ 1,00", "CodigoFipe": "004001-0"}
    assert require_keys(obj, ["Valor"], "test") is obj


def test_missing_key_names_source_and_suggests_rename():
    rows = [{"Codigo": 338, "Mes": "outubro/2026 "}, {"CodigoTabela": 337, "Mes": "setembro/2026 "}]
    with pytest.raises(SchemaError) as exc:
        require_keys(rows, ["Codigo", "Mes"], "FIPE ConsultarTabelaDeReferencia")
    msg = str(exc.value)
    assert msg.startswith("FIPE ConsultarTabelaDeReferencia (record 1): 1 expected field(s) missing")
    assert "'Codigo' (did you mean 'CodigoTabela'?)" in msg


def test_empty_list_is_an_error_unless_allowed():
    with pytest.raises(SchemaError, match="at least 1 record"):
        require_keys([], ["Value"], "empty")
    assert require_keys([], ["Value"], "empty", min_rows=0) == []


def test_wrong_shape_is_an_error():
    with pytest.raises(SchemaError, match="got str"):
        require_keys("<html>blocked</html>", ["Value"], "html page")
