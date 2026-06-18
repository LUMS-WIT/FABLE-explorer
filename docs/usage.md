# Usage Guide

## Prerequisites

- **Windows** with Microsoft Excel installed (required for workbook recalculation via COM automation)
- Python 3.9 or later
- The FABLE Pakistan workbook (`.xlsx` or `.xlsm`)

### Install dependencies

```bash
pip install pywin32 openpyxl pandas streamlit plotly
```

Or with a virtual environment (recommended):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install pywin32 openpyxl pandas streamlit plotly
```

---

## Option 1: GUI Launcher (recommended for non-technical users)

Double-click `Launch_Launcher.bat`.

The launcher window has three steps:
1. **Select workbook** — browse to your `.xlsx` / `.xlsm` file
2. **Select export folder** — where outputs will be written (defaults to an `exports/` subfolder)
3. **Run Dashboard** — runs all pathways, then opens the Streamlit dashboard automatically

---

## Option 2: Streamlit Dashboard (direct)

Double-click `Launch_Dashboard.bat`.

This opens the dashboard in your browser. Point it at an existing `all_pathways_run_*` output folder to explore previously generated results without re-running Excel.

Or from a terminal:

```bash
streamlit run src/dashboard.py
```

---

## Option 3: Command Line Runner

Run all pathways from a terminal:

```bash
python src/runner.py --workbook "path/to/Pakistan.xlsx"
```

Key flags:

| Flag | Description |
|---|---|
| `--workbook <path>` | Path to the Excel workbook |
| `--output-dir <path>` | Where to write outputs (default: `exports/` next to workbook) |
| `--max-pathways N` | Limit to first N pathways — useful for quick testing |
| `--excel-visible` | Show the Excel window during processing (helpful for debugging) |

---

## Option 4: Jupyter Notebook

Open `notebooks/runner.ipynb` in JupyterLab or VS Code and run the cells. The notebook must be run from the `notebooks/` directory so it can locate `src/runner.py` one level up.

---

## Output Structure

After a run, outputs are written to:

```
exports/
└── all_pathways_run_<YYYYMMDD_HHMMSS>/
    ├── run_manifest.csv                  ← status per pathway (success/error)
    ├── scenario_deviation_summary.csv    ← deviation vs baseline across all metrics
    ├── combined_tables/                  ← one CSV per output sheet, all pathways merged
    ├── tables_per_pathway/               ← per-pathway table CSVs
    ├── charts_per_pathway/               ← per-pathway chart series CSVs
    └── workbooks/                        ← recalculated workbook copies
```

All combined CSVs include a `RunPathway` column identifying the scenario.
