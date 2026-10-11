import * as d3 from "npm:d3";

// Brazilian number conventions: "." for thousands, "," for decimals, "R$ " prefix.
export const locale = d3.formatLocale({
  decimal: ",",
  thousands: ".",
  grouping: [3],
  currency: ["R$ ", ""]
});

const int = locale.format(",.0f");
const dec1 = locale.format(",.1~f"); // "1,5" but "20", not "20,0"
const pct0 = locale.format(".0%");
const pct1 = locale.format(".1%");
const sign1 = locale.format("+.1%");

const missing = (x) => x == null || Number.isNaN(x);

export const num = (x) => (missing(x) ? "–" : int(x));
export const pct = (x) => (missing(x) ? "–" : pct1(x));
export const pctInt = (x) => (missing(x) ? "–" : pct0(x));
export const pctSigned = (x) => (missing(x) ? "–" : sign1(x));
export const brl = (x) => (missing(x) ? "–" : `R$ ${int(x)}`);
export const anos = (x) => (missing(x) ? "–" : `${dec1(x)} ${Math.abs(x) === 1 ? "ano" : "anos"}`);

/** Compact BRL: R$ 1,2 mi · R$ 85 mil */
export function brlCompact(x) {
  if (missing(x)) return "–";
  const a = Math.abs(x);
  if (a >= 1e6) return `R$ ${dec1(x / 1e6)} mi`;
  if (a >= 1e3) return `R$ ${int(x / 1e3)} mil`;
  return `R$ ${int(x)}`;
}

export const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** Date (or ms) of a reference month -> "out/2026". */
export function mesAno(d) {
  const date = new Date(d);
  return `${MESES[date.getUTCMonth()]}/${date.getUTCFullYear()}`;
}

/** Arrow table -> array of plain objects (Plot/D3 want plain objects). */
export function rows(table) {
  return Array.from(table, (r) => r.toJSON());
}
