---
title: Consulta SQL
---

# Consulta SQL no navegador

Os arquivos Parquet que alimentam o site são carregados num **DuckDB rodando no seu navegador** (DuckDB-WASM). Nada é enviado a servidor algum. Use para fazer as suas próprias comparações.

```js
const db = DuckDBClient.of({
  precos: FileAttachment("data/precos.parquet"),
  versoes: FileAttachment("data/versoes.parquet"),
  familias: FileAttachment("data/familias.parquet"),
  grupos: FileAttachment("data/grupos.parquet"),
  perdas: FileAttachment("data/perdas.parquet"),
  tempo: FileAttachment("data/tempo.parquet")
});
```

```js
const exemplos = new Map([
  ["Seminovos de 3 anos mais baratos em relação ao novo", `WITH atual AS (SELECT * FROM precos WHERE mes = (SELECT max(mes) FROM precos))
SELECT a.familia, v.versao, a.ano_modelo, round(a.preco) AS preco,
       round(a.preco_novo_est) AS novo_estimado, round(a.retencao, 3) AS retencao
FROM atual a JOIN versoes v USING (modelo_code, combustivel_code)
WHERE NOT a.zero_km AND a.idade BETWEEN 2.5 AND 3.5
ORDER BY retencao
LIMIT 20`],
  ["Depreciação por modelo, só SUVs", `SELECT familia, marca,
       round(100 * taxa_anual, 1)     AS deprec_ano_pct,
       round(100 * perda_imediata, 1) AS saida_loja_pct,
       round(100 * retencao_5)        AS retem_5_anos_pct
FROM familias
WHERE segmento = 'SUV'
ORDER BY deprec_ano_pct`],
  ["Automático × manual dentro do mesmo modelo", `WITH atual AS (
  SELECT p.familia, v.cambio, p.retencao
  FROM precos p JOIN versoes v USING (modelo_code, combustivel_code)
  WHERE p.mes = (SELECT max(mes) FROM precos) AND NOT p.zero_km
), mistos AS (
  SELECT familia FROM atual GROUP BY familia HAVING count(DISTINCT cambio) > 1
)
SELECT familia, cambio, count(*) AS precos, round(median(retencao), 3) AS retencao_mediana
FROM atual JOIN mistos USING (familia)
GROUP BY ALL
ORDER BY familia, cambio`],
  ["Preço de um carro em cada janeiro", `SELECT familia, ano_modelo, strftime(mes, '%Y-%m') AS tabela, round(preco) AS nominal, round(preco_real) AS real
FROM precos
WHERE familia = 'Onix' AND rank = 0
  AND ano_modelo = (SELECT min(ano_modelo) + 1 FROM precos WHERE familia = 'Onix' AND rank = 0)
ORDER BY mes`]
]);
const exemplo = view(Inputs.select(exemplos, {label: "Exemplo"}));
```

```js
const consulta = view(Inputs.textarea({value: exemplo, rows: 10, submit: "Executar", spellcheck: false, monospace: true, width: "100%"}));
```

```js
// DuckDB returns BIGINT/HUGEINT (e.g. count(*)) as JavaScript BigInt; convert to
// Number so formatting and charts work.
const resultado = await db.query(consulta).then(
  (r) => ({rows: Array.from(r, (row) => Object.fromEntries(Object.entries(row).map(([k, v]) => [k, typeof v === "bigint" ? Number(v) : v])))}),
  (error) => ({error})
);
```

${resultado.error ? html`<div class="caution"><strong>Erro:</strong> <code>${resultado.error.message}</code></div>` : html`<p class="muted">${resultado.rows.length.toLocaleString("pt-BR")} linhas</p>`}

```js
resultado.error ? null : Inputs.table(resultado.rows, {rows: 20, locale: "pt-BR"})
```

## Tabelas disponíveis

```js
const esquema = await Promise.all(
  ["precos", "versoes", "familias", "grupos", "perdas", "tempo"].map(async (t) => ({
    tabela: t,
    linhas: Number(Array.from(await db.query(`SELECT count(*) AS n FROM ${t}`))[0].n),
    colunas: Array.from(await db.query(`DESCRIBE ${t}`), (c) => `${c.column_name} (${c.column_type.toLowerCase()})`).join(", ")
  }))
);
```

```js
Inputs.table(esquema, {format: {linhas: (n) => n.toLocaleString("pt-BR")}, width: {tabela: 110, linhas: 90}, layout: "auto"})
```

<div class="tip">Uma <em>série</em> é uma versão FIPE com um combustível: <code>modelo_code</code> + <code>combustivel_code</code>. Em <code>precos</code>, zero km tem <code>zero_km = true</code> e <code>ano_modelo</code> nulo. <code>rank = 0</code> marca a versão principal de cada modelo, a única com histórico em todo janeiro. <code>retencao</code> só é preenchida para a tabela mais recente.</div>
