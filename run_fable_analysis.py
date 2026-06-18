#!/usr/bin/env python
"""
run_fable_analysis.py — End-to-end FABLE pipeline runner

Steps:
  1. Finds the .xlsx/.xlsm workbook in this folder (or pass --workbook)
  2. Runs every pathway through Excel and exports combined CSVs
     (via FableVisualizerV4_AllPathwaysRunner)
  3. Generates 10 PNGs + detailed_metrics.csv + ai_briefing.md
     (via FableReportGen)

Usage:
  python run_fable_analysis.py
  python run_fable_analysis.py --workbook "path/to/file.xlsx"
  python run_fable_analysis.py --max-pathways 2   # quick test
  python run_fable_analysis.py --excel-visible     # show Excel window
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Resolve directories ────────────────────────────────────────────────────
_HERE = Path(__file__).parent.resolve()
_VISUALIZER_DIR = _HERE / "FableVisualizerV4"
_REPORTGEN_DIR  = _HERE / "FableReportGen"

for _d in (_VISUALIZER_DIR, _REPORTGEN_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

# ── Imports from sub-modules ───────────────────────────────────────────────
from FableVisualizerV4_AllPathwaysRunner import run_all_pathways  # noqa: E402
from FableReportGen import (                                       # noqa: E402
    load_combined_tables,
    compute_stats,
    build_briefing,
    _chart_01, _chart_02, _chart_03, _chart_04, _chart_05,
    _chart_06, _chart_07, _chart_08, _chart_09, _chart_10,
)
from FableVisualizerV4_Comparison import (                         # noqa: E402
    choose_baseline_pathway,
    detect_pathway_col,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def find_workbook(folder: Path) -> Path:
    """Return the first .xlsx/.xlsm in folder (excluding temp files)."""
    for ext in ("*.xlsx", "*.xlsm"):
        candidates = [
            p for p in sorted(folder.glob(ext))
            if not p.name.startswith("~$")
        ]
        if candidates:
            return candidates[0]
    raise FileNotFoundError(
        f"No .xlsx/.xlsm workbook found in {folder}\n"
        "Pass --workbook <path> to specify one explicitly."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run all FABLE pathways, generate PNGs and AI briefing."
    )
    parser.add_argument(
        "--workbook", default=None,
        help="Path to .xlsx/.xlsm workbook. Default: auto-detect in this folder.",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Root output directory. Default: <workbook_dir>/exports",
    )
    parser.add_argument(
        "--max-pathways", type=int, default=None,
        help="Limit to first N pathways (useful for quick testing).",
    )
    parser.add_argument(
        "--excel-visible", action="store_true",
        help="Show the Excel window while running (useful for debugging).",
    )
    return parser.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # ── Step 0: Resolve workbook ───────────────────────────────────────────
    if args.workbook:
        workbook_path = Path(args.workbook).expanduser().resolve()
        if not workbook_path.exists():
            raise SystemExit(f"Workbook not found: {workbook_path}")
    else:
        workbook_path = find_workbook(_HERE)

    output_root = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else workbook_path.parent / "exports"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FABLE End-to-End Analysis")
    print(f"  Workbook : {workbook_path.name}")
    print(f"  Outputs  : {output_root}")
    print("=" * 60)

    # ── Step 1: Run all pathways via Excel ─────────────────────────────────
    print("\n[STAGE 1/2] Running all pathways through Excel …")
    run_dir = run_all_pathways(
        workbook_path=workbook_path,
        output_root=output_root,
        max_pathways=args.max_pathways,
        excel_visible=args.excel_visible,
    )
    print(f"  Pathway run complete → {run_dir}")

    # ── Step 2: Generate report ────────────────────────────────────────────
    print("\n[STAGE 2/2] Generating report (PNGs + AI briefing) …")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir  = run_dir / f"report_{ts}"
    graphs_dir  = report_dir / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    # Load combined CSVs produced in stage 1
    print("  Loading combined tables …")
    tables = load_combined_tables(run_dir)
    if not tables:
        raise SystemExit(
            "No combined_tables CSVs found. "
            "The pathway run may have failed — check the run manifest."
        )

    # Detect pathways and baseline
    all_pathways: list[str] = []
    for df in tables.values():
        pcol = detect_pathway_col(df.columns.tolist())
        if pcol:
            all_pathways = sorted(df[pcol].dropna().unique().tolist(), key=str)
            break
    baseline = choose_baseline_pathway(all_pathways)
    print(f"  {len(tables)} tables | {len(all_pathways)} pathways | baseline: {baseline}")

    # Compute statistics → detailed_metrics.csv
    print("  Computing statistics …")
    stats_df = compute_stats(tables, baseline)
    stats_df.to_csv(report_dir / "detailed_metrics.csv", index=False)
    print(f"  detailed_metrics.csv  ({len(stats_df)} rows)")

    # Generate the 10 charts
    print("  Generating charts …")
    _chart_01(tables, graphs_dir, all_pathways)
    _chart_02(tables, graphs_dir, all_pathways)
    _chart_03(tables, graphs_dir, all_pathways)
    _chart_04(tables, graphs_dir, all_pathways)
    _chart_05(tables, graphs_dir, all_pathways)
    _chart_06(tables, graphs_dir, all_pathways)
    _chart_07(tables, graphs_dir, all_pathways)
    _chart_08(tables, graphs_dir, all_pathways)
    _chart_09(tables, graphs_dir, all_pathways)
    _chart_10(tables, graphs_dir, all_pathways, baseline)

    # Build and write the AI briefing markdown
    print("  Writing AI briefing …")
    briefing = build_briefing(tables, stats_df, baseline, all_pathways, run_dir)
    briefing_path = report_dir / "ai_briefing.md"
    briefing_path.write_text(briefing, encoding="utf-8")
    print(f"  ai_briefing.md  ({len(briefing):,} chars)")

    # ── Done ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("All done!")
    print(f"  PNGs       : {graphs_dir}")
    print(f"  Metrics CSV: {report_dir / 'detailed_metrics.csv'}")
    print(f"  AI briefing: {briefing_path}")
    print("=" * 60)

    # Open the output folder in Explorer
    os.startfile(str(report_dir))


if __name__ == "__main__":
    main()
