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
  head: [
    // The site is dark-only (see src/style.css).
    '<meta name="color-scheme" content="dark">',
    '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚗</text></svg>">',
    '<link rel="preconnect" href="https://fonts.googleapis.com">',
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap">',
    // Framework's chrome is English-only and built in JS (search box, search
    // result count, sidebar toggle tooltip); translate it once the page parses.
    // The pager labels are CSS and live in src/style.css.
    `<script type="module">
const busca = document.querySelector("#observablehq-search input");
if (busca) busca.placeholder = "Buscar";
const resultados = document.querySelector("#observablehq-search-results");
if (resultados) {
  new MutationObserver(() => {
    const el = resultados.querySelector(":scope > div");
    const n = el && /^([\\d,]+) results?$/.exec(el.textContent);
    if (el?.textContent === "no results") el.textContent = "nenhum resultado";
    else if (n) {
      const k = +n[1].replaceAll(",", "");
      el.textContent = k.toLocaleString("pt-BR") + (k === 1 ? " resultado" : " resultados");
    }
  }).observe(resultados, {childList: true});
}
addEventListener("load", () => {
  for (const el of document.querySelectorAll("#observablehq-sidebar-toggle, label[for='observablehq-sidebar-toggle']")) {
    el.title = el.title.replace("Toggle sidebar", "Mostrar/ocultar menu");
  }
});
</script>`
  ].join("\n"),
  // Theme imports + typography live in src/style.css.
  style: "style.css",
  footer: "Dados: Tabela FIPE (veiculos.fipe.org.br) e IPCA (Banco Central, SGS 433). Processados em tempo de build com Polars + DuckDB.",
  toc: {label: "Nesta página"},
  search: true,
  // Python loaders run inside the uv-managed environment, so `import pipeline`
  // works and nobody needs a global Python setup. `-X utf8` keeps stderr logs
  // with accents from crashing on Windows consoles.
  interpreters: {
    ".py": ["uv", "run", "--quiet", "python", "-X", "utf8"]
  }
};
