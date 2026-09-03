# The results bundle — data contract

`bundle.json` is the **only** interface between the compute layer and the
viewer. Compute can crash, a recalc engine can be swapped, a pathway can fail —
none of that reaches the viewer except as data inside this file.

Authoritative shape: [`bundle.schema.json`](bundle.schema.json) (JSON Schema
2020-12). The Python producer is `fable/compute/model.py`; the golden test
`fable/tests/test_bundle_golden.py` keeps the two in step.

## Versioning

`schema_version` is `MAJOR.MINOR.PATCH`.

| Change | Bump | Viewer behaviour |
| --- | --- | --- |
| New optional field, new table | MINOR | ignores what it doesn't know |
| Renamed/removed field, changed meaning | MAJOR | refuses to render, shows "unsupported bundle version" |
| Fix with no shape change | PATCH | none |

The viewer checks `major(bundle) === major(supported)` before rendering.

## Top-level shape

```jsonc
{
  "schema_version": "1.0.0",
  "generator": "fable-compute 2.0.0",
  "source": {
    "workbook_filename": "FABLEPAKUP50.xlsx",
    "workbook_sha256": "<64 hex, or empty if unknown>",
    "country": "Pakistan",
    "recalc_engine": "xlwings | libreoffice | precomputed-csv",
    "run_id": "all_pathways_run_20260619_155506",
    "generated_at": "2026-09-02T12:39:00Z"
  },
  "pathways": ["Current Trends", "Balanced", ...],   // display order
  "baseline_pathway": "Current Trends",
  "tables": [ Table, ... ],
  "deviation_summary": Grid,
  "run_quality": RunQuality
}
```

### Table

Columnar. One row per (pathway × year × dimension) tuple.

```jsonc
{
  "key": "GHG__ResultsGHG",          // unique; "<sheet>__<excel table name>"
  "sheet": "GHG",
  "table": "ResultsGHG",
  "columns": ["RunPathway", "Year", "GWP_Scen", "TotalCO2e", ...],
  "rows": [ ["Current Trends", 2000, "AR6", 109.49, ...], ... ],
  "pathway_col": "RunPathway",       // always present in columns
  "year_col": "Year",                // or null
  "dimension_cols": ["Year", "GWP_Scen"],
  "numeric_cols": ["TotalCO2e", ...]
}
```

### Grid

```jsonc
{ "columns": ["Table", "Metric", ...], "rows": [ [...], ... ] }
```

Used for `deviation_summary` — the ranked pathway-vs-baseline table produced by
`fable/compute/deviation.py`. Columns are that function's output verbatim.

### RunQuality

```jsonc
{
  "pathways_expected": 6,
  "pathways_ok": 6,
  "pathways_failed": 0,
  "status": "ok | degraded | failed",
  "failures": [ { "pathway": "Net-Zero", "error": "..." } ],
  "checks": [ { "name": "baseline_present", "ok": true, "detail": "..." } ]
}
```

`status` drives a banner in the viewer:

* **ok** — render normally.
* **degraded** — render, show an amber banner listing `failures` / failed `checks`.
* **failed** — a hard check (`baseline_present`, `has_pathways`, `has_tables`)
  failed or zero pathways succeeded. The publish gate blocks it.

## Cell values

Every cell is `string | number | boolean | null`. JSON has no `NaN` /
`Infinity`; the producer writes `null` for any non-finite number and the viewer
treats `null` as missing.

## The publish gate

`fable/compute/validate.py::gate()` returns `publishable` iff:

1. the document validates against `bundle.schema.json`, **and**
2. `run_quality.status != "failed"`.

CI writes `bundle.json` + `gate.json`; deploy only happens when
`gate.publishable` is true. An optional regression check compares table row
counts against the previously published bundle and emits warnings (not
failures) when they move more than 10%.

---

## LibreOffice engine — remaining work

`fable/compute/engines/libreoffice_engine.py` probes for `soffice` but its UNO
recalc macro is not written yet. To finish it:

1. Add `_uno_macro.py` run via
   `soffice --headless --norestore "vnd.sun.star.script:_uno_macro.py$main?language=Python&location=user"`.
2. In the macro: open the copied workbook, and for each row of the
   `PathwaysSelection` table on `PATHWAYS selection` — clear the `SELECTION`
   column, set `x` on that row, `Document.calculateAll()`, then read each named
   table range on `GHG, PRODUCTION, TRADE, JOBS, FOOD, LAND, WATER, N and P,
   BIODIVERSITY` and append CSV rows tagged with `RunPathway`.
3. Emit the exact directory layout in `bundle.py`'s module docstring
   (`combined_tables/<SHEET>__<Table>__all_pathways.csv` + `run_manifest.csv`).
4. Flip `available()` to return `True` when `soffice` is found, and make the
   golden test run this engine against `FABLEPAKUP50.xlsx`, diffing the bundle
   against `fixtures/expected_summary.json`.
