---
title: O que explica a depreciação
---

# O que explica a depreciação

Aqui o mesmo modelo de <a href="./ranking">Ranking</a> é ajustado juntando todas as versões que têm uma característica em comum, sem separar por modelo. Cada grupo continua sendo comparado só com os próprios anos-modelo anteriores. Por isso, um câmbio automático é comparado com seminovos automáticos, e não com carros manuais.

```js
import {num, pct, pctInt, rows} from "./components/format.js";
import {palette} from "./components/palette.js";

const grupos = rows(await FileAttachment("data/grupos.parquet").parquet());
const perdas = rows(await FileAttachment("data/perdas.parquet").parquet());
```

```js
const cores = palette(dark);
const MIN_SERIES = 5;
function painel(dimensao, {campo = "taxa_anual", label = "Depreciação por ano →", fmt = pct} = {}, largura = 560) {
  const dados = grupos.filter((d) => d.dimensao === dimensao && d[campo] != null && d.n_series >= MIN_SERIES);
  const ordenados = dados.some((d) => d.ordem != null) ? d3.sort(dados, (d) => d.ordem) : d3.sort(dados, (d) => d[campo]);
  return Plot.plot({
    width: largura,
    height: 24 * ordenados.length + 44,
    marginLeft: 130,
    marginRight: 50,
    x: {label, tickFormat: "%", grid: true, domain: [0, d3.max(grupos, (d) => d[campo]) * 1.1]},
    y: {domain: ordenados.map((d) => d.grupo), label: null},
    marks: [
      Plot.barX(ordenados, {y: "grupo", x: campo, fill: cores.accent, insetTop: 4, insetBottom: 4, rx: 2,
        channels: {"Versões": "n_series", "Preços": "n_precos"}, tip: {format: {x: fmt}}}),
      Plot.text(ordenados, {y: "grupo", x: campo, text: (d) => fmt(d[campo]), dx: 6, textAnchor: "start", fill: "var(--theme-foreground-muted)", fontSize: 11})
    ]
  });
}
```

## Premium × generalista

<div class="grid grid-cols-2">
  <div class="card">${resize((w) => painel("Categoria", {}, w))}</div>
  <div class="card">${resize((w) => painel("Categoria", {campo: "perda_imediata", label: "Perda ao sair da loja →"}, w))}</div>
</div>

<p class="muted small">Premium: BMW, Mercedes-Benz, Audi, Volvo, Land Rover, Porsche, Lexus, RAM e MINI. Generalista: as demais marcas.</p>

## Câmbio

<div class="grid grid-cols-2">
  <div class="card">${resize((w) => painel("Câmbio", {}, w))}</div>
  <div class="card">${resize((w) => painel("Câmbio", {campo: "perda_imediata", label: "Perda ao sair da loja →"}, w))}</div>
</div>

O **automatizado** é um câmbio manual com embreagem robotizada (Dualogic, Easytronic, I-Motion, GSR). É mais barato que um automático de verdade e tem má fama no mercado de usados. A FIPE não tem campo de câmbio: a classificação vem do nome da versão (<a href="./sobre">detalhes</a>).

## Segmento e faixa de preço

<div class="grid grid-cols-2">
  <div class="card">${resize((w) => painel("Segmento", {}, w))}</div>
  <div class="card">${resize((w) => painel("Preço de novo", {}, w))}</div>
</div>

## Combustível e motor

<div class="grid grid-cols-2">
  <div class="card">${resize((w) => painel("Combustível", {}, w))}</div>
  <div class="card">${resize((w) => painel("Motor", {}, w))}</div>
</div>

<p class="muted small">Elétricos e a maioria dos híbridos chegaram ao mercado há poucos anos, então as curvas deles cobrem só as idades iniciais. Grupos com menos de ${MIN_SERIES} versões não aparecem.</p>

## Marca

<div class="card">${resize((w) => painel("Marca", {}, w))}</div>

## Perda ano a ano por segmento

```js
const segs = ["Hatch", "Sedã", "SUV"].filter((s) => perdas.some((d) => d.nivel === "segmento" && d.grupo === s));
const ps = perdas.filter((d) => d.nivel === "segmento" && segs.includes(d.grupo) && d.idade >= 0 && d.idade <= 10 && d.n_pares >= 5);
display(Plot.plot({
  width,
  height: 300,
  x: {label: "Idade (anos) →", ticks: 10, tickFormat: (d) => `${d}→${d + 1}`},
  y: {label: "↑ Perda no ano (mediana)", tickFormat: "%", grid: true, zero: true},
  color: {domain: segs, range: cores.categorical.slice(0, 3), legend: true},
  marks: [
    Plot.line(ps, {x: "idade", y: "perda_mediana", stroke: "grupo", strokeWidth: 2}),
    Plot.dot(ps, {x: "idade", y: "perda_mediana", fill: "grupo", r: 4, stroke: "var(--theme-background)", strokeWidth: 2,
      channels: {Pares: "n_pares"}, tip: {format: {y: pct, x: (x) => `${x} → ${x + 1} anos`}}}),
    Plot.text(ps, Plot.selectLast({x: "idade", y: "perda_mediana", z: "grupo", text: "grupo", dx: 8, textAnchor: "start", fill: "var(--theme-foreground)"}))
  ],
  marginRight: 50
}));
```

<style>
.small { font-size: 0.85rem; }
</style>
