# Curvas de depreciação

A static data site about **how fast cars lose value in Brazil**, built from the **Tabela FIPE** with a Python pipeline (**Polars**) and **Observable Framework** (Observable Plot for charts, DuckDB-WASM for in-browser SQL). Prices are deflated with the **IPCA** from the Banco Central.

Every API call happens **at build time** in Framework data loaders. The browser only downloads pre-cleaned Parquet/JSON files.

| Page | What it shows |
|---|---|
| Início | Typical annual depreciation, loss when leaving the dealership, 5-year retention of every model, loss by year of age |
| Curva por modelo | One model: fitted curve vs. every version × model year, comparison with up to 3 others, the age where yearly losses flatten out ("sweet spot"), price table |
| Ranking | Models ranked by 5-year retention, annual depreciation or dealership loss, plus the method |
| O que explica a depreciação | The same model pooled by transmission (manual / automatic / *automated manual*), segment, price band, fuel, turbo, brand |
| Ao longo do tempo | The same car followed January to January: the 2021–22 used-car boom, nominal vs. real (IPCA), "follow a car" |
| Consulta SQL | Free-form SQL over all Parquet files with DuckDB-WASM |
| Sobre os dados | Sources, sample design, cleaning, name matching, model and limitations |

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/) and Node.js ≥ 18. No API key needed.

```bash
uv sync          # Python env (polars, duckdb, httpx, pyarrow, pytest)
npm install      # Observable Framework
npm run dev      # http://127.0.0.1:3000
npm run build    # static site in dist/
```

To try it in ~10 minutes, limit the models first: `CDC_FAMILIAS="Onix,HB20,Gol,Corolla" npm run dev` (bash). Run `npm run clean` before switching back to the full set.

**The full first build takes about 2 hours.** It makes ~5,300 price requests, and FIPE answers *429 Too Many Requests* above roughly 45 per minute. Every response is cached in `data_cache/` (git-ignored). A price for a past month never changes, so it is cached forever: an interrupted build resumes where it stopped, and later builds only fetch the new month (~1,800 requests).

Knobs (environment variables):

| Variable | Default | Effect |
|---|---|---|
| `CDC_FAMILIAS` | *(all)* | Comma-separated models for a quick partial build, e.g. `Onix,HB20,Gol,Corolla` (~10 min). Names as in `pipeline/catalogo.py` |
| `CDC_VERSOES` | `4` | Versions per model priced in the current table. Lower = faster builds, noisier curves |
| `CDC_ANO_MIN` | `2014` | Oldest model year (and first January of the history) |
| `FIPE_RPM` | `90` | Starting request rate. The limiter slows down on every 429 and speeds back up after 50 successes |
| `CDC_CACHE_DIR` | `data_cache` | Where raw responses and frames are cached |

## Data source

The JSON endpoints behind FIPE's own consultation page (`https://veiculos.fipe.org.br/api/veiculos/…`, form POSTs, no key). They serve every monthly table since 2001. The third-party Parallelum API is easier to use, but its free tier allows 500 requests/day and paywalls price history.

| Endpoint | Used for |
|---|---|
| `ConsultarTabelaDeReferencia` | Reference months (`338` = outubro/2026) |
| `ConsultarMarcas`, `ConsultarModelos` | Brands; the (model year, fuel) codes of a brand |
| `ConsultarModelosAtravesDoAno` | **Every version of a brand in one model year + fuel**: the whole catalogue for ~1 request per (brand, year, fuel) instead of one per version |
| `ConsultarValorComTodosParametros` | One price: (month, brand, version, model year, fuel) |

## How it's organised

```
pipeline/            Python package: one module per concern
  http.py            cached GET/POST, retries, adaptive rate limiter
  clean.py           BRL prices, Portuguese month names, name normalisation, the 32000 = zero km quirk
  fipe.py            FIPE client: references, brands, catalogue, prices
  catalogo.py        90 model families, 24 brands (ordered regexes) + attributes parsed from version names
  painel.py          which prices to fetch (sample design) and the cleaned price panel (age, real prices)
  bcb.py             IPCA from SGS; deflator; 12-month IPCA
  curvas.py          the depreciation model (within estimator), retention, loss by age, year-on-year changes
  frames.py          catalogue and panel memoised as Parquet, shared across loaders
  io.py              stdout writers; casts int64 -> int32 so JS doesn't get BigInt
src/data/*.py        Framework data loaders (thin; run via `uv run`, see observablehq.config.js)
src/components/      formatting (pt-BR), palette
src/*.md             pages
tests/               offline tests: cleaning, family matching, attribute parsing, the model on synthetic data
```

## The model

For each group (a model, a segment, a transmission type…), on the latest FIPE table:

```
log(price) = a[version] + b · age + c · zero_km
```

- `a[version]`: a fixed effect per FIPE version, so a top trim is only compared with its own older model years, never with a base trim;
- **annual depreciation** = `1 − e^b`;
- **loss when leaving the dealership** = `1 − e^(−c)`;
- **retention after t years** = `e^(b·t − c)`.

It is estimated with the *within* estimator (demean per version, then a 2×2 least-squares solve), so it runs as a plain Polars aggregation. Discontinued models have no zero-km price to identify `c` and use the pooled one. The "loss by year of age" chart makes no functional assumption: it compares adjacent model years of the same version.

## Messy-data problems handled

- **No "model" field.** FIPE rows are hand-written version names (`ONIX HATCH 1.0 12V TB Flex 5p Mec.`, `ONIX  Lollapalooza 1.0 F.Power 5p Mec.`, `ONIX SED. Plus PREM. 1.0 12V TB Flex Aut`). Families come from an ordered list of regexes per brand: specific before generic (Onix Plus before Onix, Corolla Cross before Corolla, HB20S before HB20, Oroch before Duster), with negative lookaheads for Gol/Golf, Polo/Polo Sedan, Cruze/Cruze Sport6.
- **Attributes hidden in names.** Transmission: *Aut.*, CVT, DSG → automatic; Dualogic, Easytronic, I-Motion, GSR → **automated manual**; otherwise manual, since FIPE almost always flags "Aut." but often omits "Mec.". Hybrids are filed as "Gasolina" with "(Híbrido)" (or "Hibrído") in the name. Turbo appears as TB, Turbo, TSI, THP, T270…
- **Normalisation that keeps engine sizes.** Punctuation becomes spaces, but `1.0` stays `1.0`; `KA+` keeps its `+`.
- **Zero km is model year 32000.**
- **Misses are 200s.** A version/year missing from a month's table returns `{"erro": "nadaencontrado"}` with HTTP 200, so it is cached like any other answer and never re-queried.
- **Body-less POSTs fail** with *411 Length Required*. Dates come as `"outubro/2026 "` or `"outubro de 2026 "`, prices as `"R$ 60.653,00"`.
- **Undocumented rate limit.** The limiter is adaptive (AIMD-style).
- **Age.** Next year's model is sold from mid-year, which would give a negative age, so age is floored at 0.

## Refreshing data and deploying

FIPE answers **403 Forbidden** to GitHub Actions runners (datacenter IPs), so the data can't be downloaded in CI. Instead, the raw API responses in `data_cache/` (~9 MB) are committed, and the workflow builds **offline** (`CDC_OFFLINE=1`): it reads only from `data_cache/` and fails with a clear message if something is missing. *Settings → Pages → Source* must be set to **GitHub Actions**.

To publish a new month (FIPE releases it in the first days of each month):

```bash
npm run clean          # clear loader outputs and frames, keep raw responses
npm run build          # downloads only what's new (~40 min), on your machine
git add data_cache && git commit -m "Data: FIPE <month>" && git push
```

Framework caches each loader's output in `src/.observablehq/cache` and only reruns a loader when its own file changes. After changing code in `pipeline/`, run `npm run clean` (it clears Framework's loader cache and the memoised frames in `data_cache/frames`, but keeps raw API responses).

| Variable | Effect |
|---|---|
| `CDC_OFFLINE=1` | Never touch the network; serve every request from the cache regardless of age, and fail with a clear message if something is missing |

## Tests

```bash
uv run pytest
```
