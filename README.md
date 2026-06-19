# FABLE Pakistan — Post-processing & Visualization

Post-processing and visualization tools for FABLE Pakistan pathway outputs. This repository takes the raw Excel-based FABLE Pakistan workbook, runs all scenario pathways through Excel to extract outputs, and provides an interactive dashboard to explore and compare results across pathways.

FABLE (Food, Agriculture, Biodiversity, Land, and Energy) is a global modelling framework for analyzing food and land-use systems. See [docs/overview.md](docs/overview.md) for project background.

---

## What This Repository Does

1. **Runs all pathways** — iterates every named scenario in the FABLE Pakistan workbook, triggers Excel recalculation, and exports all output tables as CSVs.
2. **Compares pathways** — computes deviation of each scenario from a chosen baseline (`CurrentTrends` by default) across all output domains.
3. **Visualizes results** — interactive Streamlit dashboard with curated charts, combined table explorer, and deviation analysis.

Output domains: GHG, PRODUCTION, TRADE, JOBS, FOOD, LAND, WATER, N and P, BIODIVERSITY.

---

## Repository Structure

```
FABLE_Pakistan/
├── fable.py              # Unified entry point — run pathways or launch dashboard
├── config.yaml           # Workbook filename config (edit here, not in code)
├── src/
│   ├── runner.py         # Phase 1: run all pathways through Excel, export CSVs
│   ├── dashboard.py      # Phase 2: Streamlit dashboard for exploring outputs
│   ├── comparison.py     # Shared helpers: deviation analysis, baseline comparison
│   └── launcher.py       # GUI launcher (Tkinter)
├── notebooks/
│   └── runner.ipynb      # Jupyter version of the runner
├── docs/                 # Documentation
├── pyproject.toml        # Project metadata and dependencies
└── requirements.txt      # Dependencies for direct install
```

---

## Installation

Requires **Microsoft Excel** (Windows or Mac) for Phase 1 (running pathways). Phase 2 (dashboard) works on any machine.

```bash
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

### Recommended: virtual environment

```bash
python -m venv .venv

# Mac / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -e .
```

---

## Workflow

```
1. Edit config.yaml with your workbook filename
         ↓
2. Run pathways  →  python fable.py run          (needs Excel installed)
         ↓
3. View results  →  python fable.py dashboard    (browser, no Excel needed)
```

---

## Quick Start

**Step 1** — set your workbook name in `config.yaml`:

```yaml
workbook: FABLEPAKUP50.xlsx
```

Place the workbook file in the repo root.

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
python fable.py run --max-pathways 2        # quick test: first 2 pathways only
python fable.py run --excel-visible         # show Excel window while running
python fable.py run --charts                # also extract raw chart data (slower)
python fable.py run --workbook path/to/file.xlsx   # override config.yaml

# Launch dashboard
python fable.py dashboard
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
    ├── combined_tables/                  ← one CSV per output sheet, all pathways merged
    ├── tables_per_pathway/               ← per-pathway table CSVs
    ├── charts_per_pathway/               ← per-pathway chart series CSVs (if --charts)
    └── workbooks/                        ← recalculated Excel copy per pathway
```

All combined CSVs include a `RunPathway` column to identify the scenario.

---

## Documentation

- [Overview](docs/overview.md) — Project background and output domain descriptions
- [Usage Guide](docs/usage.md) — Step-by-step instructions for all run modes
- [Pathway Comparisons](docs/comparisons.md) — How deviation analysis and baseline comparison work

---

## Contributors

- [Syeda Baseerat Fatima](https://github.com/syeda-baseerat)
- [Ahmad Saeed](https://github.com/Ahmed-Saeed20)
- [Muhammad Awais](https://github.com/awais307)
