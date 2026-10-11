---
title: Ranking
---

# Ranking dos modelos

```js
import {brlCompact, num, pct, pctInt, rows} from "./components/format.js";
import {palette} from "./components/palette.js";

const familias = rows(await FileAttachment("data/familias.parquet").parquet());
```

```js
const cores = palette(dark);
const metricas = new Map([
  ["Retenção em 5 anos (maior é melhor)", {campo: "retencao_5", desc: true, fmt: pctInt, label: "Retenção em 5 anos →"}],
  ["Depreciação anual (menor é melhor)", {campo: "taxa_anual", desc: false, fmt: pct, label: "Depreciação por ano →"}],
  ["Perda ao sair da loja (menor é melhor)", {campo: "perda_imediata", desc: false, fmt: pct, label: "Perda ao sair da loja →"}]
]);
```

```js
const metrica = view(Inputs.select(metricas, {label: "Ordenar por"}));
const segmento = view(Inputs.select(["Todos", ...new Set(familias.map((d) => d.segmento))], {label: "Segmento"}));
```

```js
const m = metrica;
const lista = d3.sort(
  familias.filter((d) => (segmento === "Todos" || d.segmento === segmento) && d[m.campo] != null),
  (d) => (m.desc ? -d[m.campo] : d[m.campo])
);
display(Plot.plot({
  width,
  height: 18 * lista.length + 40,
  marginLeft: 110,
  marginRight: 50,
  x: {label: m.label, tickFormat: "%", grid: true, nice: true},
  y: {domain: lista.map((d) => d.familia), label: null},
  marks: [
    Plot.ruleY(lista, {y: "familia", x1: 0, x2: m.campo, stroke: cores.muted}),
    Plot.dot(lista, {
      y: "familia",
      x: m.campo,
      r: 5,
      fill: cores.accent,
      stroke: "var(--theme-background)",
      strokeWidth: 2,
      channels: {Marca: "marca", Segmento: "segmento", "Versões": "n_series"},
      tip: {format: {x: m.fmt}}
    }),
    Plot.text(lista, {y: "familia", x: m.campo, text: (d) => m.fmt(d[m.campo]), dx: 10, textAnchor: "start", fill: "var(--theme-foreground-muted)", fontSize: 10})
  ]
}));
```

<p class="muted small">Modelos fora de linha não têm preço de zero km, então não aparecem no ranking de perda ao sair da loja. Na retenção em 5 anos, eles usam a perda média de todos os modelos.</p>

## Tabela completa

```js
Inputs.table(lista, {
  columns: ["familia", "marca", "segmento", "propulsao", "taxa_anual", "perda_imediata", "retencao_3", "retencao_5", "preco_novo_mediano", "n_series", "n_precos"],
  header: {
    familia: "Modelo", marca: "Marca", segmento: "Segmento", propulsao: "Combustível", taxa_anual: "Deprec./ano",
    perda_imediata: "Saída da loja", retencao_3: "Retém 3 anos", retencao_5: "Retém 5 anos",
    preco_novo_mediano: "Preço de novo", n_series: "Versões", n_precos: "Preços"
  },
  format: {taxa_anual: pct, perda_imediata: pct, retencao_3: pctInt, retencao_5: pctInt, preco_novo_mediano: brlCompact, n_series: num, n_precos: num},
  layout: "auto",
  rows: 25
})
```

## Como é calculado

Para cada modelo, o preço de cada versão em cada ano-modelo (na tabela FIPE mais recente) é ajustado pela regressão

<p class="formula">log(preço) = a<sub>versão</sub> + b · idade + c · zero km</p>

- **a<sub>versão</sub>**: um nível de preço próprio de cada versão. Assim, uma versão topo de linha não é comparada com uma de entrada, e sim só com os próprios anos-modelo anteriores.
- **Depreciação anual** = 1 − e<sup>b</sup>: quanto o carro usado perde, em %, a cada ano de idade.
- **Perda ao sair da loja** = 1 − e<sup>−c</sup>: a diferença entre o zero km e um seminovo da mesma versão quase sem uso.
- **Retenção em t anos** = e<sup>b·t − c</sup>: quanto sobra do preço de novo depois de t anos.

O modelo supõe uma perda percentual constante por ano. Em <a href="./curvas">Curva por modelo</a> você vê a perda ano a ano, sem essa suposição.

<style>
.formula { font-family: var(--monospace); font-size: 1rem; padding: 0.5rem 0; }
.small { font-size: 0.85rem; }
</style>
