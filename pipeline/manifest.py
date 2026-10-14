"""Data manifest: what each build was made from, and how it compares to the last one.

``build()`` records the code version, the FIPE reference month, when each raw
source was downloaded and row counts of every cleaned frame (overall, per year
and per family). The site publishes it at a stable URL (``/manifest.json``), so
CI can fetch the live copy before deploying and report what changed:

    python -m pipeline.manifest publish                     # dist/_file/... -> dist/manifest.json
    python -m pipeline.manifest compare previous.json dist/manifest.json

``compare`` warns on any metric that dropped by more than ``--threshold``
(default 10 %) and on output columns that disappeared. Here the usual culprits
are a FIPE version renamed so a family regex no longer matches it (the family's
row count drops or vanishes) and a month whose prices weren't committed. It
never fails the build unless ``--strict`` is given.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import polars as pl

from . import bcb, fipe, frames, painel
from .http import ROOT, cached_path


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _source(nome: str, url: str, *, params: dict | None = None, data: dict | None = None) -> dict:
    """A raw download and when it entered the cache. Never includes request
    headers. Form fields (FIPE's POSTs) are shown as a query string."""
    path = cached_path(url, params=params, data=data, suffix=".json")
    query = params or data
    return {
        "nome": nome,
        "url": url + (f"?{urlencode(query)}" if query else ""),
        "baixado_em": _iso(path.stat().st_mtime) if path else None,
    }


def _table(df: pl.DataFrame, *, por: list[str] | None = None) -> dict:
    """Row count and columns, plus row counts per value of each column in ``por``."""
    out: dict = {"linhas": df.height, "colunas": df.columns}
    for col in por or []:
        grupos = df.group_by(col).agg(pl.len().alias("linhas")).drop_nulls(col).sort(col)
        out[f"linhas_por_{col}"] = {str(r[col]): r["linhas"] for r in grupos.iter_rows(named=True)}
    return out


def build() -> dict:
    refs = frames.referencias()
    ref = int(refs["ref"][-1])
    cat = frames.catalogo()
    precos = frames.precos().with_columns(pl.col("mes").dt.year().alias("ano"))
    atual = frames.atual()
    ipca = bcb.ipca(painel.ANO_MIN - 1)

    fontes = [
        _source("FIPE — tabelas de referência", f"{fipe.API}/ConsultarTabelaDeReferencia", data={}),
        _source(
            f"FIPE — marcas da tabela {ref}",
            f"{fipe.API}/ConsultarMarcas",
            data={"codigoTabelaReferencia": ref, "codigoTipoVeiculo": fipe.CARROS},
        ),
        # The IPCA is requested in ten-year windows; which ones depends on the
        # first year each loader asks for, so list every window that was downloaded.
        *[
            f
            for inicio in (painel.ANO_MIN - 1, painel.ANO_MIN)
            for url, params in bcb.janelas(bcb.IPCA_MENSAL, inicio)
            if (f := _source(f"BCB — IPCA {params['dataInicial'][-4:]}–{params['dataFinal'][-4:]}", url, params=params))["baixado_em"]
        ],
    ]
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": os.environ.get("GITHUB_SHA"),
        "codigo_pipeline": frames.CODE_VERSION,
        "referencia_fipe": {"codigo": ref, "mes": refs["mes"][-1].isoformat()},
        "parametros": {"ano_min": painel.ANO_MIN, "versoes_por_familia": painel.VERSOES, "familias": painel.FAMILIAS or None},
        "fontes": list({f["url"]: f for f in fontes}.values()),
        "tabelas": {
            "referencias": {"meses": refs.height},
            "catalogo": _table(cat, por=["marca"]) | {"familias": cat["familia"].n_unique()},
            "precos": _table(precos, por=["ano"]),
            "precos_atual": _table(atual, por=["familia"]) | {"series": atual.select(painel.SERIE).n_unique()},
            "ipca": {"meses": ipca.height, "ultimo_mes": ipca["mes"].max().isoformat()},
        },
    }


# ------------------------------------------------------------------- compare


def _numbers(d: dict, prefix: str = "") -> dict[str, float]:
    """Flatten numeric leaves: {"precos": {"linhas": 3}} -> {"precos.linhas": 3}."""
    out: dict[str, float] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out |= _numbers(v, f"{key}.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = v
    return out


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.4g}"


def compare(old: dict, new: dict, threshold: float = 0.10) -> tuple[str, list[str]]:
    """Markdown report of changed metrics, and the list of warnings."""
    warnings: list[str] = []
    rows: list[str] = []
    a, b = _numbers(old.get("tabelas", {})), _numbers(new.get("tabelas", {}))
    unchanged = 0
    for key in sorted(a.keys() | b.keys()):
        va, vb = a.get(key), b.get(key)
        if va == vb:
            unchanged += 1
            continue
        change = (vb - va) / abs(va) if va not in (None, 0) and vb is not None else None
        flag = ""
        if vb is None:
            flag = "⚠"
            warnings.append(f"{key} disappeared (was {_fmt(va)})")
        elif change is not None and change < -threshold:
            flag = "⚠"
            warnings.append(f"{key} dropped {-change:.0%}: {_fmt(va)} → {_fmt(vb)}")
        rows.append(f"| {f'{flag} ' if flag else ''}`{key}` | {_fmt(va)} | {_fmt(vb)} | {'—' if change is None else f'{change:+.1%}'} |")

    for name, table in new.get("tabelas", {}).items():
        before = set(old.get("tabelas", {}).get(name, {}).get("colunas", []))
        after = set(table.get("colunas", []))
        if before and (gone := before - after):
            warnings.append(f"{name}: columns removed: {', '.join(sorted(gone))}")
        if before and (added := after - before):
            rows.append(f"| `{name}.colunas` | | +{', '.join(sorted(added))} | |")

    mes = lambda m: (m.get("referencia_fipe") or {}).get("mes", "?")  # noqa: E731
    lines = [
        "## Data manifest vs. live site",
        "",
        f"Previous build: {old.get('gerado_em', '?')} (FIPE {mes(old)}, code `{old.get('codigo_pipeline', '?')}`) · "
        f"this build: {new.get('gerado_em', '?')} (FIPE {mes(new)}, code `{new.get('codigo_pipeline', '?')}`)",
        "",
    ]
    if warnings:
        lines += [f"### ⚠ {len(warnings)} warning(s)", "", *[f"- {w}" for w in warnings], ""]
    if rows:
        lines += ["| Metric | Previous | Current | Change |", "|---|--:|--:|--:|", *rows, ""]
    lines.append(f"{unchanged} metric(s) unchanged.")
    lines += ["", "### Sources", "", "| Source | Downloaded |", "|---|---|"]
    lines += [f"| [{f['nome']}]({f['url']}) | {f['baixado_em'] or '—'} |" for f in new.get("fontes", [])]
    return "\n".join(lines) + "\n", warnings


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _publish(dist: Path) -> Path:
    """Copy Framework's content-hashed copy of the manifest to a stable URL."""
    candidates = [p for p in dist.glob("_file/**/manifest*.json") if re.fullmatch(r"manifest(\.[0-9a-f]+)?\.json", p.name)]
    if len(candidates) != 1:
        raise SystemExit(f"expected one built manifest under {dist}/_file, found {len(candidates)}: {candidates}")
    target = dist / "manifest.json"
    shutil.copyfile(candidates[0], target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline.manifest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pub = sub.add_parser("publish", help="copy the built manifest to dist/manifest.json")
    pub.add_argument("--dist", type=Path, default=ROOT / "dist")
    cmp_ = sub.add_parser("compare", help="report changes between two manifests")
    cmp_.add_argument("previous", type=Path)
    cmp_.add_argument("current", type=Path)
    cmp_.add_argument("--threshold", type=float, default=0.10, help="warn on drops larger than this fraction")
    cmp_.add_argument("--strict", action="store_true", help="exit 1 when there are warnings")
    args = parser.parse_args(argv)

    if args.cmd == "publish":
        print(f"manifest published at {_publish(args.dist)}")
        return 0

    new = _load(args.current)
    if new is None:
        print(f"::error::cannot read {args.current}")
        return 1
    old = _load(args.previous)
    if old is None:
        report, warnings = "## Data manifest\n\nNo previous manifest to compare with (first deploy?).\n", []
    else:
        report, warnings = compare(old, new, args.threshold)

    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    else:
        sys.stdout.write(report)
    if in_ci:
        for w in warnings:
            print(f"::warning title=Data regression::{w}")
    return 1 if args.strict and warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
