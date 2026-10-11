---
toc: false
---

# Curvas de depreciação

<p class="lede">Quanto um carro perde de valor por ano no Brasil? A Tabela FIPE é consultada em tempo de build para ${familias.length} modelos populares. Para cada modelo, os preços de todos os anos-modelo no mês mais recente mostram a curva de depreciação. O mesmo carro também é acompanhado ano a ano desde o lançamento.</p>

```js
import {anos, brlCompact, mesAno, num, pct, pctInt, rows} from "./components/format.js";
import {palette} from "./components/palette.js";

const familias = rows(await FileAttachment("data/familias.parquet").parquet());
const perdas = rows(await FileAttachment("data/perdas.parquet").parquet());
const qualidade = FileAttachment("data/qualidade.json").json();
```

```js
const cores = palette(dark);
const mediana = (k) => d3.median(familias, (d) => d[k]);
const porRetencao = d3.sort(familias, (d) => -d.retencao_5);
const melhor = porRetencao[0];
const pior = porRetencao.at(-1);
const geral = perdas.filter((d) => d.nivel === "todos");
const saida = geral.find((d) => d.idade === -1);
```

<div class="grid grid-cols-4">
  <div class="card">
    <h2>Depreciação anual típica</h2>
    <span class="big">${pct(mediana("taxa_anual"))}</span>
    <p class="muted">mediana dos ${familias.length} modelos, para carros usados</p>
  </div>
  <div class="card">
    <h2>Ao sair da loja</h2>
    <span class="big">${pct(saida?.perda_mediana)}</span>
    <p class="muted">diferença mediana entre o zero km e o seminovo mais novo da mesma versão</p>
  </div>
  <div class="card">
    <h2>Retém mais valor</h2>
    <span class="big">${melhor.familia}</span>
    <p class="muted">${pctInt(melhor.retencao_5)} do preço de novo após 5 anos (${melhor.marca})</p>
  </div>
  <div class="card">
    <h2>Retém menos valor</h2>
    <span class="big">${pior.familia}</span>
    <p class="muted">${pctInt(pior.retencao_5)} do preço de novo após 5 anos (${pior.marca})</p>
  </div>
</div>

## Quanto do preço de novo sobra depois de 5 anos

<p class="muted">Estimativa do modelo para um carro comprado zero km e vendido 5 anos depois, a preços da FIPE de ${mesAno(qualidade.referencia.mes)}. Passe o mouse para ver os detalhes. A ordem e a metodologia completas estão no <a href="./ranking">ranking</a>.</p>

```js
const segmentos = ["Hatch", "Sedã", "SUV", "Picape", "Minivan"];
const segmento = view(Inputs.radio(["Todos", ...segmentos.filter((s) => familias.some((d) => d.segmento === s))], {label: "Segmento", value: "Todos"}));
```

```js
const visiveis = porRetencao.filter((d) => segmento === "Todos" || d.segmento === segmento);
display(Plot.plot({
  width,
  height: 18 * visiveis.length + 40,
  marginLeft: 110,
  x: {domain: [0, 1], tickFormat: "%", label: "Retenção em 5 anos →", grid: true},
  y: {domain: visiveis.map((d) => d.familia), label: null},
  marks: [
    Plot.ruleY(visiveis, {y: "familia", x1: 0, x2: "retencao_5", stroke: cores.muted, strokeWidth: 1}),
    Plot.dot(visiveis, {
      y: "familia",
      x: "retencao_5",
      r: 5,
      fill: cores.accent,
      stroke: "var(--theme-background)",
      strokeWidth: 2,
      channels: {Marca: "marca", Segmento: "segmento", "Depreciação anual": (d) => pct(d.taxa_anual), "Preço de novo (mediana)": (d) => brlCompact(d.preco_novo_mediano)},
      tip: {format: {x: (x) => pctInt(x), y: true}}
    }),
    Plot.text(visiveis, {y: "familia", x: "retencao_5", text: (d) => pctInt(d.retencao_5), dx: 10, textAnchor: "start", fill: "var(--theme-foreground-muted)", fontSize: 10})
  ]
}));
```

## Em que idade o carro mais perde valor

```js
display(Plot.plot({
  width,
  height: 260,
  x: {label: "Idade (anos)", tickFormat: (d) => (d === -1 ? "0 km" : `${d}→${d + 1}`), type: "band"},
  y: {label: "↑ Perda no ano (mediana)", tickFormat: "%", grid: true},
  marks: [
    Plot.barY(geral.filter((d) => d.idade <= 10), {
      x: "idade",
      y: "perda_mediana",
      fill: (d) => (d.idade === -1 ? cores.categorical[1] : cores.accent),
      inset: 1,
      rx: 2,
      channels: {Pares: "n_pares"},
      tip: {format: {y: (y) => pct(y), x: (x) => (x === -1 ? "zero km → seminovo" : `${x} → ${x + 1} anos`), fill: false}}
    }),
    Plot.ruleY([0])
  ]
}));
```

<p class="muted small">A primeira barra (laranja) é a perda imediata: zero km contra o seminovo mais novo da mesma versão. As demais barras comparam anos-modelo vizinhos (Y contra Y−1) da mesma versão. Os detalhes de cada modelo estão em <a href="./curvas">Curva por modelo</a>.</p>

<div class="grid grid-cols-3">
  <a class="card card-link" href="./curvas">
    <h3>Curva por modelo</h3>
    <p>Escolha um modelo, veja a curva ajustada e os preços de cada versão, e descubra a idade em que a perda anual se estabiliza.</p>
  </a>
  <a class="card card-link" href="./fatores">
    <h3>O que explica a depreciação</h3>
    <p>Segmento, marca, câmbio automático ou automatizado, turbo, combustível e faixa de preço.</p>
  </a>
  <a class="card card-link" href="./tempo">
    <h3>Ao longo do tempo</h3>
    <p>O mesmo carro de janeiro a janeiro: o boom dos usados em 2021–22 e os preços em termos reais (IPCA).</p>
  </a>
</div>

<p class="muted small">Dados gerados em ${new Date(qualidade.gerado_em).toLocaleString("pt-BR")}.</p>

<style>
.lede { font-size: 1.15rem; max-width: 52rem; color: var(--theme-foreground-muted); }
.card-link { text-decoration: none; color: inherit; transition: border-color 150ms; }
.card-link:hover { border-color: var(--theme-foreground-focus); }
.small { font-size: 0.85rem; }
</style>
