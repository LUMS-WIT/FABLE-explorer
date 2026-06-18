# FableVisualizerV4

FableVisualizerV4 is a lightweight toolkit to run **all FABLE pathways** and explore results in a Streamlit dashboard.

## What's Included
- `FableVisualizerV4_AllPathwaysRunner.py` - Excel runner that exports all pathway outputs
- `FableVisualizerV4_Dashboard.py` - Streamlit dashboard for viewing exported results
- `FableVisualizerV4_Comparison.py` - shared baseline/deviation logic used by runner and dashboard
- `FableVisualizerV4_Launcher.py` - Tkinter launcher for exports plus dashboard
- `Launch_FableVisualizerV4_Dashboard.bat` - optional convenience launcher for the dashboard
- `Launch_FableVisualizerV4_Launcher.bat` - optional convenience launcher for exports plus dashboard
- `FableVisualizerV4_AllPathwaysRunner.ipynb` - optional notebook workflow for interactive analysis

## Requirements
- Windows + Microsoft Excel installed
- Python packages: `pandas`, `openpyxl`, `pywin32`, `streamlit`, `plotly`

## Quick Start (Dashboard Only)
Double-click:
```text
Launch_FableVisualizerV4_Dashboard.bat
```

This opens the dashboard. In the sidebar, point it at an existing `exports\all_pathways_run_*` folder.

## Run Exports + Dashboard
Double-click:
```text
Launch_FableVisualizerV4_Launcher.bat
```

This opens the launcher, lets you select a workbook and export folder, runs all pathways, and then opens the dashboard.

## Notebook Usage
Open and run:
```text
FableVisualizerV4_AllPathwaysRunner.ipynb
```

The notebook is optional. The core application only needs the `.py` files.

## Outputs
Exports are saved to:
```text
<workbook folder>\exports\all_pathways_run_YYYYMMDD_HHMMSS
```

## Troubleshooting
- If a BAT file does nothing, make sure `streamlit` is installed and the `.py` files are in the same folder as the BAT. The BAT files will prefer `.venv\Scripts\python*.exe`, then `py`, then `python`.
- If the dashboard fails to open automatically, run from PowerShell:
```text
python -m streamlit run FableVisualizerV4_Dashboard.py
```
