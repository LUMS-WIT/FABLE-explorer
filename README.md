# FABLE Explorer

Post-processing and a web viewer for any [FABLE](https://fableconsortium.org)
country workbook. Runs every pathway (scenario) in the Excel model, compares
each against a baseline, and turns the result into an interactive site.

- **What FABLE is:** [docs/overview.md](docs/overview.md)
- **Pathway comparison / deviation analysis:** [docs/comparisons.md](docs/comparisons.md)
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

## What the current version does

### 1. View a results bundle — no install

Open the site (once deployed to GitHub Pages) or run it locally:

```bash
cd viewer && npm ci && npm run dev      # http://localhost:5173/FABLE_Pakistan/
```

It loads the committed `viewer/public/data/bundle.json`. You can also **drag any
`bundle.json` onto the page** or use **Open bundle…** — fully offline, no server.

Tabs:

| Tab | Works with any FABLE workbook | Shows |
| --- | --- | --- |
| Overview | yes | source info, pathway list, run-quality banner, table inventory |
| Table explorer | yes | any output table × chosen pathways; raw / Δ / % Δ vs baseline; chart + grid |
| Deviation analysis | yes | pathways ranked by divergence from the baseline |

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
| **done** | data contract + bundle builder + publish gate; parallel resumable xlwings engine; static viewer; CI + Pages workflows |
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
  compute/        engines, bundle builder, publish gate, CLI
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
