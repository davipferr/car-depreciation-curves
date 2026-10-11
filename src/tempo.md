---
title: Ao longo do tempo
---

# Ao longo do tempo

As outras páginas usam só a tabela FIPE mais recente. Aqui, a versão principal de cada modelo (a que tem mais anos-modelo) é consultada em todo mês de janeiro desde o lançamento. Assim dá para seguir **o mesmo carro** ano a ano.

```js
import {brl, brlCompact, mesAno, num, pct, pctSigned, rows} from "./components/format.js";
import {palette} from "./components/palette.js";

const tempo = rows(await FileAttachment("data/tempo.parquet").parquet());
const precos = rows(await FileAttachment("data/precos.parquet").parquet());
const versoes = rows(await FileAttachment("data/versoes.parquet").parquet());
```

```js
const cores = palette(dark);
const todos = tempo.filter((d) => d.segmento === "Todos");
const SERIES = ["Usado (mesmo carro)", "Zero km (mesma versão)", "IPCA"];
const variacao = (campo) => [
  ...todos.filter((d) => d.condicao === "Usado").map((d) => ({ano: d.ano_ref, serie: SERIES[0], v: d[campo], n: d.n_carros})),
  ...todos.filter((d) => d.condicao === "Zero km").map((d) => ({ano: d.ano_ref, serie: SERIES[1], v: d[campo], n: d.n_carros})),
  ...(campo === "var_nominal" ? todos.filter((d) => d.condicao === "Usado" && d.ipca_12m != null).map((d) => ({ano: d.ano_ref, serie: SERIES[2], v: d.ipca_12m})) : [])
];
function grafico(dados, label) {
  const series = SERIES.filter((s) => dados.some((d) => d.serie === s));
  return Plot.plot({
    width,
    height: 320,
    marginRight: 150,
    x: {label: "Janeiro de →", tickFormat: "d", ticks: d3.range(d3.min(dados, (d) => d.ano), d3.max(dados, (d) => d.ano) + 1)},
    y: {label, tickFormat: "+.0%", grid: true},
    color: {domain: series, range: [cores.accent, cores.categorical[1], cores.muted], legend: true},
    marks: [
      Plot.ruleY([0]),
      Plot.line(dados, {x: "ano", y: "v", stroke: "serie", strokeWidth: 2, strokeDasharray: (d) => (d.serie === "IPCA" ? "4,3" : null)}),
      Plot.dot(dados, {x: "ano", y: "v", fill: "serie", r: 4, stroke: "var(--theme-background)", strokeWidth: 2}),
      Plot.text(dados, Plot.selectLast({x: "ano", y: "v", z: "serie", text: "serie", dx: 8, textAnchor: "start", fill: "var(--theme-foreground)", fontSize: 11})),
      Plot.tip(dados, Plot.pointerX({x: "ano", y: "v", channels: {Série: "serie", Carros: "n"}, format: {y: pctSigned, x: (x) => `jan/${x - 1} → jan/${x}`, stroke: false}}))
    ]
  });
}
```

## Quanto o mesmo carro mudou de preço em 12 meses

Para cada janeiro: a variação mediana do preço do mesmo usado (mesma versão e ano-modelo, um ano mais velho) e a variação do zero km da mesma versão, comparadas com a inflação dos 12 meses anteriores.

```js
display(grafico(variacao("var_nominal"), "↑ Variação nominal em 12 meses"));
```

<p class="muted small">Num ano normal, o usado fica mais barato: ele envelheceu um ano. Na pandemia, a falta de chips parou as fábricas e os zero km ficaram escassos e caros, então muitos usados <strong>subiram</strong> de preço mesmo envelhecendo.</p>

## O mesmo gráfico, descontada a inflação

```js
display(grafico(variacao("var_real"), "↑ Variação real (IPCA) em 12 meses"));
```

## Siga um carro

```js
const chefes = versoes.filter((v) => v.carro_chefe);
const nomes = d3.sort([...new Set(chefes.map((v) => v.familia))], (d) => d.localeCompare("pt-BR"));
const familia = view(Inputs.select(nomes, {label: "Modelo", value: nomes.includes("Gol") ? "Gol" : nomes[0]}));
```

```js
const hist = precos.filter((d) => d.familia === familia && d.rank === 0);
const anosModelo = d3.sort([...new Set(hist.filter((d) => !d.zero_km).map((d) => d.ano_modelo))]);
const ano = view(Inputs.select(anosModelo, {label: "Ano-modelo", format: String, value: anosModelo.find((a) => a >= 2019) ?? anosModelo[0]}));
const termos = view(Inputs.radio(["Nominal", "Real (IPCA)"], {label: "Valores", value: "Nominal"}));
```

```js
const chefe = chefes.find((v) => v.familia === familia);
const campo = termos === "Nominal" ? "preco" : "preco_real";
const linha = [
  ...hist.filter((d) => d.ano_modelo === ano).map((d) => ({...d, serie: `${familia} ${ano}`})),
  ...hist.filter((d) => d.zero_km && new Date(d.mes).getUTCFullYear() >= ano).map((d) => ({...d, serie: "Zero km da mesma versão"}))
];
const seriesCarro = [`${familia} ${ano}`, "Zero km da mesma versão"];
display(Plot.plot({
  width,
  height: 340,
  marginLeft: 70,
  marginRight: 170,
  x: {type: "utc", label: null},
  y: {label: `↑ Preço FIPE (${termos === "Nominal" ? "R$ correntes" : "R$ de hoje"})`, tickFormat: brlCompact, grid: true, zero: true},
  color: {domain: seriesCarro, range: [cores.accent, cores.categorical[1]], legend: true},
  marks: [
    Plot.line(linha, {x: "mes", y: campo, stroke: "serie", strokeWidth: 2}),
    Plot.dot(linha, {x: "mes", y: campo, fill: "serie", r: 4, stroke: "var(--theme-background)", strokeWidth: 2}),
    Plot.text(linha, Plot.selectLast({x: "mes", y: campo, z: "serie", text: "serie", dx: 8, textAnchor: "start", fill: "var(--theme-foreground)", fontSize: 11})),
    Plot.tip(linha, Plot.pointer({x: "mes", y: campo, channels: {Série: "serie", Idade: (d) => (d.zero_km ? "zero km" : `${d.idade.toFixed(1).replace(".", ",")} anos`)}, format: {x: (x) => mesAno(x), y: brl, stroke: false}}))
  ]
}));
```

<p class="muted small">Versão acompanhada: <em>${chefe.versao}</em>. A linha do zero km só existe enquanto essa versão foi vendida nova. Os valores reais estão em reais do último mês com IPCA publicado.</p>

<style>
.small { font-size: 0.85rem; }
</style>
