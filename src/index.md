---
toc: false
---

# Curvas de depreciação

<p class="lede">Quanto um carro perde de valor por ano no Brasil? A Tabela FIPE é consultada em tempo de build para ${familias.length} modelos populares. Para cada modelo, os preços de todos os anos-modelo no mês mais recente mostram a curva de depreciação. O mesmo carro também é acompanhado ano a ano desde o lançamento.</p>

```js
import {brlCompact, mesAno, num, pct, pctInt, rows} from "./components/format.js";
import {palette} from "./components/palette.js";
import {hbars, meter, miniColumns, miniStrip} from "./components/charts.js";

const familias = rows(await FileAttachment("data/familias.parquet").parquet());
const grupos = rows(await FileAttachment("data/grupos.parquet").parquet());
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
const curvaHref = (nome) => `./curvas#${encodeURIComponent(nome)}`;

// Headline: the typical car's curve among every model's.
const IDADE_MAX = 8;
const curva = (b, c) => d3.range(0, IDADE_MAX + 0.01, 0.25).map((t) => ({idade: t, retencao: Math.exp(b * t - c)}));
const curvas = familias.flatMap((f) => curva(f.b_idade, f.b_novo_efetivo).map((d) => ({...d, familia: f.familia})));
const tipica = curva(mediana("b_idade"), mediana("b_novo_efetivo"));
const tipica5 = tipica.find((d) => d.idade === 5);
const destaques = [
  {f: melhor, cor: cores.categorical[2]},
  {f: pior, cor: cores.categorical[1]}
].map(({f, cor}) => ({cor, nome: f.familia, linha: curvas.filter((d) => d.familia === f.familia)}));
const MIN_SERIES = 5;
const porSegmento = grupos.filter((d) => d.dimensao === "Segmento" && d.n_series >= MIN_SERIES);
```

<div class="card hero">
  <h2 class="hero-title">Na mediana, um carro perde ${pct(saida?.perda_mediana)} do valor ao sair da loja e ${pct(mediana("taxa_anual"))} a cada ano depois. Em 5 anos, sobra ${pctInt(mediana("retencao_5"))} do preço de novo.</h2>
  <div class="hero-grid">
    <div>
      ${resize((width) => Plot.plot({
        width,
        height: Math.min(380, Math.max(260, width * 0.6)),
        marginRight: width < 500 ? 12 : 90,
        x: {label: "Idade (anos) →", domain: [0, IDADE_MAX], ticks: IDADE_MAX},
        y: {label: "↑ Fração do preço de novo", tickFormat: "%", domain: [0, 1.02], grid: true},
        marks: [
          Plot.line(curvas, {x: "idade", y: "retencao", z: "familia", stroke: cores.muted, strokeOpacity: 0.35, strokeWidth: 1}),
          ...destaques.flatMap(({linha, cor, nome}) => [
            Plot.line(linha, {x: "idade", y: "retencao", stroke: cor, strokeWidth: 2}),
            width < 500 ? null : Plot.text(linha, Plot.selectLast({x: "idade", y: "retencao", text: () => nome, dx: 6, textAnchor: "start", fill: cor, fontSize: 11}))
          ]),
          Plot.line(tipica, {x: "idade", y: "retencao", stroke: cores.accent, strokeWidth: 3}),
          width < 500 ? null : Plot.text(tipica, Plot.selectLast({x: "idade", y: "retencao", text: () => "Mediana", dx: 6, textAnchor: "start", fill: cores.accent, fontSize: 11, fontWeight: 600})),
          Plot.dot([tipica5], {x: "idade", y: "retencao", r: 5, fill: cores.accent, stroke: "var(--theme-background-alt)", strokeWidth: 2}),
          Plot.text([tipica5], {x: "idade", y: "retencao", text: (d) => `${pctInt(d.retencao)} após 5 anos`, dy: -14, fill: "currentColor", fontSize: 11, stroke: "var(--theme-background-alt)", strokeWidth: 3, paintOrder: "stroke"}),
          Plot.tip(curvas, Plot.pointer({x: "idade", y: "retencao", title: (d) => `${d.familia}\n${pctInt(d.retencao)} do preço de novo com ${num(d.idade)} anos`}))
        ]
      }))}
      <div class="legend-row">${[
        [cores.accent, "Mediana dos modelos"],
        [cores.categorical[2], `${melhor.familia}, o que mais retém`],
        [cores.categorical[1], `${pior.familia}, o que menos retém`],
        [cores.muted, "Demais modelos"]
      ].map(([cor, nome]) => html`<span><i class="line" style=${{color: cor}}></i>${nome}</span>`)}</div>
    </div>
    <div>
      <h3>Quanto sobra em 5 anos, por segmento</h3>
      ${resize((width) => hbars(porSegmento, {width, y: "grupo", x: "retencao_5", fill: cores.accent, format: pctInt, maxMargin: 90, xMax: 1, channels: {Versões: "n_series"}}))}
      <p class="muted small">O modelo ajustado juntando todas as versões de cada segmento (com ${MIN_SERIES} versões ou mais). <a href="./fatores">O que explica a depreciação →</a></p>
    </div>
  </div>
</div>

```js
// Mini-chart data for the cards: how the models spread, in 1-point bins.
function distribuicao(campo) {
  const valores = familias.map((d) => d[campo]).filter((v) => v != null);
  const bins = d3.bin().thresholds(d3.range(0, 0.3, 0.01))(valores).filter((b) => b.x0 < d3.max(valores));
  const m = d3.median(valores);
  return {m, bins: bins.map((b) => ({x0: b.x0, x1: b.x1, n: b.length, mediana: m >= b.x0 && m < b.x1}))};
}
const distTaxa = distribuicao("taxa_anual");
const distSaida = distribuicao("perda_imediata");
// A card whose link depends on data must be built in JS: Markdown can't put ${} in an attribute.
const cartaoModelo = (titulo, f) => html`<a class="card card-link" href=${curvaHref(f.familia)}>
  <h2>${titulo}</h2>
  <span class="big">${f.familia}</span>
  ${meter(f.retencao_5, cores, `${pctInt(f.retencao_5)} do preço de novo`)}
  <p class="muted">${pctInt(f.retencao_5)} do preço de novo após 5 anos (${f.marca}, ${f.segmento})</p>
  ${resize((width) => miniStrip(familias, {width, x: "retencao_5", pal: cores, format: pctInt, highlight: (d) => d === f, title: (d) => `${d.familia}: ${pctInt(d.retencao_5)}`}))}
  <p class="muted small">Retenção em 5 anos dos ${familias.length} modelos; em azul, ${f.familia}</p>
</a>`;
const titulo = (d) => `${pctInt(d.x0)}–${pctInt(d.x1)}: ${d.n} ${d.n === 1 ? "modelo" : "modelos"}`;
```

<div class="grid grid-cols-4">
  <a class="card card-link" href="./ranking">
    <h2>Depreciação anual típica</h2>
    <span class="big">${pct(mediana("taxa_anual"))}</span>
    <p class="muted">mediana dos ${familias.length} modelos, para carros usados</p>
    ${resize((width) => miniColumns(distTaxa.bins, {width, x: "x0", y: "n", pal: cores, highlight: (d) => d.mediana, title: titulo}))}
    <p class="muted small">Quantos modelos perdem cada % ao ano; em azul, a faixa da mediana</p>
  </a>
  <a class="card card-link" href="./curvas">
    <h2>Ao sair da loja</h2>
    <span class="big">${pct(saida?.perda_mediana)}</span>
    <p class="muted">diferença mediana entre o zero km e o seminovo mais novo da mesma versão</p>
    ${resize((width) => miniColumns(distSaida.bins, {width, x: "x0", y: "n", pal: cores, highlight: (d) => d.mediana, title: titulo}))}
    <p class="muted small">A mesma distribuição para a perda na saída da loja</p>
  </a>
  ${cartaoModelo("Retém mais valor", melhor)}
  ${cartaoModelo("Retém menos valor", pior)}
</div>

## Quanto do preço de novo sobra depois de 5 anos

<p class="muted">Estimativa do modelo para um carro comprado zero km e vendido 5 anos depois, a preços da FIPE de ${mesAno(qualidade.referencia.mes)}. Clique num modelo para ver a curva dele. A ordem e a metodologia completas estão no <a href="./ranking">ranking</a>.</p>

```js
const segmentos = ["Hatch", "Sedã", "SUV", "Picape", "Minivan", "Esportivo"];
const segmento = view(Inputs.radio(["Todos", ...segmentos.filter((s) => familias.some((d) => d.segmento === s))], {label: "Segmento", value: "Todos"}));
```

```js
const visiveis = porRetencao.filter((d) => segmento === "Todos" || d.segmento === segmento);
const CATEGORIAS = ["Generalista", "Premium"];
const corCategoria = {domain: CATEGORIAS, range: [cores.accent, cores.categorical[6]]};
```

<div class="card">
  <h2>Retenção em 5 anos${segmento === "Todos" ? "" : ` — ${segmento}`}</h2>
  <h3>Cada ponto é um modelo, na cor da categoria da marca; a haste mostra a distância até a mediana de todos os modelos (tracejado)</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 22 * visiveis.length + 60,
    marginLeft: 100,
    marginRight: 44,
    marginTop: 40,
    insetLeft: 30,
    x: {tickFormat: "%", label: "Retenção em 5 anos →", grid: true, axis: "top", nice: true, ticks: width < 500 ? 4 : 8},
    y: {domain: visiveis.map((d) => d.familia), label: null, tickSize: 0},
    color: {...corCategoria, legend: true},
    marks: [
      Plot.ruleY(visiveis, {y: "familia", x1: mediana("retencao_5"), x2: "retencao_5", stroke: "currentColor", strokeOpacity: 0.25, strokeWidth: 2}),
      Plot.ruleX([mediana("retencao_5")], {stroke: "currentColor", strokeOpacity: 0.7, strokeDasharray: "4,3"}),
      Plot.text([mediana("retencao_5")], {x: (d) => d, frameAnchor: "bottom", dy: 14, textAnchor: "middle", text: (d) => `mediana: ${pctInt(d)}`, fill: "currentColor", fontSize: 11}),
      Plot.dot(visiveis, {
        y: "familia",
        x: "retencao_5",
        r: 5,
        fill: "categoria",
        stroke: "var(--theme-background-alt)",
        strokeWidth: 2,
        href: (d) => curvaHref(d.familia),
        channels: {Marca: "marca", Segmento: "segmento", "Depreciação anual": (d) => pct(d.taxa_anual), "Preço de novo (mediana)": (d) => brlCompact(d.preco_novo_mediano)},
        tip: {format: {x: (x) => pctInt(x), y: true, fill: false}}
      }),
      ...[["start", 10, (d) => d.retencao_5 >= mediana("retencao_5")], ["end", -10, (d) => d.retencao_5 < mediana("retencao_5")]].map(([textAnchor, dx, lado]) =>
        Plot.text(visiveis.filter(lado), {y: "familia", x: "retencao_5", text: (d) => pctInt(d.retencao_5), dx, textAnchor, fill: "currentColor", fontSize: 11})
      )
    ]
  }))}
</div>

## Em que idade o carro mais perde valor

```js
const porIdade = geral.filter((d) => d.idade <= 10);
```

<div class="card">
  <h2>Perda mediana em cada ano de vida</h2>
  <h3>Em laranja, a perda imediata (zero km × seminovo mais novo da mesma versão); em azul, anos-modelo vizinhos (Y × Y−1) da mesma versão</h3>
  ${resize((width) => Plot.plot({
    width,
    height: 260,
    marginTop: 24,
    x: {label: "Idade (anos)", tickFormat: (d) => (d === -1 ? "0 km" : width < 520 ? String(d) : `${d}→${d + 1}`), type: "band", padding: 0.15},
    y: {axis: null},
    marks: [
      Plot.barY(porIdade, {
        x: "idade",
        y: "perda_mediana",
        fill: (d) => (d.idade === -1 ? cores.categorical[1] : cores.accent),
        ry1: 3,
        channels: {Pares: "n_pares"},
        tip: {format: {y: (y) => pct(y), x: (x) => (x === -1 ? "zero km → seminovo" : `${x} → ${x + 1} anos`), fill: false}}
      }),
      Plot.text(porIdade, {x: "idade", y: "perda_mediana", text: (d) => pct(d.perda_mediana), dy: -8, lineAnchor: "bottom", fill: "currentColor", fontSize: width < 520 ? 9 : 11}),
      Plot.ruleY([0], {strokeOpacity: 0.4})
    ]
  }))}
  <p class="muted small">Os detalhes de cada modelo estão em <a href="./curvas">Curva por modelo</a>.</p>
</div>

<div class="grid grid-cols-3">
  <a class="card card-link" href="./curvas">
    <h2>Curva por modelo</h2>
    <p>Escolha um modelo, veja a curva ajustada e os preços de cada versão, e descubra a idade em que a perda anual se estabiliza.</p>
  </a>
  <a class="card card-link" href="./fatores">
    <h2>O que explica a depreciação</h2>
    <p>Segmento, marca, câmbio automático ou automatizado, turbo, combustível e faixa de preço.</p>
  </a>
  <a class="card card-link" href="./tempo">
    <h2>Ao longo do tempo</h2>
    <p>O mesmo carro de janeiro a janeiro: o boom dos usados em 2021–22 e os preços em termos reais (IPCA).</p>
  </a>
</div>

<p class="muted small">Dados gerados em ${new Date(qualidade.gerado_em).toLocaleString("pt-BR")}.</p>
