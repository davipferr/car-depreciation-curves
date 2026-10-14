---
title: O que explica a depreciação
---

# O que explica a depreciação

Aqui o mesmo modelo de <a href="./ranking">Ranking</a> é ajustado juntando todas as versões que têm uma característica em comum, sem separar por modelo. Cada grupo continua sendo comparado só com os próprios anos-modelo anteriores. Por isso, um câmbio automático é comparado com seminovos automáticos, e não com carros manuais.

```js
import {num, pct, pctInt, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {hbars} from "./components/charts.js";

const grupos = rows(await FileAttachment("data/grupos.parquet").parquet());
const perdas = rows(await FileAttachment("data/perdas.parquet").parquet());
```

```js
const cores = palette(dark);
const MIN_SERIES = 5;
// Bars of one dimension, sorted by value (or by the band order for price bands).
// Every panel of the same metric shares the x domain, so bar lengths compare across cards.
function painel(dimensao, {campo = "taxa_anual"} = {}, largura = 560) {
  const dados = grupos.filter((d) => d.dimensao === dimensao && d[campo] != null && d.n_series >= MIN_SERIES);
  const ordenados = dados.some((d) => d.ordem != null) ? d3.sort(dados, (d) => d.ordem) : d3.sort(dados, (d) => d[campo]);
  return hbars(ordenados, {
    width: largura,
    y: "grupo",
    x: campo,
    fill: cores.accent,
    sort: null,
    xMax: d3.max(grupos, (d) => d[campo]) * 1.05,
    maxMargin: 150,
    channels: {Versões: "n_series", Preços: "n_precos"}
  });
}
```

## Premium × generalista

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Depreciação por ano</h2>
    ${resize((w) => painel("Categoria", {}, w))}
  </div>
  <div class="card">
    <h2>Perda ao sair da loja</h2>
    ${resize((w) => painel("Categoria", {campo: "perda_imediata"}, w))}
  </div>
</div>

<p class="muted small">Premium: BMW, Mercedes-Benz, Audi, Volvo, Land Rover, Porsche, Lexus, RAM e MINI. Generalista: as demais marcas.</p>

## Câmbio

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Depreciação por ano</h2>
    ${resize((w) => painel("Câmbio", {}, w))}
  </div>
  <div class="card">
    <h2>Perda ao sair da loja</h2>
    ${resize((w) => painel("Câmbio", {campo: "perda_imediata"}, w))}
  </div>
</div>

O **automatizado** é um câmbio manual com embreagem robotizada (Dualogic, Easytronic, I-Motion, GSR). É mais barato que um automático de verdade e tem má fama no mercado de usados. A FIPE não tem campo de câmbio: a classificação vem do nome da versão (<a href="./sobre">detalhes</a>).

## Segmento e faixa de preço

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Depreciação por ano, por segmento</h2>
    ${resize((w) => painel("Segmento", {}, w))}
  </div>
  <div class="card">
    <h2>Depreciação por ano, por faixa de preço de novo</h2>
    ${resize((w) => painel("Preço de novo", {}, w))}
  </div>
</div>

## Combustível e motor

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Depreciação por ano, por combustível</h2>
    ${resize((w) => painel("Combustível", {}, w))}
  </div>
  <div class="card">
    <h2>Depreciação por ano, por tipo de motor</h2>
    ${resize((w) => painel("Motor", {}, w))}
  </div>
</div>

<p class="muted small">Elétricos e a maioria dos híbridos chegaram ao mercado há poucos anos, então as curvas deles cobrem só as idades iniciais. Grupos com menos de ${MIN_SERIES} versões não aparecem.</p>

## Marca

<div class="card">
  <h2>Depreciação por ano, por marca</h2>
  ${resize((w) => painel("Marca", {}, w))}
</div>

## Perda ano a ano por segmento

```js
const segs = ["Hatch", "Sedã", "SUV"].filter((s) => perdas.some((d) => d.nivel === "segmento" && d.grupo === s));
const ps = perdas.filter((d) => d.nivel === "segmento" && segs.includes(d.grupo) && d.idade >= 0 && d.idade <= 10 && d.n_pares >= 5);
```

<div class="card">
  <h2>Perda mediana em cada ano de vida: ${segs.join(", ")}</h2>
  <h3>Anos-modelo vizinhos da mesma versão; só idades com 5 pares ou mais</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 300,
    marginRight: 60,
    x: {label: "Idade (anos) →", ticks: 10, tickFormat: (d) => (width < 520 ? String(d) : `${d}→${d + 1}`)},
    y: {label: "↑ Perda no ano (mediana)", tickFormat: "%", grid: true, zero: true},
    color: {domain: segs, range: cores.categorical.slice(0, 3), legend: true},
    marks: [
      Plot.ruleY([0], {strokeOpacity: 0.4}),
      Plot.line(ps, {x: "idade", y: "perda_mediana", stroke: "grupo", strokeWidth: 2}),
      Plot.dot(ps, {x: "idade", y: "perda_mediana", fill: "grupo", r: 4, stroke: "var(--theme-background-alt)", strokeWidth: 2,
        channels: {Pares: "n_pares"}, tip: {format: {y: pct, x: (x) => `${x} → ${x + 1} anos`}}}),
      Plot.text(ps, Plot.selectLast({x: "idade", y: "perda_mediana", z: "grupo", text: "grupo", fill: "grupo", dx: 8, textAnchor: "start", fontSize: 11, fontWeight: 600}))
    ]
  }))}
</div>
