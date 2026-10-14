---
title: Sobre os dados
---

# Sobre os dados

```js
import {mesAno, num, pct} from "./components/format.js";
const q = await FileAttachment("data/qualidade.json").json();
```

Este é um site estático. Os dados são baixados e limpos **em tempo de build** por *data loaders* em Python (Polars) do Observable Framework. O navegador recebe apenas arquivos Parquet/JSON prontos. Tabela FIPE usada: **${mesAno(q.referencia.mes)}**. Última geração: **${new Date(q.gerado_em).toLocaleString("pt-BR")}**.

## Fontes

| Fonte | Acesso | O que usamos |
|---|---|---|
| Tabela FIPE: endpoints JSON da consulta pública (`veiculos.fipe.org.br/api/veiculos`) | Público, sem chave, POST de formulário | Catálogo de versões × ano-modelo e preços médios de ${num(q.referencia.meses)} tabelas mensais (desde ${mesAno(q.referencia.primeira)}) |
| Banco Central: SGS, série 433 | API pública | IPCA mensal, para trazer preços a valores de hoje |

A API da Parallelum (`fipe.parallelum.com.br`) é mais cômoda, mas a versão gratuita limita a 500 requisições/dia e só mostra os últimos 3 meses de histórico. Os endpoints da própria FIPE servem qualquer mês desde 2001.

## Amostra

Precificar toda versão em todo mês exigiria centenas de milhares de requisições. A FIPE tolera cerca de 45 por minuto antes de responder *429 Too Many Requests*. Por isso a amostra é deliberada:

- **${q.catalogo.familias} modelos** de ${q.catalogo.marcas} marcas, anos-modelo a partir de **${q.parametros.ano_min}**.
- **Tabela atual:** para cada modelo, as **${q.parametros.versoes_por_familia} versões** com mais anos-modelo, em todos os anos-modelo. Versões de vida longa dão as curvas mais limpas.
- **Histórico:** a versão principal de cada modelo, em todos os anos-modelo, em todo mês de **janeiro** desde o lançamento, mais o preço de zero km nesses janeiros.

O catálogo completo das marcas custa uma requisição por (marca, ano-modelo, combustível), graças ao endpoint `ConsultarModelosAtravesDoAno`. Cada preço de um mês passado nunca muda, então fica em cache para sempre: depois do primeiro build, só o mês novo é baixado.

| | |
|---|---|
| Versões × anos-modelo nas marcas acompanhadas | ${num(q.catalogo.linhas_marcas)} (${num(q.catalogo.versoes_marcas)} versões) |
| … dos ${q.catalogo.familias} modelos | ${num(q.catalogo.linhas_familias)} (${num(q.catalogo.versoes_familias)} versões) |
| Consultas de preço | ${num(q.consultas.total)} |
| … com preço | ${num(q.consultas.com_preco)} |
| … sem preço (versão ainda ou já fora da tabela naquele mês) | ${num(q.consultas.sem_preco)} |
| Preços na tabela atual | ${num(q.painel.precos_atual)} de ${num(q.painel.series_atual)} séries |
| Preços históricos (janeiros) | ${num(q.painel.precos_historico)} |

## Limpeza

- **Zero km.** A FIPE usa o ano-modelo **32000** para "zero km". Ele vira `zero_km = true`, com idade 0.
- **Idade.** Idade = ano da tabela − ano-modelo + meses decorridos no ano. O ano-modelo seguinte, que é vendido a partir do meio do ano, daria idade negativa, por isso a idade mínima é 0.
- **Preço e mês.** `"R$ 60.653,00"` → 60653; `"outubro/2026 "` e `"outubro de 2026 "` → 2026-10-01.
- **Falta de preço.** Uma combinação que não existe naquele mês volta como `{"erro": "nadaencontrado"}` com status 200. Isso não é um erro HTTP, então essa resposta também fica em cache.
- **Limite de requisições.** O limitador começa em 90/min, desacelera 25% a cada 429 e acelera 10% a cada 50 sucessos seguidos.

## Do nome da versão ao modelo

A FIPE não tem campo de "modelo". Cada linha é uma versão escrita à mão ao longo de décadas: `ONIX HATCH 1.0 12V TB Flex 5p Aut.`, `ONIX  Lollapalooza 1.0 F.Power 5p Mec.`, `ONIX SED. Plus PREM. 1.0 12V TB Flex Aut`. O nome é normalizado (sem acentos, maiúsculas, sem pontuação, mas mantendo o ponto de `1.0`) e comparado com uma lista ordenada de padrões por marca. Os mais específicos vêm antes: *Onix Plus* antes de *Onix*, *Corolla Cross* antes de *Corolla*, *HB20S* antes de *HB20*, *Oroch* antes de *Duster*. Padrões negativos evitam *Gol* ↔ *Golf*, *Polo* ↔ *Polo Sedan* e *Cruze* ↔ *Cruze Sport6*.

Do nome também saem os atributos:

- **Câmbio.** "Aut.", CVT, DSG… viram automático. Dualogic, Easytronic, I-Motion, GSR e AMT viram **automatizado**. O resto é manual, porque a FIPE quase sempre marca "Aut." mas nem sempre marca "Mec.".
- **Combustível.** Vem do código FIPE, exceto para híbridos, que a FIPE costuma registrar como "Gasolina" com "(Híbrido)" no nome (às vezes escrito "Hibrído").
- **Turbo.** TB, Turbo, TSI, THP, T270…

<details>
<summary>Modelos das marcas acompanhadas que ficaram de fora (os ${q.catalogo.sem_familia.length} com mais versões)</summary>

```js
Inputs.table(q.catalogo.sem_familia, {header: {marca: "Marca", modelo: "Primeira palavra", versoes: "Versões"}, layout: "auto"})
```

</details>

## O modelo estatístico

Para cada grupo (um modelo, um segmento, um tipo de câmbio…), na tabela mais recente:

<p class="formula">log(preço) = a<sub>versão</sub> + b · idade + c · zero km</p>

Ele é estimado por mínimos quadrados com efeito fixo por versão (estimador *within*). Depreciação anual = 1 − e<sup>b</sup>. Perda ao sair da loja = 1 − e<sup>−c</sup>. Retenção em t anos = e<sup>b·t − c</sup>. Modelos fora de linha não identificam c e usam o c estimado com todos os modelos juntos.

A página de perda ano a ano não usa o modelo: ela compara anos-modelo vizinhos da mesma versão na mesma tabela.

## Limitações

- **Transversal ≠ longitudinal.** A curva compara o preço *hoje* de carros de idades diferentes. Um ano-modelo antigo pode ser de outra geração ou ter outro conteúdo. O efeito fixo por versão ajuda, porque a FIPE costuma criar versão nova quando o carro muda, mas não elimina o problema.
- **Preço FIPE não é preço de transação.** É uma média de anúncios e negociações pesquisada pela FIPE. Carros específicos (quilometragem, estado) variam muito.
- **Zero km.** O preço de zero km da FIPE é próximo do preço de tabela e não inclui descontos de concessionária. Por isso a "perda ao sair da loja" tende a ser superestimada.
- **Amostra.** As versões com mais anos-modelo não são necessariamente as mais vendidas: a FIPE não publica volume de vendas.
- **Elétricos e híbridos** estão no mercado há poucos anos. As curvas deles cobrem só as idades iniciais.

## Versão dos dados

Cada build publica um manifesto com a versão do código, o mês da tabela FIPE, a data de download de cada fonte e a contagem de linhas de cada tabela (no total, por ano e por modelo). Ele também é publicado em `/manifest.json`, num endereço fixo, para comparar cada atualização com a anterior: se um modelo some ou perde muitos preços, por exemplo porque a FIPE renomeou as versões dele, a publicação avisa (${html`<a href=${FileAttachment("data/manifest.json").href}>ver o arquivo</a>`}).

```js
const manifesto = await FileAttachment("data/manifest.json").json();
```

<p class="muted">Código do pipeline: <code>${manifesto.codigo_pipeline}</code>${manifesto.commit ? html` · commit <a href=${`https://github.com/davipferr/car-depreciation-curves/commit/${manifesto.commit}`}><code>${manifesto.commit.slice(0, 7)}</code></a>` : ""}</p>
