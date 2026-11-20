# `viewer/` — static FABLE bundle explorer

Vite + React + TypeScript. Reads a single `bundle.json`
([`../fable/contract/bundle.schema.json`](../fable/contract/bundle.schema.json))
and renders it. No backend — deploys to GitHub Pages as static files.

## Develop

```bash
cd viewer
npm install
npm run dev            # http://localhost:5173/
```

It loads `public/data/bundle.json` on start. Refresh it with:

```bash
python -m fable.compute bundle <run_dir> --out viewer/public/data
```

You can also drag any `bundle.json` onto the page, or use **Open bundle…**.

## Build

```bash
npm run build          # -> viewer/dist/
VITE_BASE=/ npm run build   # for a custom domain / user-site root
```

`VITE_BASE` defaults to `./` (relative), so the built site works under any path:
a GitHub project site, a custom domain, or `python -m fable.compute view`, which
serves `dist/` on http://127.0.0.1:8765 with the latest `public/data/bundle.json`.

## Tabs

| Tab | Country-agnostic? | What it shows |
| --- | --- | --- |
| Overview | yes | source metadata, pathway list, run-quality banner, table inventory |
| Table explorer | yes | any output table × chosen pathways, raw / Δ / %Δ vs baseline, line chart + grid |
| Deviation analysis | yes | ranked pathway-vs-baseline divergence from `deviation_summary` |
| IAMC export | yes | `bundle.iamc` (schema 1.1.0+): IAMC variables, chart, table, CSV downloads; explains how to rebuild when absent |
| Guide | yes | user documentation for the site and the IAMC conventions |

## Robustness

* refuses a bundle whose `schema_version` major ≠ `SUPPORTED_MAJOR` (`src/bundle/types.ts`)
* `run_quality.status` drives a banner; a `degraded` bundle still renders
* every chart/grid degrades independently on missing columns
* raw workbook column names are humanised for titles/legends by
  `src/lib/labels.ts` (hover shows the original token)
