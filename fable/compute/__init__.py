"""Compute layer: turn a FABLE workbook into a validated results bundle.

Two independent stages, joined only by a CSV run directory on disk:

1. ``engines`` — recalc every pathway in the workbook and write per-pathway +
   combined CSVs (the same layout the legacy ``src/runner.py`` produced).
   This stage needs a spreadsheet engine (Excel via xlwings, or LibreOffice
   headless) and is the only fragile part of the system.

2. ``bundle`` + ``validate`` — read that CSV run directory and emit a single
   versioned ``bundle.json`` plus a pass/fail quality report. Pure Python,
   no spreadsheet engine, runs anywhere (CI, Pyodide, a laptop).

Because the stages only share a directory of CSVs, stage 1 can be swapped or
can partially fail without stage 2 or the viewer breaking.
"""

BUNDLE_SCHEMA_VERSION = "1.0.0"
