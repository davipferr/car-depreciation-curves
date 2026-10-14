---
title: Curva por modelo
---

# Curva por modelo

```js
import {anos, brl, brlCompact, mesAno, num, pct, pctInt, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {meter} from "./components/charts.js";

const familias = rows(await FileAttachment("data/familias.parquet").parquet());
const precos = rows(await FileAttachment("data/precos.parquet").parquet());
const versoes = rows(await FileAttachment("data/versoes.parquet").parquet());
const perdas = rows(await FileAttachment("data/perdas.parquet").parquet());
```

```js
const cores = palette(dark);
const mesAtual = d3.max(precos, (d) => d.mes);
const atual = precos.filter((d) => +d.mes === +mesAtual);
const nomes = d3.sort(familias.map((d) => d.familia), (d) => d.localeCompare("pt-BR"));
const versaoPor = new Map(versoes.map((v) => [`${v.modelo_code}-${v.combustivel_code}`, v]));
```

```js
// Links from other pages open a model directly: /curvas#Onix
const doHash = decodeURIComponent(location.hash.slice(1));
const familia = view(Inputs.select(nomes, {label: "Modelo", value: nomes.includes(doHash) ? doHash : nomes.includes("Onix") ? "Onix" : nomes[0]}));
```

```js
// Keep the URL shareable.
history.replaceState(null, "", `#${encodeURIComponent(familia)}`);
const f = familias.find((d) => d.familia === familia);
// Share of the other models this one beats (loses value more slowly / keeps more).
const melhorQue = (campo, menorMelhor) => {
  const outros = familias.filter((d) => d.familia !== familia && d[campo] != null);
  return f[campo] == null ? null : outros.filter((d) => (menorMelhor ? d[campo] > f[campo] : d[campo] < f[campo])).length / outros.length;
};
const pTaxa = melhorQue("taxa_anual", true);
const pRet = melhorQue("retencao_5", false);
const pontos = atual
  .filter((d) => d.familia === familia)
  .map((d) => ({...d, versao: versaoPor.get(`${d.modelo_code}-${d.combustivel_code}`)?.versao}));
const curva = (b, c) => d3.range(0, 20.01, 0.25).map((t) => ({idade: t, retencao: Math.exp(b * t - c)}));
const idadeMax = Math.max(6, d3.max(pontos, (d) => d.idade) ?? 0);
```

<p class="muted">${f.marca} · ${f.segmento} · ${f.vendido_zero_km ? "ainda vendido zero km" : "fora de linha (sem preço de zero km na tabela atual)"} · FIPE de ${mesAno(mesAtual)}</p>

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Depreciação anual</h2>
    <span class="big">${pct(f.taxa_anual)}</span>
    ${meter(pTaxa, cores, `${f.familia} perde valor mais devagar que ${pctInt(pTaxa)} dos modelos`)}
    <p class="muted">por ano de idade; deprecia menos que ${pctInt(pTaxa)} dos ${familias.length - 1} outros modelos</p>
  </div>
  <div class="card">
    <h2>Ao sair da loja</h2>
    <span class="big">${f.perda_imediata == null ? "–" : pct(f.perda_imediata)}</span>
    <p class="muted">${f.perda_imediata == null ? "sem zero km para comparar; as curvas usam a média de todos os modelos" : "zero km × seminovo da mesma versão"}</p>
  </div>
  <div class="card">
    <h2>Retenção em 3 / 5 anos</h2>
    <span class="big">${pctInt(f.retencao_3)} / ${pctInt(f.retencao_5)}</span>
    ${meter(f.retencao_5, cores, `${pctInt(f.retencao_5)} do preço de novo após 5 anos`)}
    <p class="muted">do preço de novo; em 5 anos, retém mais que ${pctInt(pRet)} dos modelos</p>
  </div>
  <div class="card">
    <h2>Preço de novo</h2>
    <span class="big">${brlCompact(f.preco_novo_mediano)}</span>
    <p class="muted">mediana das ${num(f.n_series)} versões acompanhadas</p>
  </div>
</div>

## Quanto vale, por idade

Cada ponto é uma versão e um ano-modelo, dividido pelo preço de novo estimado da mesma versão. A linha é a curva ajustada; a tracejada, a curva do modelo mediano. Compare com até três outros modelos:

```js
const comparar = view(Inputs.select(nomes.filter((n) => n !== familia), {label: "Comparar com", multiple: 3, value: []}));
```

```js
const linhas = [familia, ...comparar.slice(0, 3)].flatMap((nome, i) => {
  const g = familias.find((d) => d.familia === nome);
  return curva(g.b_idade, g.b_novo_efetivo).filter((d) => d.idade <= idadeMax).map((d) => ({...d, familia: nome}));
});
const ordem = [familia, ...comparar.slice(0, 3)];
const coresLinha = [cores.accent, ...cores.categorical.slice(1, 4)];
const tipica = curva(d3.median(familias, (d) => d.b_idade), d3.median(familias, (d) => d.b_novo_efetivo)).filter((d) => d.idade <= idadeMax);
```

<div class="card">
  <h2>${ordem.join(" × ")}: fração do preço de novo por idade</h2>
  <h3>FIPE de ${mesAno(mesAtual)}; o tracejado é a curva do modelo mediano. Passe o mouse sobre um ponto para ver a versão e o preço</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 400,
    marginRight: width < 520 ? 16 : 100,
    x: {label: "Idade (anos) →", domain: [0, idadeMax], grid: true},
    y: {label: "↑ Fração do preço de novo", tickFormat: "%", domain: [0, 1.05], grid: true},
    color: {domain: ordem, range: coresLinha, legend: width < 520 && ordem.length > 1},
    marks: [
      Plot.line(tipica, {x: "idade", y: "retencao", stroke: "currentColor", strokeOpacity: 0.5, strokeDasharray: "4,3"}),
      Plot.dot(pontos, {
        x: "idade",
        y: "retencao",
        r: 4,
        fill: cores.accent,
        fillOpacity: 0.35,
        channels: {Versão: "versao", "Ano-modelo": (d) => (d.zero_km ? "zero km" : d.ano_modelo), Preço: (d) => brl(d.preco)},
        tip: {format: {x: (x) => anos(x), y: (y) => pctInt(y)}}
      }),
      Plot.line(linhas, {x: "idade", y: "retencao", stroke: "familia", strokeWidth: 2.5}),
      width < 520 ? null : Plot.text(linhas, Plot.selectLast({x: "idade", y: "retencao", z: "familia", text: "familia", fill: "familia", dx: 6, textAnchor: "start", fontSize: 11, fontWeight: 600}))
    ]
  }))}
</div>

## A idade em que a perda se estabiliza

Perda mediana em cada ano de vida, comparando anos-modelo vizinhos da mesma versão. Quando as barras ficam baixas e estáveis, um ano a mais de idade custa pouco: é um bom ponto para comprar usado.

```js
const pf = perdas.filter((d) => d.nivel === "familia" && d.grupo === familia && d.idade <= 12);
const seg = new Map(perdas.filter((d) => d.nivel === "segmento" && d.grupo === f.segmento).map((d) => [d.idade, d.perda_mediana]));
const perdaPlot = (width) => Plot.plot({
  width,
  height: 260,
  marginTop: 24,
  x: {label: "Idade (anos)", type: "band", padding: 0.15, tickFormat: (d) => (d === -1 ? "0 km" : width < 520 ? String(d) : `${d}→${d + 1}`)},
  y: {axis: null},
  marks: [
    Plot.barY(pf, {
      x: "idade",
      y: "perda_mediana",
      fill: (d) => (d.idade === -1 ? cores.categorical[1] : cores.accent),
      ry1: 3,
      channels: {Pares: "n_pares", [`Mediana ${f.segmento}`]: (d) => pct(seg.get(d.idade))},
      tip: {format: {y: (y) => pct(y), fill: false}}
    }),
    Plot.tickY(pf, {x: "idade", y: (d) => seg.get(d.idade), stroke: "currentColor", strokeOpacity: 0.8, strokeWidth: 2, strokeDasharray: "3,2"}),
    Plot.text(pf, {x: "idade", y: (d) => Math.max(d.perda_mediana, seg.get(d.idade) ?? 0), text: (d) => pct(d.perda_mediana), dy: -8, lineAnchor: "bottom", fill: "currentColor", fontSize: width < 520 ? 9 : 11}),
    Plot.ruleY([0], {strokeOpacity: 0.4})
  ]
});
```

<div class="card">
  <h2>Perda mediana de ${familia} em cada ano de vida</h2>
  <h3>Em laranja, a saída da loja; o tracejado é a mediana do segmento ${f.segmento}. Idades com poucos pares (veja <em>Pares</em> na dica) são ruidosas</h3>
  ${pf.length ? resize(perdaPlot) : html`<p class="muted">Poucos anos-modelo para calcular.</p>`}
</div>

## Preços na tabela atual

```js
const tabela = d3.sort(pontos, (d) => d.versao, (d) => -(d.zero_km ? 9999 : d.ano_modelo));
display(Inputs.table(tabela, {
  columns: ["versao", "ano_modelo", "preco", "idade", "retencao"],
  header: {versao: "Versão", ano_modelo: "Ano-modelo", preco: "Preço FIPE", idade: "Idade", retencao: "% do novo"},
  format: {ano_modelo: (a) => (a == null ? "zero km" : String(a)), preco: brl, idade: (x) => anos(x), retencao: pctInt},
  layout: "auto",
  rows: 16
}));
```
