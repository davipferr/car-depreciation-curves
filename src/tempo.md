---
title: Ao longo do tempo
---

# Ao longo do tempo

As outras páginas usam só a tabela FIPE mais recente. Aqui, a versão principal de cada modelo (a que tem mais anos-modelo) é consultada em todo mês de janeiro desde o lançamento. Assim dá para seguir **o mesmo carro** ano a ano.

```js
import {brl, brlCompact, mesAno, num, pct, pctSigned, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {periodoMarks, rotuloMark} from "./components/charts.js";

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
// The 2021-22 chip shortage: Januaries 2021 and 2022 (each compared with the year before).
const CRISE = {de: 2021, ate: 2022, nome: "Falta de chips"};
function grafico(dados, label, width) {
  const series = SERIES.filter((s) => dados.some((d) => d.serie === s));
  const estreito = width < 640;
  const pico = d3.greatest(dados.filter((d) => d.serie === SERIES[0]), (d) => d.v);
  return Plot.plot({
    width,
    height: 340,
    marginRight: estreito ? 16 : 150,
    x: {label: "Janeiro de →", tickFormat: (d) => (estreito ? `'${String(d).slice(2)}` : String(d)), ticks: d3.range(d3.min(dados, (d) => d.ano), d3.max(dados, (d) => d.ano) + 1)},
    y: {label, tickFormat: "+.0%", grid: true, insetTop: 22},
    color: {domain: series, range: [cores.accent, cores.categorical[1], cores.muted], legend: true},
    marks: [
      ...periodoMarks([CRISE.de - 0.5, CRISE.ate + 0.5], CRISE.nome),
      Plot.ruleY([0], {strokeOpacity: 0.4}),
      Plot.line(dados, {x: "ano", y: "v", stroke: "serie", strokeWidth: 2, strokeDasharray: (d) => (d.serie === "IPCA" ? "4,3" : null)}),
      Plot.dot(dados, {x: "ano", y: "v", fill: "serie", r: 4, stroke: "var(--theme-background-alt)", strokeWidth: 2}),
      estreito ? null : Plot.text(dados, Plot.selectLast({x: "ano", y: "v", z: "serie", text: "serie", fill: "serie", dx: 8, textAnchor: "start", fontSize: 11, fontWeight: 600})),
      pico?.v > 0 ? rotuloMark(pico, {x: "ano", y: "v", text: (d) => `usado: ${pctSigned(d.v)}`, dx: 8, dy: 0, textAnchor: "start", lineAnchor: "middle"}) : null,
      Plot.tip(dados, Plot.pointerX({x: "ano", y: "v", channels: {Série: "serie", Carros: "n"}, format: {y: pctSigned, x: (x) => `jan/${x - 1} → jan/${x}`, stroke: false, fill: false}}))
    ]
  });
}
```

## Quanto o mesmo carro mudou de preço em 12 meses

Para cada janeiro: a variação mediana do preço do mesmo usado (mesma versão e ano-modelo, um ano mais velho) e a variação do zero km da mesma versão, comparadas com a inflação dos 12 meses anteriores.

<div class="card">
  <h2>Variação nominal do preço em 12 meses</h2>
  <h3>Mediana dos carros acompanhados; a faixa cinza marca a falta de chips de 2021–22</h3>
  ${resize((width) => grafico(variacao("var_nominal"), "↑ Variação nominal em 12 meses", width))}
</div>

<p class="muted small">Num ano normal, o usado fica mais barato: ele envelheceu um ano. Na pandemia, a falta de chips parou as fábricas e os zero km ficaram escassos e caros, então muitos usados <strong>subiram</strong> de preço mesmo envelhecendo.</p>

## O mesmo gráfico, descontada a inflação

<div class="card">
  <h2>Variação real (descontado o IPCA) em 12 meses</h2>
  <h3>Abaixo de zero, o carro perdeu valor em relação aos outros preços da economia</h3>
  ${resize((width) => grafico(variacao("var_real"), "↑ Variação real (IPCA) em 12 meses", width))}
</div>

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
```

<div class="card">
  <h2>${familia} ${ano}: preço FIPE em cada janeiro${termos === "Nominal" ? "" : " (R$ de hoje)"}</h2>
  <h3>Comparado com o zero km da mesma versão enquanto ela foi vendida nova</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 340,
    marginLeft: 70,
    marginRight: width < 640 ? 16 : 170,
    x: {type: "utc", label: null},
    y: {label: `↑ Preço FIPE (${termos === "Nominal" ? "R$ correntes" : "R$ de hoje"})`, tickFormat: brlCompact, grid: true, zero: true, insetTop: 22},
    color: {domain: seriesCarro, range: [cores.accent, cores.categorical[1]], legend: true},
    marks: [
      ...periodoMarks([new Date(Date.UTC(CRISE.de - 1, 6, 1)), new Date(Date.UTC(CRISE.ate, 6, 1))], CRISE.nome),
      Plot.line(linha, {x: "mes", y: campo, stroke: "serie", strokeWidth: 2}),
      Plot.dot(linha, {x: "mes", y: campo, fill: "serie", r: 4, stroke: "var(--theme-background-alt)", strokeWidth: 2}),
      width < 640 ? null : Plot.text(linha, Plot.selectLast({x: "mes", y: campo, z: "serie", text: "serie", fill: "serie", dx: 8, textAnchor: "start", fontSize: 11, fontWeight: 600})),
      Plot.tip(linha, Plot.pointer({x: "mes", y: campo, channels: {Série: "serie", Idade: (d) => (d.zero_km ? "zero km" : `${d.idade.toFixed(1).replace(".", ",")} anos`)}, format: {x: (x) => mesAno(x), y: brl, stroke: false, fill: false}}))
    ]
  }))}
</div>

<p class="muted small">Versão acompanhada: <em>${chefe.versao}</em>. A linha do zero km só existe enquanto essa versão foi vendida nova. Os valores reais estão em reais do último mês com IPCA publicado.</p>
