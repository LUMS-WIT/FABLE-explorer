#!/usr/bin/env python
"""
Run every pathway in a FABLE workbook, recalculate in Excel, and export outputs.

Outputs per pathway:
- Recalculated workbook copy (.xlsx/.xlsm matching source extension)
- CSV files for all output tables on report sheets
- CSV files for every chart series source range on report sheets

Aggregated outputs:
- Combined CSV per output table with a Pathway column
- Run manifest CSV with status per pathway
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter, range_boundaries

from comparison import export_scenario_deviation_summary, safe_name

try:
    import win32com.client as win32
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "win32com is required. Install pywin32 and ensure Excel is installed."
    ) from exc


TABLE_OUTPUT_SHEETS = [
    "GHG",
    "PRODUCTION",
    "TRADE",
    "JOBS",
    "FOOD",
    "LAND",
    "WATER",
    "N and P",
    "BIODIVERSITY",
]

CHART_OUTPUT_SHEETS = TABLE_OUTPUT_SHEETS + ["SCENARIOS definition"]
DEVIATION_SUMMARY_FILE = "scenario_deviation_summary.csv"


@dataclass
class PathwaySelectionInfo:
    sheet_name: str
    selection_col_idx: int
    pathway_col_idx: int
    first_data_row: int
    last_data_row: int
    pathways: List[Tuple[int, str]]

RUN_PATHWAY_COL = "RunPathway"


def dedupe_headers(headers: List[object]) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for i, header in enumerate(headers, start=1):
        base = str(header).strip() if header is not None else f"col_{i}"
        if not base:
            base = f"col_{i}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        out.append(base if count == 0 else f"{base}_{count+1}")
    return out


def table_to_dataframe(ws, ref: str) -> pd.DataFrame:
    rows = [[cell.value for cell in row] for row in ws[ref]]
    if not rows:
        return pd.DataFrame()
    headers = dedupe_headers(rows[0])
    data = rows[1:] if len(rows) > 1 else []
    return pd.DataFrame(data, columns=headers)


def table_ref(table_obj) -> str:
    if isinstance(table_obj, str):
        return table_obj
    return table_obj.ref


def split_sheet_ref(ref: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not ref or "!" not in ref:
        return None, None
    sheet, rng = ref.split("!", 1)
    sheet = sheet.strip("'").replace("''", "'")
    rng = rng.replace("$", "")
    return sheet, rng


def read_ref_values(wb, ref: Optional[str]) -> List[object]:
    sheet_name, rng = split_sheet_ref(ref)
    if not sheet_name or not rng or sheet_name not in wb.sheetnames:
        return []
    ws = wb[sheet_name]
    if ":" not in rng:
        return [ws[rng].value]
    min_col, min_row, max_col, max_row = range_boundaries(rng)
    vals: List[object] = []
    for row in ws.iter_rows(
        min_row=min_row,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
        values_only=True,
    ):
        vals.extend(list(row))
    return vals


def chart_title(chart) -> str:
    try:
        return chart.title.tx.rich.p[0].r[0].t
    except Exception:
        return "chart"


def get_pathway_selection_info(workbook_path: Path) -> PathwaySelectionInfo:
    wb = load_workbook(workbook_path, data_only=False, read_only=False)
    try:
        ws = wb["PATHWAYS selection"]
        if "PathwaysSelection" not in ws.tables:
            raise ValueError("Table 'PathwaysSelection' not found in PATHWAYS selection.")
        psel_ref = table_ref(ws.tables["PathwaysSelection"])
        min_col, min_row, max_col, max_row = range_boundaries(psel_ref)
        headers = [ws.cell(min_row, c).value for c in range(min_col, max_col + 1)]
        normalized = [str(h).strip().lower() if h is not None else "" for h in headers]

        if "selection" not in normalized or "pathway" not in normalized:
            raise ValueError("PathwaysSelection table must include 'SELECTION' and 'PATHWAY' headers.")

        selection_col_idx = min_col + normalized.index("selection")
        pathway_col_idx = min_col + normalized.index("pathway")

        first_data_row = min_row + 1
        last_data_row = max_row
        pathways: List[Tuple[int, str]] = []
        for row in range(first_data_row, last_data_row + 1):
            pathway_name = ws.cell(row, pathway_col_idx).value
            if pathway_name is None or str(pathway_name).strip() == "":
                continue
            pathways.append((row, str(pathway_name).strip()))

        if not pathways:
            raise ValueError("No pathway rows found in PathwaysSelection table.")

        return PathwaySelectionInfo(
            sheet_name="PATHWAYS selection",
            selection_col_idx=selection_col_idx,
            pathway_col_idx=pathway_col_idx,
            first_data_row=first_data_row,
            last_data_row=last_data_row,
            pathways=pathways,
        )
    finally:
        wb.close()


def wait_for_excel_calculation(excel_app, timeout_sec: int = 1800) -> None:
    start = time.time()
    while True:
        state = None
        try:
            state = excel_app.CalculationState
        except Exception:
            state = 1
        if state == 0:  # xlDone
            return
        if time.time() - start > timeout_sec:
            raise TimeoutError("Excel recalculation timed out.")
        time.sleep(0.5)


def extract_output_tables(
    workbook_path: Path,
    pathway_name: str,
    per_pathway_tables_dir: Path,
    combined_tables: Dict[Tuple[str, str], List[pd.DataFrame]],
) -> None:
    wb = load_workbook(workbook_path, data_only=True, read_only=False)
    try:
        for sheet_name in TABLE_OUTPUT_SHEETS:
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            if not ws.tables:
                continue
            for table_name, table_obj in ws.tables.items():
                ref = table_ref(table_obj)
                df = table_to_dataframe(ws, ref)
                if df.empty:
                    continue
                pathway_col = RUN_PATHWAY_COL
                if pathway_col in df.columns:
                    pathway_col = f"_{RUN_PATHWAY_COL}"
                df.insert(0, pathway_col, pathway_name)

                out_dir = per_pathway_tables_dir / safe_name(pathway_name)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"{safe_name(sheet_name)}__{safe_name(table_name)}.csv"
                df.to_csv(out_file, index=False)

                key = (sheet_name, table_name)
                combined_tables.setdefault(key, []).append(df)
    finally:
        wb.close()


def extract_chart_sources(
    workbook_path: Path,
    pathway_name: str,
    per_pathway_charts_dir: Path,
) -> None:
    wb = load_workbook(workbook_path, data_only=True, read_only=False)
    try:
        for sheet_name in CHART_OUTPUT_SHEETS:
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            charts = getattr(ws, "_charts", [])
            if not charts:
                continue

            for chart_idx, chart in enumerate(charts, start=1):
                title = chart_title(chart)
                for series_idx, series in enumerate(chart.series, start=1):
                    val_ref = getattr(getattr(series, "val", None), "numRef", None)
                    cat_ref = getattr(getattr(series, "cat", None), "numRef", None) or getattr(
                        getattr(series, "cat", None), "strRef", None
                    )
                    val_formula = val_ref.f if val_ref is not None else None
                    cat_formula = cat_ref.f if cat_ref is not None else None

                    values = read_ref_values(wb, val_formula)
                    categories = read_ref_values(wb, cat_formula)
                    row_count = max(len(values), len(categories), 1)

                    padded_values = values + [None] * (row_count - len(values))
                    padded_categories = categories + [None] * (row_count - len(categories))

                    df = pd.DataFrame(
                        {
                            RUN_PATHWAY_COL: [pathway_name] * row_count,
                            "Sheet": [sheet_name] * row_count,
                            "ChartIndex": [chart_idx] * row_count,
                            "ChartTitle": [title] * row_count,
                            "SeriesIndex": [series_idx] * row_count,
                            "CategoryRef": [cat_formula] * row_count,
                            "ValueRef": [val_formula] * row_count,
                            "Category": padded_categories,
                            "Value": padded_values,
                        }
                    )

                    out_dir = per_pathway_charts_dir / safe_name(pathway_name) / safe_name(sheet_name)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_name = (
                        f"chart_{chart_idx:02d}_{safe_name(title)}__series_{series_idx:02d}.csv"
                    )
                    df.to_csv(out_dir / out_name, index=False)
    finally:
        wb.close()


def export_combined_tables(
    combined_tables: Dict[Tuple[str, str], List[pd.DataFrame]],
    combined_dir: Path,
) -> None:
    combined_dir.mkdir(parents=True, exist_ok=True)
    for (sheet_name, table_name), frames in combined_tables.items():
        if not frames:
            continue
        all_df = pd.concat(frames, ignore_index=True)
        out_name = f"{safe_name(sheet_name)}__{safe_name(table_name)}__all_pathways.csv"
        all_df.to_csv(combined_dir / out_name, index=False)


def run_all_pathways(
    workbook_path: Path,
    output_root: Path,
    max_pathways: Optional[int] = None,
    excel_visible: bool = False,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
) -> Path:
    print(f"Starting all-pathways run for: {workbook_path}", flush=True)
    print(f"Outputs root: {output_root}", flush=True)
    selection = get_pathway_selection_info(workbook_path)
    pathways = selection.pathways[:max_pathways] if max_pathways else selection.pathways

    run_dir = output_root / f"all_pathways_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workbooks_dir = run_dir / "workbooks"
    tables_dir = run_dir / "tables_per_pathway"
    charts_dir = run_dir / "charts_per_pathway"
    combined_tables_dir = run_dir / "combined_tables"
    for d in (workbooks_dir, tables_dir, charts_dir, combined_tables_dir):
        d.mkdir(parents=True, exist_ok=True)

    combined_tables: Dict[Tuple[str, str], List[pd.DataFrame]] = {}
    manifest_rows: List[dict] = []

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = bool(excel_visible)
    excel.DisplayAlerts = False
    excel.AskToUpdateLinks = False

    com_wb = None
    try:
        com_wb = excel.Workbooks.Open(str(workbook_path.resolve()), UpdateLinks=0, ReadOnly=False)
        sheet = com_wb.Worksheets(selection.sheet_name)
        selection_col_letter = get_column_letter(selection.selection_col_idx)
        clear_range = (
            f"{selection_col_letter}{selection.first_data_row}:"
            f"{selection_col_letter}{selection.last_data_row}"
        )

        for i, (row_num, pathway_name) in enumerate(pathways, start=1):
            print(f"[{i}/{len(pathways)}] Running pathway: {pathway_name}")
            if progress_callback is not None:
                try:
                    progress_callback(i, len(pathways), pathway_name, "running")
                except Exception:
                    pass
            start = time.time()
            entry = {
                "Pathway": pathway_name,
                "Row": row_num,
                "Status": "ok",
                "WorkbookFile": "",
                "Error": "",
            }
            try:
                sheet.Range(clear_range).Value = ""
                sheet.Cells(row_num, selection.selection_col_idx).Value = "x"
                excel.CalculateFullRebuild()
                wait_for_excel_calculation(excel)

                out_wb_name = f"{i:02d}_{safe_name(pathway_name)}{workbook_path.suffix}"
                out_wb_path = workbooks_dir / out_wb_name
                com_wb.SaveCopyAs(str(out_wb_path.resolve()))
                entry["WorkbookFile"] = str(out_wb_path.resolve())

                extract_output_tables(
                    out_wb_path,
                    pathway_name=pathway_name,
                    per_pathway_tables_dir=tables_dir,
                    combined_tables=combined_tables,
                )
                extract_chart_sources(
                    out_wb_path,
                    pathway_name=pathway_name,
                    per_pathway_charts_dir=charts_dir,
                )
            except Exception as exc:
                entry["Status"] = "failed"
                entry["Error"] = str(exc)
            finally:
                entry["Seconds"] = round(time.time() - start, 2)
                manifest_rows.append(entry)
    finally:
        if com_wb is not None:
            com_wb.Close(SaveChanges=False)
        excel.Quit()

    export_combined_tables(combined_tables, combined_tables_dir)
    deviation_csv = run_dir / DEVIATION_SUMMARY_FILE
    try:
        deviation_df = export_scenario_deviation_summary(
            combined_dir=combined_tables_dir,
            output_csv=deviation_csv,
        )
        print(
            f"Scenario deviation summary saved: {deviation_csv} "
            f"(rows={len(deviation_df)})",
            flush=True,
        )
    except Exception as exc:
        print(
            f"Warning: scenario deviation summary failed: {exc}",
            flush=True,
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(run_dir / "run_manifest.csv", index=False)
    if progress_callback is not None:
        try:
            progress_callback(len(pathways), len(pathways), "Done", "done")
        except Exception:
            pass
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run all pathways in a FABLE workbook and export per-pathway workbook, "
            "tables, and chart sources."
        )
    )
    parser.add_argument(
        "--workbook",
        required=True,
        help="Path to the source FABLE workbook (.xlsx/.xlsm).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory root. Default: <workbook_dir>/exports",
    )
    parser.add_argument(
        "--max-pathways",
        type=int,
        default=None,
        help="Optional limit for testing (runs first N pathways only).",
    )
    parser.add_argument(
        "--excel-visible",
        action="store_true",
        help="Show Excel window (useful for debugging prompts).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workbook_path = Path(args.workbook).expanduser().resolve()
    if not workbook_path.exists():
        raise SystemExit(f"Workbook not found: {workbook_path}")

    output_root = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else workbook_path.parent / "exports"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    run_dir = run_all_pathways(
        workbook_path=workbook_path,
        output_root=output_root,
        max_pathways=args.max_pathways,
        excel_visible=args.excel_visible,
    )
    print(f"Done. Outputs written to: {run_dir}")


if __name__ == "__main__":
    main()
