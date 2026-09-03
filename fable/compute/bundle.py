"""Build a :class:`~fable.compute.model.Bundle` from a CSV run directory.

Pure Python + pandas. No spreadsheet engine. This is the half of the pipeline
that must never crash on bad input: a missing table, a failed pathway, or an
absent deviation summary each degrade the bundle rather than raise.

A "CSV run directory" is whatever the recalc engines write, matching the legacy
``src/runner.py`` layout::

    <run_dir>/
        run_manifest.csv                     # Pathway,Row,Status,Error,Seconds
        scenario_deviation_summary.csv       # optional; regenerated if absent
        combined_tables/
            <SHEET>__<Table>__all_pathways.csv
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .deviation import (
    DEFAULT_BASELINE_PATHWAY,
    choose_baseline_pathway,
    detect_pathway_col,
    detect_year_col,
    export_scenario_deviation_summary,
)
from .model import (
    Bundle,
    Grid,
    PathwayFailure,
    QualityCheck,
    RunQuality,
    Source,
    Table,
    _clean,
)

COMBINED_SUFFIX = "__all_pathways.csv"
DEVIATION_SUMMARY_FILE = "scenario_deviation_summary.csv"
MANIFEST_FILE = "run_manifest.csv"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rows_as_lists(df: pd.DataFrame) -> List[list]:
    # object dtype so a column can hold mixed str / float / None cleanly
    return [[_clean(v) for v in rec] for rec in df.astype(object).to_records(index=False)]


def _classify_columns(df: pd.DataFrame, pathway_col: str):
    year_col = detect_year_col(df.columns.tolist())
    dimension_cols = [
        c
        for c in df.columns
        if c != pathway_col and (df[c].dtype == object or c == year_col)
    ]
    numeric_cols: List[str] = []
    for c in df.columns:
        if c == pathway_col or c in dimension_cols:
            continue
        if pd.to_numeric(df[c], errors="coerce").notna().any():
            numeric_cols.append(c)
    return year_col, dimension_cols, numeric_cols


def _table_from_csv(path: Path) -> Optional[Table]:
    stem = path.name[: -len(COMBINED_SUFFIX)] if path.name.endswith(COMBINED_SUFFIX) else path.stem
    sheet, _, table = stem.partition("__")
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if df.empty:
        return None
    df.columns = [str(c) for c in df.columns]
    pathway_col = detect_pathway_col(df.columns.tolist())
    if pathway_col is None:
        return None
    year_col, dimension_cols, numeric_cols = _classify_columns(df, pathway_col)
    return Table(
        key=stem,
        sheet=sheet or stem,
        table=table or stem,
        columns=df.columns.tolist(),
        rows=_rows_as_lists(df),
        pathway_col=pathway_col,
        year_col=year_col,
        dimension_cols=dimension_cols,
        numeric_cols=numeric_cols,
    )


def _ordered_pathways(tables: List[Table], manifest: Optional[pd.DataFrame]) -> List[str]:
    seen: List[str] = []
    if manifest is not None and "Pathway" in manifest.columns:
        for name in manifest["Pathway"].tolist():
            name = str(name).strip()
            if name and name not in seen:
                seen.append(name)
    for t in tables:
        idx = t.columns.index(t.pathway_col)
        for row in t.rows:
            name = row[idx]
            if isinstance(name, str) and name and name not in seen:
                seen.append(name)
    return seen


def _load_manifest(run_dir: Path) -> Optional[pd.DataFrame]:
    p = run_dir / MANIFEST_FILE
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def _run_quality(
    manifest: Optional[pd.DataFrame],
    pathways: List[str],
    tables: List[Table],
    baseline: str,
) -> RunQuality:
    failures: List[PathwayFailure] = []
    ok_count = len(pathways)
    expected = len(pathways)

    if manifest is not None and "Status" in manifest.columns:
        expected = len(manifest)
        ok_count = 0
        for _, r in manifest.iterrows():
            status = str(r.get("Status", "")).strip().lower()
            if status == "ok":
                ok_count += 1
            else:
                failures.append(
                    PathwayFailure(
                        pathway=str(r.get("Pathway", "?")),
                        error=str(r.get("Error", "") or "unknown"),
                    )
                )

    checks = [
        QualityCheck("has_pathways", bool(pathways), f"{len(pathways)} pathway(s)"),
        QualityCheck("has_tables", bool(tables), f"{len(tables)} table(s)"),
        QualityCheck(
            "baseline_present",
            baseline in pathways,
            f"baseline={baseline!r}",
        ),
        QualityCheck(
            "min_two_pathways",
            len(pathways) >= 2,
            "deviation analysis needs >= 2 pathways",
        ),
        QualityCheck(
            "all_tables_nonempty",
            all(t.row_count > 0 for t in tables),
            f"{sum(1 for t in tables if t.row_count == 0)} empty",
        ),
        QualityCheck(
            "all_pathways_ok",
            not failures,
            f"{len(failures)} failed" if failures else "",
        ),
    ]

    q = RunQuality(
        pathways_expected=expected,
        pathways_ok=ok_count,
        pathways_failed=len(failures),
        failures=failures,
        checks=checks,
    )
    q.recompute_status()
    return q


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------
def build_bundle(
    run_dir: Path,
    *,
    workbook_path: Optional[Path] = None,
    country: str = "Unknown",
    recalc_engine: str = "precomputed-csv",
    baseline_pathway: Optional[str] = DEFAULT_BASELINE_PATHWAY,
    generator: str = "",
    regenerate_deviation: bool = True,
) -> Bundle:
    """Read ``run_dir`` and return a :class:`Bundle`. Never raises on bad data."""
    run_dir = Path(run_dir)
    combined_dir = run_dir / "combined_tables"

    tables: List[Table] = []
    for csv_path in sorted(combined_dir.glob(f"*{COMBINED_SUFFIX}")):
        t = _table_from_csv(csv_path)
        if t is not None:
            tables.append(t)

    manifest = _load_manifest(run_dir)
    pathways = _ordered_pathways(tables, manifest)
    baseline = (
        choose_baseline_pathway(pathways, baseline_pathway)
        if pathways
        else (baseline_pathway or DEFAULT_BASELINE_PATHWAY)
    )

    # deviation summary: regenerate from the combined CSVs (single source of
    # truth) and fall back to a pre-existing file, then to empty. Regeneration
    # goes to a temp file so the run directory is never mutated here.
    dev_df: Optional[pd.DataFrame] = None
    if regenerate_deviation and combined_dir.is_dir():
        try:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=True) as tmp:
                dev_df = export_scenario_deviation_summary(
                    combined_dir=combined_dir,
                    output_csv=Path(tmp.name),
                    baseline_pathway=baseline,
                )
        except Exception:
            dev_df = None
    existing_dev = run_dir / DEVIATION_SUMMARY_FILE
    if dev_df is None and existing_dev.exists():
        try:
            dev_df = pd.read_csv(existing_dev)
        except Exception:
            dev_df = None
    if dev_df is None:
        dev_df = pd.DataFrame()
    dev_df.columns = [str(c) for c in dev_df.columns]
    deviation_summary = Grid(
        columns=dev_df.columns.tolist(),
        rows=_rows_as_lists(dev_df) if not dev_df.empty else [],
    )

    run_quality = _run_quality(manifest, pathways, tables, baseline)

    wb_path = Path(workbook_path) if workbook_path else None
    source = Source(
        workbook_filename=wb_path.name if wb_path else "unknown.xlsx",
        workbook_sha256=sha256_file(wb_path) if wb_path and wb_path.exists() else "",
        country=country,
        recalc_engine=recalc_engine,
        run_id=run_dir.name,
    )

    return Bundle(
        source=source,
        pathways=pathways,
        baseline_pathway=baseline,
        tables=tables,
        deviation_summary=deviation_summary,
        run_quality=run_quality,
        generator=generator,
    )
