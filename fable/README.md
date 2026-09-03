# `fable/` — compute layer + data contract

Turns a FABLE country workbook into a single versioned `bundle.json` that a
static viewer renders. Replaces the ad-hoc `src/runner.py` → CSV → Streamlit
flow with a firewall in the middle: the **contract**.

```
FABLE .xlsx
  │
  ▼  fable/compute/engines/         recalc every pathway  → CSV run dir   [fragile, isolated]
  ▼  fable/compute/bundle.py        CSV run dir           → Bundle        [pure python]
  ▼  fable/compute/validate.py      publish gate (schema + quality)       [pure python]
  ▼
bundle.json  ──►  viewer/  (static React, GitHub Pages)                   [cannot break the pipeline]
```

Whatever goes wrong upstream — Excel COM crash, LibreOffice version drift, one
pathway failing — the worst case downstream is a `degraded` banner, never a
broken site. See [`contract/CONTRACT.md`](contract/CONTRACT.md).

## Layout

| Path | Role |
| --- | --- |
| `contract/bundle.schema.json` | authoritative bundle shape (JSON Schema 2020-12) |
| `contract/CONTRACT.md` | human docs + versioning rules |
| `compute/model.py` | dataclasses ↔ JSON (NaN → null) |
| `compute/bundle.py` | CSV run dir → `Bundle`; never raises on bad data |
| `compute/deviation.py` | pathway-vs-baseline maths (moved from `src/comparison.py`) |
| `compute/validate.py` | `gate()` → publishable? + warnings |
| `compute/engines/` | `xlwings` (Excel, parallel), `libreoffice` (headless, pending), `auto` |
| `compute/pipeline.py` | wires the stages, writes `bundle.json` + `gate.json` |
| `compute/cli.py` | `python -m fable.compute …` |
| `tests/` | golden test against a frozen 6-pathway Pakistan run |

## Commands

```bash
# which recalc engines work on this machine
python -m fable.compute engines

# recalc a workbook (needs Excel or LibreOffice) → CSV run directory
python -m fable.compute recalc workbooks/FABLEPAKUP50.xlsx --engine auto

# CSV run directory → bundle.json + gate.json  (no spreadsheet engine needed)
python -m fable.compute bundle exports/all_pathways_run_XXXX \
    --workbook workbooks/FABLEPAKUP50.xlsx --out viewer/public/data

# recalc + bundle in one step
python -m fable.compute run workbooks/FABLEPAKUP50.xlsx --out viewer/public/data

# re-check an existing bundle against the gate
python -m fable.compute check viewer/public/data/bundle.json
```

Exit code is non-zero when the publish gate rejects the bundle — CI keys the
deploy off that.

## Scaling to hundreds of pathways

The recalc loop, not the bundle build, is the cost. The `xlwings` engine
(`engines/xlwings_engine.py`) does:

| technique | effect |
| --- | --- |
| parse the 14 MB workbook **once** with openpyxl, share the plan | drops N file parses to 1 |
| Excel on `calculation=manual`, events / screen-updating / alerts off | ~2–3× per pathway |
| one `app.calculate()` per pathway, then bulk-read each table range | fewer COM round-trips |
| **scenario-tuple dedupe** — identical selections computed once, CSVs fanned out | FABLE decks repeat scenarios; often 30–50% fewer recalcs |
| **resumable** — a pathway whose CSVs already exist is skipped | kill & restart safely |
| `--workers N` — N Excel processes, each its own workbook copy, sharded pathways | ~linear to CPU/disk limit |
| `--pathway-slice START:STOP` — disjoint ranges on M machines / CI matrix jobs, merge run dirs | scales past one box |

```bash
# 8 local Excel processes
python -m fable.compute run workbooks/FABLEPAKUP50.xlsx --workers 8

# machine k of 4 (CI matrix): recalc its slice, then a final job bundles the merged run dir
python -m fable.compute recalc WB.xlsx --pathway-slice $((k*250)):$(((k+1)*250)) --run-dir exports/big_run
```

For a licence-free fleet, finish the `libreoffice` engine (below) and run the
same slicing across containers.

## Status

- [x] Contract, model, bundle builder, publish gate, CLI, golden test
- [x] `xlwings` engine — native, parallel (`--workers`), dedupe, resumable, sliceable
- [x] `viewer/` — static React app (`../viewer/`)
- [x] `src/launcher.py` — rewired to the new pipeline (engine + workers picker)
- [x] GitHub Actions — `ci.yml`, `deploy-pages.yml`, `bundle.yml`, `recalc-selfhosted.yml` (see `docs/DEPLOY.md`)
- [ ] `libreoffice` engine — probe done, UNO recalc macro pending (see CONTRACT.md)

## Legacy `src/`

`src/runner.py`, `src/comparison.py`, `src/dashboard.py` still work unchanged
and are removed once the new stack reaches parity. `src/launcher.py` has been
rewired to drive `fable.compute` (engine + parallel workers + bundle output).
`compute/deviation.py` is the canonical copy of the comparison maths;
`src/comparison.py` is a frozen duplicate until `src/dashboard.py` goes.
