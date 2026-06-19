# FABLE All-Pathways Runner & Dashboard

Post-processing and visualization tools for FABLE country workbooks. This repository takes any Excel-based FABLE workbook, runs all scenario pathways through Excel to extract outputs, and provides an interactive Streamlit dashboard to explore and compare results.

FABLE (Food, Agriculture, Biodiversity, Land, and Energy) is a global modelling framework for analyzing food and land-use systems. See [docs/overview.md](docs/overview.md) for project background.

---

## What This Repository Does

1. **Runs all pathways** — iterates every named scenario in the FABLE workbook, triggers Excel recalculation, and exports all output tables as CSVs.
2. **Compares pathways** — computes deviation of each scenario from a chosen baseline (`CurrentTrends` by default) across all output domains.
3. **Visualizes results** — interactive Streamlit dashboard with curated charts, a combined table explorer, pathway comparison plots, and deviation analysis.

Output domains: GHG, PRODUCTION, TRADE, JOBS, FOOD, LAND, WATER, N and P, BIODIVERSITY.

---

## Adapting for Your Country

This repository was developed for FABLE Pakistan and can be adapted for any FABLE country workbook:

1. Place your country's `.xlsx` workbook in `workbooks/` and update `config.yaml`.
2. The runner discovers pathways and output tables automatically — no code changes needed.
3. The **Curated Charts** tab contains charts tailored for the Pakistan workbook column names. For other countries, use the **Combined Tables**, **Pathway Comparison**, and **Deviation Analysis** tabs, which work generically with any FABLE output structure.

---

## Repository Structure

```
FABLE_Pakistan/
├── fable.py              # Unified entry point — run pathways, dashboard, or launcher
├── config.yaml           # Workbook path (edit this, not the code)
├── workbooks/            # Place your .xlsx workbook here (not committed to git)
├── src/
│   ├── runner.py         # Phase 1: iterate all pathways through Excel, export CSVs
│   ├── dashboard.py      # Phase 2: Streamlit dashboard for exploring outputs
│   ├── comparison.py     # Shared helpers: deviation analysis, baseline comparison
│   └── launcher.py       # Optional Tkinter GUI launcher
├── notebooks/
│   └── runner.ipynb      # Jupyter version of the runner
├── docs/                 # Documentation
├── pyproject.toml        # Project metadata and dependencies
└── requirements.txt      # Dependencies for direct install
```

---

## Installation

Requires **Microsoft Excel** (Windows or Mac) for Phase 1 (running pathways). Phase 2 (dashboard) works on any machine.

### Recommended: virtual environment

```bash
python -m venv .venv

# Mac / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -e .
```

Or without installing as a package:

```bash
pip install -r requirements.txt
```

For Jupyter notebook support:

```bash
pip install -e ".[notebook]"
```

---

## Workflow

```
1. Place workbook in workbooks/ and edit config.yaml
         ↓
2. Run pathways  →  python fable.py run          (needs Excel installed)
         ↓
3. View results  →  python fable.py dashboard    (browser, no Excel needed)
```

---

## Quick Start

**Step 1** — place your workbook in `workbooks/` and set its name in `config.yaml`:

```yaml
workbook: workbooks/FABLEPAKUP50.xlsx
```

**Step 2** — run all pathways (opens Excel, iterates each scenario, exports CSVs):

```bash
python fable.py run
```

**Step 3** — explore results in the browser:

```bash
python fable.py dashboard
```

---

## CLI Reference

```bash
# Run all pathways (reads workbook from config.yaml)
python fable.py run

# Run with options
python fable.py run --max-pathways 2          # quick test: first 2 pathways only
python fable.py run --excel-visible           # show Excel window while running
python fable.py run --workbook path/to/file.xlsx   # override config.yaml

# Launch dashboard
python fable.py dashboard

# Launch Tkinter GUI (alternative to CLI)
python fable.py launcher
```

Pass `--help` to see all options:

```bash
python fable.py run --help
```

---

## Outputs

Each run creates a timestamped folder under `exports/`:

```
exports/
└── all_pathways_run_<timestamp>/
    ├── run_manifest.csv                  ← status per pathway (ok / failed)
    ├── scenario_deviation_summary.csv    ← deviation vs baseline across all metrics
    ├── combined_tables/                  ← one CSV per output table, all pathways merged
    └── tables_per_pathway/               ← per-pathway table CSVs
```

All combined CSVs include a `RunPathway` column to identify the scenario.

---

## Dashboard Tabs

| Tab                          | Description                                                                                                                                                                                                             |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Curated Charts**     | Pre-built charts for the Pakistan workbook (production, trade, jobs, food, land, GHG, biodiversity)                                                                                                                     |
| **Combined Tables**    | Interactive explorer for any output table. Toggle between**Single metric** (line/bar + optional baseline comparison) and **Multi-metric comparison** (subplot grid of all selected metrics across pathways) |
| **Deviation Analysis** | Highlights which metrics deviate most from the baseline pathway                                                                                                                                                         |
| **Chart Series**       | Plots chart series extracted directly from Excel (if available)                                                                                                                                                         |

---

## Documentation

- [Overview](docs/overview.md) — Project background and output domain descriptions
- [Usage Guide](docs/usage.md) — Step-by-step instructions for all run modes
- [Pathway Comparisons](docs/comparisons.md) — How deviation analysis and baseline comparison work

---

## Contributors

- [Muhammad Awais](https://github.com/awais307)
- [Syeda Baseerat Fatima](https://github.com/syeda-baseerat)
- [Ahmad Saeed](https://github.com/Ahmed-Saeed20)

---

## License

This project is licensed under the [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSE) license.

You are free to share and adapt this work for any purpose, including commercially, as long as you give appropriate credit to the authors. When using or building on this tool, please cite:

> Muhammad Awais, Syeda Baseerat Fatima, Ahmad Saeed. *FABLE All-Pathways Runner & Dashboard*. 2026. https://github.com/awais307/FABLE_Pakistan
