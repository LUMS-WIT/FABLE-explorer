# FABLE Pakistan — Post-processing & Visualization

Post-processing and visualization tools for FABLE Pakistan pathway outputs. This repository takes the raw Excel-based FABLE Pakistan workbook, runs all scenario pathways through Excel to extract outputs, and provides an interactive dashboard to explore and compare results across pathways.

FABLE (Food, Agriculture, Biodiversity, Land, and Energy) is a global modelling framework for analyzing food and land-use systems. See [docs/overview.md](docs/overview.md) for project background.

---

## What This Repository Does

1. **Runs all pathways** — iterates every named scenario in the FABLE Pakistan workbook, triggers Excel recalculation, and exports all output tables and chart series as CSVs.
2. **Compares pathways** — computes deviation of each scenario from a chosen baseline (`CurrentTrends` by default) across all output domains.
3. **Visualizes results** — interactive Streamlit dashboard with curated charts, combined table explorer, and deviation analysis.

Output domains: GHG, PRODUCTION, TRADE, JOBS, FOOD, LAND, WATER, N and P, BIODIVERSITY.

---

## Repository Structure

```
FABLE_Pakistan/
├── src/
│   ├── comparison.py     # Shared helpers: deviation analysis, baseline comparison
│   ├── runner.py         # Step 1: run all pathways through Excel, export CSVs
│   ├── dashboard.py      # Step 2: Streamlit dashboard for exploring outputs
│   └── launcher.py       # Windows GUI launcher (Tkinter)
├── notebooks/
│   └── runner.ipynb      # Jupyter version of the runner
├── docs/                 # Documentation
├── Launch_Dashboard.bat  # Windows: launch Streamlit dashboard
├── Launch_Launcher.bat   # Windows: launch GUI launcher
├── launch_dashboard.sh   # Mac/Linux: launch Streamlit dashboard
├── launch_launcher.sh    # Mac/Linux: launch GUI launcher (run step Windows-only)
├── pyproject.toml        # Project metadata and dependencies
├── requirements.txt      # Pinned dependencies for quick install
└── run_fable_analysis.py # Planned end-to-end pipeline (WIP)
```

---

## Installation

**Requires Windows with Microsoft Excel** — the runner uses Excel COM automation to recalculate the workbook for each pathway.

```bash
# Option 1: install as a project (recommended)
pip install -e .

# Option 2: install dependencies directly
pip install -r requirements.txt

# Then install pywin32 separately (Windows only)
pip install pywin32>=306
```

For Jupyter notebook support:

```bash
pip install -e ".[notebook]"
```

### Virtual environment (recommended)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[notebook]"
pip install pywin32>=306
```

---

## Workflow

```
1. Place FABLE Pakistan workbook (.xlsx / .xlsm) in this folder
        ↓
2. Run pathways  →  Launch_Launcher.bat  or  python src/runner.py --workbook <path>
        ↓
3. Explore results  →  Launch_Dashboard.bat  or  streamlit run src/dashboard.py
```

---

## Quick Start

**Windows** (full workflow — run pathways + visualize):

1. Place your FABLE Pakistan workbook (`.xlsx` or `.xlsm`) in this folder.
2. Double-click `Launch_Launcher.bat` to open the GUI.
3. Select the workbook, choose an output folder, and click **Run Dashboard**.

**Mac / Linux** (visualize existing run outputs only — pathway runner requires Windows + Excel):

```bash
chmod +x launch_dashboard.sh
./launch_dashboard.sh
```

---

## CLI Usage

```bash
# Run all pathways
python src/runner.py --workbook "path/to/Pakistan.xlsx"

# Optional flags
python src/runner.py --workbook "Pakistan.xlsx" --max-pathways 2   # quick test
python src/runner.py --workbook "Pakistan.xlsx" --excel-visible     # show Excel window

# Launch dashboard
streamlit run src/dashboard.py
```

---

## Outputs

Each run produces an `all_pathways_run_<timestamp>/` folder:

```
exports/
└── all_pathways_run_<timestamp>/
    ├── run_manifest.csv                  ← status per pathway (success / error)
    ├── scenario_deviation_summary.csv    ← deviation vs baseline across all metrics
    ├── combined_tables/                  ← one CSV per output sheet, all pathways merged
    ├── tables_per_pathway/               ← per-pathway table CSVs
    ├── charts_per_pathway/               ← per-pathway chart series CSVs
    └── workbooks/                        ← recalculated Excel copies per pathway
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
