// See https://observablehq.com/framework/config for documentation.
export default {
  title: "Curvas de depreciação",
  root: "src",
  lang: "pt-BR",
  pages: [
    {name: "Curva por modelo", path: "/curvas"},
    {name: "Ranking", path: "/ranking"},
    {name: "O que explica a depreciação", path: "/fatores"},
    {name: "Ao longo do tempo", path: "/tempo"},
    {name: "Consulta SQL", path: "/sql"},
    {name: "Sobre os dados", path: "/sobre"}
  ],
  head: '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚗</text></svg>">',
  theme: ["air", "near-midnight", "alt", "wide"],
  footer: "Dados: Tabela FIPE (veiculos.fipe.org.br) e IPCA (Banco Central, SGS 433). Processados em tempo de build com Polars + DuckDB.",
  toc: true,
  search: true,
  // Python loaders run inside the uv-managed environment, so `import pipeline`
  // works and nobody needs a global Python setup. `-X utf8` keeps stderr logs
  // with accents from crashing on Windows consoles.
  interpreters: {
    ".py": ["uv", "run", "--quiet", "python", "-X", "utf8"]
  }
};
