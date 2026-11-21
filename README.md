# FABLE Explorer

**Live dashboard:** https://lums-wit.github.io/FABLE-explorer/

Post-processing and a web viewer for any [FABLE](https://fableconsortium.org)
country workbook. Runs every pathway (scenario) in the Excel model, compares
each against a baseline, and turns the result into an interactive site.

- **What FABLE is:** [docs/overview.md](docs/overview.md)
- **Pathway comparison / deviation analysis:** [docs/comparisons.md](docs/comparisons.md)
- **IAMC-format export (common-definitions):** [docs/iamc.md](docs/iamc.md)
- **Legacy Excel/Streamlit usage:** [docs/usage.md](docs/usage.md)

---

## How it fits together

```
workbook.xlsx
  │   recalc every pathway            (needs Excel now; LibreOffice later)
  ▼
CSV run directory
  │   fable/compute  →  bundle.json   (pure Python, runs anywhere)
  ▼
bundle.json  ── the versioned data contract ──►  viewer/  (static React site)
```

The `bundle.json` in the middle is the only thing the site reads. Compute can
fail a pathway, drift, or change engine and the worst the site shows is an
amber "partial run" banner — never a broken page.

| Piece | Path | Docs |
| --- | --- | --- |
| Compute layer + data contract | [`fable/`](fable/) | [fable/README.md](fable/README.md) |
| Static viewer | [`viewer/`](viewer/) | [viewer/README.md](viewer/README.md) |
| Deployment / CI | [`.github/workflows/`](.github/workflows/) | [docs/DEPLOY.md](docs/DEPLOY.md) |

---

## How to launch

**One-time setup** (Python 3.9+, and Microsoft Excel only if you recalculate workbooks):

```bash
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -e ".[excel,dev]"
cd viewer && npm ci && npm run build && cd ..   # builds the website once (needs Node 20+)
```

Set `workbook:` and `country:` in [`config.yaml`](config.yaml).

**Desktop launcher.** Double-click `Launch_Launcher.command` (macOS) or
`Launch_Launcher.bat` (Windows), or run `python src/launcher.py`. Pick the
workbook, type the IAMC model name (e.g. `FABLE-Pakistan v1`) and press **Run**.
**Open viewer** shows the results in your browser.

**Command line.**

```bash
# recalculate every pathway (Excel), write bundle.json and the IAMC files
python -m fable.compute run workbooks/YOUR_COUNTRY.xlsx --model "FABLE-YourCountry v1"

# no Excel: rebuild from an existing run directory
python -m fable.compute bundle exports/all_pathways_run_XXXX --model "FABLE-YourCountry v1"

# IAMC files only
python -m fable.compute iamc exports/all_pathways_run_XXXX --model "FABLE-YourCountry v1"

# open the website locally (http://127.0.0.1:8765) with the latest bundle
python -m fable.compute view
```

### Running hundreds or thousands of pathways

The workbook's own pathway table holds a handful of rows. For more, write a
**pathway design**: a CSV with one row per pathway and one column per scenario
lever (Diet, Land, Afforestation, Livestock, ...). The tool writes each row into
a spare row of its private workbook copy, so you never edit the workbook.

```bash
python -m fable.compute pathways levers                     # every lever and its allowed options
python -m fable.compute pathways template -o design.csv     # the workbook's pathways, to edit by hand
python -m fable.compute pathways sample -n 1000 --vary Diet,Land,Afforestation,Livestock,Crop -o design.csv
python -m fable.compute pathways factorial --vary Diet,Land,Afforestation -o design.csv   # all 48 combinations
python -m fable.compute pathways check --design design.csv  # validate before a long run

python -m fable.compute run --design design.csv --workers 8 --model "FABLE-Pakistan v1"
```

Levers you leave out of the design keep the value of the base pathway
(`--base-pathway`, default the first). Reporting settings (BaseYear, GWP, Price)
are never varied unless you name them. Identical combinations are computed once;
a killed run resumes where it stopped; `--pathway-slice A:B` splits a run across
machines.

For large runs the dashboard switches to an ensemble view: every pathway as a
grey distribution, up to seven chosen pathways in colour, and a panel showing
which lever settings move each indicator. The IAMC files carry every pathway,
with its lever settings as columns of the `meta` sheet. The bundle keeps raw
workbook tables for the first 25 pathways only, so it stays a manageable size
(1,000 pathways: about 27 MB, 4 MB as served compressed).

Outputs:

| File | What it is |
| --- | --- |
| `viewer/public/data/bundle.json` | everything the website shows; can also be dragged onto the published site |
| `exports/<run>/iamc/<Model>_iamc.csv` | IAMC timeseries, all pathways ([docs/iamc.md](docs/iamc.md)) |
| `exports/<run>/iamc/<Model>_iamc.xlsx` | the same, with about, meta and mapping sheets, for sharing |

---

## What the current version does

### 1. View a results bundle — no install

Open the site (once deployed to GitHub Pages) or run it locally:

```bash
python -m fable.compute view            # built site, http://127.0.0.1:8765
cd viewer && npm ci && npm run dev      # or the dev server, http://localhost:5173/
```

It loads the committed `viewer/public/data/bundle.json`. You can also **drag any
`bundle.json` onto the page** or use **Open bundle…** — fully offline, no server.

Tabs:

| Tab | Shows |
| --- | --- |
| Summary | where each pathway lands on the headline indicators (dot strip), statements of what stands out, a scorecard |
| Compare pathways | any IAMC variable: ranked bars for one year, trajectories, composition of a total, two pathways head to head |
| IAMC data | the IAMC table with charts, variable mapping and CSV downloads |
| Workbook tables | any raw output table × chosen pathways; raw / Δ / % Δ vs baseline |
| Deviation ranking | workbook metrics ranked by divergence from the baseline |
| Run details | source info, pathway list, table inventory |
| Guide | how to use the site, the IAMC conventions, and how to build a bundle |

All tabs work with any FABLE country workbook. Summary, Compare and IAMC data
need a bundle with the IAMC block (schema 1.1.0+). Pathway colours follow the
IPCC AR6 scenario palette, checked for colour-blind separation in light and dark
mode.

Workbook column names (`TotalCO2e`, `LNPPMatureForest`, …) are humanised in
chart titles and legends; hover shows the original.

### 2. Generate a bundle from a workbook

Needs Microsoft Excel installed (Windows or macOS).

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[excel,dev]"

# recalc every pathway and write the bundle
python -m fable.compute run workbooks/YOUR_COUNTRY.xlsx --workers 8 --out viewer/public/data

# or the desktop launcher (Browse → pick engine + workers → Run → Open viewer)
python src/launcher.py
```

Point `config.yaml` at your workbook first (`workbook:`, optional `country:` and
`baseline_pathway:`).

Check `viewer/public/data/gate.json` — it says whether the bundle passed the
publish gate (schema valid **and** run status not `failed`).

### 3. Add a new / updated workbook

1. Put the `.xlsx` in `workbooks/` (git-ignored) and update `config.yaml`.
2. `python -m fable.compute run workbooks/NEW.xlsx --out viewer/public/data`.
3. Commit **`viewer/public/data/bundle.json`** (not the workbook) and push.
4. GitHub Pages redeploys automatically.

The website itself does **not** accept a raw `.xlsx` upload yet — see below.

### 4. Deploy

Settings → Pages → Source: **GitHub Actions**, then push. Full flow, custom
domains, and scaling to hundreds of pathways: [docs/DEPLOY.md](docs/DEPLOY.md).

### Scaling

`--workers N` runs N Excel processes. `--pathway-slice A:B --run-dir shared`
splits a run across machines / CI jobs; identical scenario tuples are computed
once; a killed run resumes. Details in
[fable/README.md](fable/README.md#scaling-to-hundreds-of-pathways).

---

## What to expect next

| Status | Item |
| --- | --- |
| **done** | data contract + bundle builder + publish gate; parallel resumable xlwings engine; static viewer; CI + Pages workflows; IAMC export (files + IAMC tab) |
| **next** | **LibreOffice engine** — headless recalc with no Excel licence, so CI (or a container) can build bundles on its own. Env probe is in place; the UNO recalc macro is specified in [fable/contract/CONTRACT.md](fable/contract/CONTRACT.md) but not written. |
| **next** | **Upload-and-run web app** — a small API (LibreOffice engine behind FastAPI, on a free host) that takes an `.xlsx` upload, recalculates, and returns a bundle the viewer renders. This needs a server, so it is *in addition to* the static GitHub Pages viewer, not a replacement. |
| **maybe** | **In-browser recalc** (HyperFormula / Pyodide) — true `.xlsx` upload with zero server, staying on GitHub Pages. Gated on a fidelity check against known-good outputs; may not be feasible for FABLE's formula set. |
| **later** | curated per-domain charts in the viewer (workbook-column-specific, opt-in per country); bundle size trimming; a LibreOffice golden test in CI. |

### Today's honest limitation

The GitHub Pages site is **view-only**: give it a `bundle.json`, it renders.
Turning a workbook into a bundle is a separate step that needs Excel (local, or
a self-hosted CI runner). The "drop your FABLE file on the website and press
Launch" experience arrives with the upload API above.

---

## Repository layout

```
fable/            compute layer + data contract (new)
  compute/        engines, bundle builder, publish gate, CLI, local web server
  iamc/           IAMC export: product table, common-definitions snapshot
  contract/       bundle.schema.json + CONTRACT.md
  tests/          golden test over a frozen Pakistan run
viewer/           static React app (Vite + TypeScript + Plotly)
src/              legacy: runner.py, dashboard.py (Streamlit), launcher.py (rewired)
docs/             overview, usage, comparisons, DEPLOY
workbooks/        put your .xlsx here (git-ignored)
config.yaml       workbook path + country + baseline
```

Legacy `src/runner.py` and `src/dashboard.py` still work unchanged; they are
retired once the new stack reaches parity.

## License

MIT — see [LICENSE](LICENSE).
