import * as Plot from "npm:@observablehq/plot";
import {html} from "npm:htl";
import {pct} from "./format.js";

/** Cut a label to `n` characters with an ellipsis (the tooltip keeps the full text). */
export function truncate(text, n) {
  const s = String(text ?? "");
  return s.length > n ? `${s.slice(0, Math.max(1, n - 1)).trimEnd()}…` : s;
}

/** Left margin for bar labels: up to `max`, and at most ~45 % of a narrow chart. */
export function labelMargin(width, max = 200) {
  return Math.round(Math.max(72, Math.min(max, width * 0.45)));
}

/**
 * Horizontal bars with the value printed at the end of each bar instead of an
 * x axis. Labels on the left are truncated to fit the (responsive) margin.
 *
 * @param data  array of objects
 * @param opts  {width, y: field or accessor, x: field, fill: colour or accessor,
 *               format: value -> label text, sort: "desc" | "asc" | null (keep
 *               the given order), limit: keep the first N, xMax: shared domain
 *               end (so side-by-side charts compare), href, maxMargin, channels}
 */
export function hbars(data, {width, y, x = "valor", fill, format = pct, sort = "desc", limit, xMax, href, maxMargin = 200, channels} = {}) {
  const yOf = typeof y === "function" ? y : (d) => d[y];
  let rows = data.filter((d) => d[x] != null);
  if (sort) rows = rows.sort((a, b) => (sort === "asc" ? a[x] - b[x] : b[x] - a[x]));
  rows = rows.slice(0, limit ?? Infinity);
  const marginLeft = labelMargin(width, maxMargin);
  const chars = Math.floor((marginLeft - 8) / 5.6); // ~5.6 px per character at Plot's 10px
  return Plot.plot({
    width,
    height: rows.length * 26 + 12,
    marginLeft,
    marginRight: 56,
    marginTop: 4,
    marginBottom: 4,
    x: {axis: null, ...(xMax ? {domain: [0, xMax]} : {})},
    y: {label: null, tickSize: 0, tickFormat: (d) => truncate(d, chars), domain: rows.map(yOf)},
    marks: [
      Plot.barX(rows, {y: yOf, x, fill, href, channels, rx2: 4, insetTop: 3, insetBottom: 3, tip: {format: {x: format, fill: false}}}),
      Plot.text(rows, {y: yOf, x, text: (d) => format(d[x]), dx: 5, textAnchor: "start", fill: "currentColor", fontSize: 11}),
      Plot.ruleX([0], {strokeOpacity: 0.4})
    ]
  });
}

/**
 * Compact chart for a stat tile: no axes, a hover tooltip, the de-emphasis hue
 * with the `highlight(d)` items in `highlightColor` (the accent by default).
 */
export function miniColumns(data, {width, x, y, highlight = () => false, highlightColor, pal, title, height = 64}) {
  return Plot.plot({
    width,
    height,
    margin: 0,
    marginTop: 4,
    x: {axis: null, type: "band", padding: 0.2},
    y: {axis: null},
    marks: [
      Plot.barY(data, {x, y, fill: (d) => (highlight(d) ? highlightColor ?? pal.accent : pal.muted), ry1: 2, tip: false}),
      Plot.tip(data, Plot.pointerX({x, y, title}))
    ]
  });
}

/**
 * Compact strip for a stat tile: one tick per item along x, in the de-emphasis
 * hue, with the `highlight(d)` items taller and in the accent.
 */
export function miniStrip(data, {width, x, highlight = () => false, pal, title, format, height = 64}) {
  const marcado = data.filter(highlight);
  return Plot.plot({
    width,
    height,
    marginTop: 8,
    marginLeft: 8,
    marginRight: 8,
    marginBottom: 18,
    x: {nice: true, tickFormat: format, ticks: 4, tickSize: 0, label: null},
    y: {axis: null},
    marks: [
      Plot.tickX(data, {x, stroke: pal.muted, strokeWidth: 1.5, insetTop: 12, insetBottom: 12}),
      Plot.tickX(marcado, {x, stroke: pal.accent, strokeWidth: 3}),
      Plot.tip(data, Plot.pointerX({x, title}))
    ]
  });
}

/** Horizontal meter for a share in [0, 1]: accent fill on a lighter step of the same ramp. */
export function meter(frac, pal, title) {
  return html`<div class="meter" style=${{background: pal.blues(7)[0]}} title=${title ?? ""}><div style=${{width: `${Math.max(2, Math.min(1, frac) * 100)}%`, background: pal.accent}}></div></div>`;
}

/**
 * Shaded band + label for a period on the x axis ([x1, x2] in the chart's x
 * units). Pair with `y: {insetTop: 22}` so the label sits above the data.
 */
export function periodoMarks([x1, x2], label) {
  return [
    Plot.rectX([{x1, x2}], {x1: "x1", x2: "x2", fill: "currentColor", fillOpacity: 0.07}),
    Plot.text([{x1, x2}], {x: (d) => d.x1, text: () => label, frameAnchor: "top", textAnchor: "start", dx: 4, fill: "currentColor", fillOpacity: 0.8, fontSize: 11})
  ];
}

/** Label one point (with a halo, so it reads over grid lines and other marks). */
export function rotuloMark(d, {x, y, text, dx = 0, dy = -10, textAnchor = "middle", lineAnchor = "bottom"}) {
  if (!d) return null;
  return Plot.text([d], {
    x,
    y,
    text,
    dx,
    dy,
    textAnchor,
    lineAnchor,
    fill: "currentColor",
    fontSize: 11,
    stroke: "var(--theme-background-alt)",
    strokeWidth: 3,
    paintOrder: "stroke"
  });
}
