import json

import polars as pl

from pipeline import manifest


def _manifest(**tabelas):
    return {
        "gerado_em": "2026-10-01T00:00:00+00:00",
        "codigo_pipeline": "abc",
        "referencia_fipe": {"codigo": 338, "mes": "2026-10-01"},
        "fontes": [],
        "tabelas": tabelas,
    }


def test_table_stats_per_group():
    df = pl.DataFrame({"familia": ["Onix", "Onix", "Gol", None], "preco": [1.0, 2.0, 5.0, 1.0]})
    assert manifest._table(df, por=["familia"]) == {
        "linhas": 4,
        "colunas": ["familia", "preco"],
        "linhas_por_familia": {"Gol": 1, "Onix": 2},
    }


def test_compare_flags_drops_missing_families_and_removed_columns():
    old = _manifest(
        precos_atual={"linhas": 1000, "colunas": ["a", "b"], "linhas_por_familia": {"Gol": 600, "Onix": 400}},
        catalogo={"linhas": 50, "colunas": ["x"], "familias": 2},
    )
    new = _manifest(
        precos_atual={"linhas": 1100, "colunas": ["a", "c"], "linhas_por_familia": {"Onix": 1100}},  # Gol vanished
        catalogo={"linhas": 40, "colunas": ["x"], "familias": 2},  # -20 %
    )
    report, warnings = manifest.compare(old, new, threshold=0.10)
    assert warnings == [
        "catalogo.linhas dropped 20%: 50 → 40",
        "precos_atual.linhas_por_familia.Gol disappeared (was 600)",
        "precos_atual: columns removed: b",
    ]
    assert "| `precos_atual.linhas` | 1,000 | 1,100 | +10.0% |" in report  # growth is reported, not flagged
    assert "+c" in report
    assert "FIPE 2026-10-01" in report


def test_compare_identical_manifests_is_quiet():
    m = _manifest(precos={"linhas": 10, "colunas": ["a"]})
    report, warnings = manifest.compare(m, m)
    assert warnings == []
    assert "1 metric(s) unchanged." in report  # colunas aren't metrics


def test_cli_compare_without_previous_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    current = tmp_path / "manifest.json"
    current.write_text(json.dumps(_manifest(precos={"linhas": 1})), encoding="utf-8")
    assert manifest.main(["compare", str(tmp_path / "missing.json"), str(current)]) == 0
    assert "No previous manifest" in capsys.readouterr().out


def test_cli_strict_fails_on_warnings(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps(_manifest(precos={"linhas": 100})), encoding="utf-8")
    new.write_text(json.dumps(_manifest(precos={"linhas": 10})), encoding="utf-8")
    assert manifest.main(["compare", str(old), str(new)]) == 0
    assert manifest.main(["compare", str(old), str(new), "--strict"]) == 1


def test_publish_copies_hashed_manifest_to_stable_path(tmp_path):
    built = tmp_path / "_file" / "data" / "manifest.1a2b3c4d.json"
    built.parent.mkdir(parents=True)
    built.write_text('{"ok": true}', encoding="utf-8")
    assert manifest.main(["publish", "--dist", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == {"ok": True}
