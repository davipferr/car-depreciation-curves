# Curvas de depreciação

A static data site about **how fast cars lose value in Brazil**, built from the **Tabela FIPE** with a Python pipeline (**Polars**) and **Observable Framework** (Observable Plot for charts, DuckDB-WASM for in-browser SQL). Prices are deflated with the **IPCA** from the Banco Central.

Every API call happens **at build time** in Framework data loaders. The browser only downloads pre-cleaned Parquet/JSON files.

| Page | What it shows |
|---|---|
| Início | Typical annual depreciation, loss when leaving the dealership, 5-year retention of every model, loss by year of age |
| Curva por modelo | One model: fitted curve vs. every version × model year, comparison with up to 3 others, the age where yearly losses flatten out ("sweet spot"), price table |
| Ranking | Models ranked by 5-year retention, annual depreciation or dealership loss, plus the method |
| O que explica a depreciação | The same model pooled by premium × mainstream brand, transmission (manual / automatic / *automated manual*), segment, price band, fuel, turbo, brand |
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

> **Monthly routine:** the data must be updated on your computer once a month and pushed. See [Monthly data update](#monthly-data-update).

To try it in ~10 minutes, limit the models first: `CDC_FAMILIAS="Onix,HB20,Gol,Corolla" npm run dev` (bash). Run `npm run clean` before switching back to the full set.

**A build from an empty cache takes about 2.5 hours.** It makes ~7,800 requests, and FIPE answers *429 Too Many Requests* above roughly 45 per minute. Every response is cached in `data_cache/` (committed to git, see [Monthly data update](#monthly-data-update)). An interrupted build resumes where it stopped.

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

## Monthly data update

**Fetch the data once a month, on your own computer, before pushing.** FIPE publishes one new price table per month, in its first days; until the next one comes out nothing changes. A good habit is updating around the **8th of each month**.

### Why it has to be done locally

FIPE answers **403 Forbidden** to GitHub Actions runners (datacenter IPs), so GitHub can't download anything. Instead, the downloaded API responses in `data_cache/` are committed, and the workflow builds the site **offline** (`CDC_OFFLINE=1`) from them. If a push contains no new data, the site is rebuilt with the old data.

### Commands

Run in the project folder, with your computer connected (it takes **~70 minutes**, ~85 in January):

```bash
npm run clean    # 1. delete derived files (loader outputs, data_cache/frames); downloaded data is kept
npm run build    # 2. download the new month from FIPE and build the site
uv run pytest    # 3. run the tests
git add -A       # 4. stage the new files in data_cache/
git commit -m "Data: FIPE <month>/<year>"
git push         # 5. GitHub builds the site offline and publishes it
```

Optionally, check the site before pushing with `npm run dev` (http://127.0.0.1:3000). The *Sobre os dados* page shows which FIPE month is in use.

If the build is interrupted (computer off, connection lost), just run `npm run build` again: everything already downloaded is cached, so it resumes where it stopped.

### What gets downloaded, and why only that

Each kind of data is cached for as long as it can't change, so a monthly update never re-downloads the past:

| Data | Cached for | Why |
|---|---|---|
| Prices | Forever | A price from a past month never changes |
| Model / version lists | Until a new month exists | Each list belongs to one month's table |
| List of available months | 1 day | How the pipeline notices a new month |
| IPCA (inflation) | 1 day | A single request; the Banco Central adds one month at a time |
| `data_cache/frames` (derived tables) | 12 hours | Rebuilt in seconds from cached files, no downloads |

A new month costs ~980 requests for the model lists (24 brands × each model year and fuel since 2014) and ~2,310 for the new prices; **January** adds ~710 for the yearly history of each model. At ~47 requests per minute that's ~70 minutes (~85 in January).

**Everything is downloaded again (~2.5 h)** only if you delete `data_cache/` or change `CDC_ANO_MIN`/`CDC_VERSOES`; adding models to `pipeline/catalogo.py` downloads only their prices.

### Other notes

- *Settings → Pages → Source* must be set to **GitHub Actions** in the repository.
- Framework caches each loader's output in `src/.observablehq/cache` and only reruns a loader when its own file changes. After changing code in `pipeline/`, run `npm run clean`.

| Variable | Effect |
|---|---|
| `CDC_OFFLINE=1` | Never touch the network; serve every request from the cache regardless of age, and fail with a clear message if something is missing (set in the GitHub workflow) |

## Tests

```bash
uv run pytest
```
