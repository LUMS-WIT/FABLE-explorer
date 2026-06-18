#!/usr/bin/env python
"""
Shared pathway-comparison helpers for the runner and dashboard.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

RUN_PATHWAY_COL = "RunPathway"
DEFAULT_BASELINE_PATHWAY = "CurrentTrends"


def safe_name(text: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("._")
    return cleaned or "unnamed"


def detect_pathway_col(columns: Sequence[object]) -> Optional[str]:
    if RUN_PATHWAY_COL in columns:
        return RUN_PATHWAY_COL
    prefixed = f"_{RUN_PATHWAY_COL}"
    if prefixed in columns:
        return prefixed
    return None


def detect_year_col(columns: Sequence[object]) -> Optional[str]:
    for column in columns:
        if str(column).strip().lower() == "year":
            return str(column)
    return None


def choose_baseline_pathway(
    pathway_names: Sequence[object],
    preferred: Optional[str] = None,
) -> str:
    available = sorted(
        [pathway for pathway in pathway_names if pd.notna(pathway)],
        key=lambda value: str(value),
    )
    if not available:
        raise ValueError("At least one pathway is required for comparison.")
    if preferred in available:
        return str(preferred)
    if DEFAULT_BASELINE_PATHWAY in available:
        return DEFAULT_BASELINE_PATHWAY
    return str(available[0])


def metric_thresholds_for(
    metric: str,
    default_abs_threshold: float,
    default_pct_threshold: float,
    metric_thresholds: Optional[Dict[str, Dict[str, float]]],
) -> Tuple[float, float]:
    spec = (metric_thresholds or {}).get(metric, {})
    abs_thr = float(spec.get("abs", default_abs_threshold))
    pct_thr = float(spec.get("pct", default_pct_threshold))
    return abs_thr, pct_thr


def group_text(row: pd.Series, dims: List[str]) -> str:
    if not dims:
        return "(all rows)"
    parts: List[str] = []
    for dim in dims:
        value = row.get(dim, None)
        if pd.isna(value):
            value = "<NA>"
        parts.append(f"{dim}={value}")
    return " | ".join(parts)


def _rowwise_idxmax(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="object")
    valid_rows = frame.notna().any(axis=1)
    result = frame.fillna(float("-inf")).idxmax(axis=1)
    return result.where(valid_rows)


def _rowwise_idxmin(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="object")
    valid_rows = frame.notna().any(axis=1)
    result = frame.fillna(float("inf")).idxmin(axis=1)
    return result.where(valid_rows)


def safe_pct_delta(
    values: pd.Series,
    baseline_values: pd.Series,
) -> pd.Series:
    diff = values - baseline_values
    baseline_abs = baseline_values.abs()
    pct = diff.divide(baseline_abs.replace(0, float("nan"))).mul(100.0)
    pct = pct.mask(baseline_abs.eq(0) & diff.eq(0), other=0.0)
    return pct


def safe_pct_delta_frame(
    values: pd.DataFrame,
    baseline_values: pd.Series,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    diff = values.sub(baseline_values, axis=0)
    baseline_abs = baseline_values.abs()
    pct = diff.divide(baseline_abs.replace(0, float("nan")), axis=0).mul(100.0)
    undefined = pd.DataFrame(False, index=values.index, columns=values.columns)

    for column in values.columns:
        same_as_baseline = diff[column].eq(0)
        zero_baseline = baseline_abs.eq(0)
        pct.loc[zero_baseline & same_as_baseline, column] = 0.0
        undefined[column] = zero_baseline & diff[column].ne(0)

    return pct, undefined


def apply_baseline_mode(
    df: pd.DataFrame,
    pathway_col: str,
    key_cols: List[str],
    metric: str,
    baseline: str,
    mode: str,
) -> pd.DataFrame:
    out = df.copy()
    merge_key_cols = key_cols[:] if key_cols else ["__all_rows__"]
    if "__all_rows__" in merge_key_cols:
        out["__all_rows__"] = 0

    baseline_rows = out[out[pathway_col] == baseline][merge_key_cols + [metric]].copy()
    if baseline_rows.empty:
        out["_baseline"] = float("nan")
    else:
        baseline_rows = baseline_rows.groupby(
            merge_key_cols,
            dropna=False,
            as_index=False,
        )[metric].sum()
        baseline_rows = baseline_rows.rename(columns={metric: "_baseline"})
        out = out.merge(baseline_rows, on=merge_key_cols, how="left")

    if mode == "Delta":
        out[metric] = out[metric] - out["_baseline"]
    elif mode == "% Delta":
        out[metric] = safe_pct_delta(out[metric], out["_baseline"])

    if "__all_rows__" in out.columns:
        out = out.drop(columns=["__all_rows__"])
    return out


def export_scenario_deviation_summary(
    combined_dir: Path,
    output_csv: Path,
    baseline_pathway: Optional[str] = DEFAULT_BASELINE_PATHWAY,
    default_abs_threshold: float = 0.0,
    default_pct_threshold: float = 15.0,
    metric_thresholds: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.DataFrame:
    table_paths = sorted(combined_dir.glob("*.csv"))
    summary_frames: List[pd.DataFrame] = []

    for path in table_paths:
        table_name = path.stem.replace("__all_pathways", "")
        df = pd.read_csv(path)
        if df.empty:
            continue

        pathway_col = detect_pathway_col(df.columns.tolist())
        if pathway_col is None:
            continue

        year_col = detect_year_col(df.columns.tolist())
        dimension_cols = [
            column
            for column in df.columns
            if column != pathway_col and (df[column].dtype == object or column == year_col)
        ]

        numeric_cols: List[str] = []
        for column in df.columns:
            if column == pathway_col or column in dimension_cols:
                continue
            series = pd.to_numeric(df[column], errors="coerce")
            if series.notna().any():
                df[column] = series
                numeric_cols.append(column)
        if not numeric_cols:
            continue

        for metric in numeric_cols:
            cols = dimension_cols + [pathway_col, metric]
            work = df[cols].copy()
            work[metric] = pd.to_numeric(work[metric], errors="coerce")
            work = work.dropna(subset=[pathway_col, metric])
            if work.empty:
                continue

            expected_pathways = sorted(
                work[pathway_col].dropna().unique().tolist(),
                key=lambda value: str(value),
            )
            if len(expected_pathways) < 2:
                continue

            agg = work.groupby(
                dimension_cols + [pathway_col],
                dropna=False,
                as_index=False,
            )[metric].sum()
            if agg.empty:
                continue

            if dimension_cols:
                pivot = agg.pivot_table(
                    index=dimension_cols,
                    columns=pathway_col,
                    values=metric,
                    aggfunc="sum",
                ).reset_index()
            else:
                totals = agg.groupby(pathway_col, as_index=False)[metric].sum()
                if totals.empty:
                    continue
                pivot = pd.DataFrame([totals.set_index(pathway_col)[metric].to_dict()])

            for pathway_name in expected_pathways:
                if pathway_name not in pivot.columns:
                    pivot[pathway_name] = pd.NA

            pivot.columns.name = None
            values = pivot[expected_pathways].apply(pd.to_numeric, errors="coerce")
            baseline = choose_baseline_pathway(expected_pathways, baseline_pathway)
            baseline_values = pd.to_numeric(pivot[baseline], errors="coerce")

            diff_vs_baseline = values.sub(baseline_values, axis=0)
            pct_diff_vs_baseline, undefined_pct = safe_pct_delta_frame(
                values,
                baseline_values,
            )

            max_values = values.max(axis=1)
            min_values = values.min(axis=1)
            spread_abs = max_values - min_values
            mean_abs = values.abs().mean(axis=1)
            spread_pct = spread_abs.divide(mean_abs.replace(0, pd.NA)).mul(100.0)
            spread_pct = spread_pct.where(mean_abs > 0)

            present_counts = values.notna().sum(axis=1)
            expected_count = len(expected_pathways)
            incomplete_coverage = present_counts < expected_count
            missing_pathways = values.isna().apply(
                lambda row: " | ".join(
                    str(pathway_name)
                    for pathway_name, is_missing in row.items()
                    if bool(is_missing)
                ),
                axis=1,
            )

            compare_cols = [name for name in expected_pathways if name != baseline]
            if compare_cols:
                abs_diff_non_base = diff_vs_baseline[compare_cols].abs()
                pct_diff_non_base = pct_diff_vs_baseline[compare_cols].abs()
                undefined_non_base = undefined_pct[compare_cols]
                max_abs_diff = abs_diff_non_base.max(axis=1)
                max_pct_diff = pct_diff_non_base.max(axis=1)
                max_diff_pathway = _rowwise_idxmax(abs_diff_non_base)
                has_undefined_pct = undefined_non_base.any(axis=1).astype(bool)
            else:
                max_abs_diff = pd.Series(0.0, index=pivot.index)
                max_pct_diff = pd.Series(0.0, index=pivot.index)
                max_diff_pathway = pd.Series(baseline, index=pivot.index, dtype="object")
                has_undefined_pct = pd.Series(False, index=pivot.index)

            abs_thr, pct_thr = metric_thresholds_for(
                metric=metric,
                default_abs_threshold=default_abs_threshold,
                default_pct_threshold=default_pct_threshold,
                metric_thresholds=metric_thresholds,
            )
            max_abs_diff_num = pd.to_numeric(max_abs_diff, errors="coerce")
            max_pct_diff_num = pd.to_numeric(max_pct_diff, errors="coerce")
            pct_threshold_pass = (
                max_pct_diff_num.fillna(0.0).ge(pct_thr) | has_undefined_pct
            )
            significant = (
                ~incomplete_coverage
                & max_abs_diff_num.fillna(0.0).ge(abs_thr)
                & pct_threshold_pass
            )

            out = (
                pivot[dimension_cols].copy()
                if dimension_cols
                else pd.DataFrame(index=pivot.index)
            )
            out.insert(0, "Table", table_name)
            out.insert(1, "Metric", metric)
            out["Group"] = (
                out.apply(lambda row: group_text(row, dimension_cols), axis=1)
                if dimension_cols
                else "(all rows)"
            )
            out["BaselinePathway"] = baseline
            out["BaselineValue"] = baseline_values
            out["MaxPathway"] = _rowwise_idxmax(values)
            out["MaxValue"] = max_values
            out["MinPathway"] = _rowwise_idxmin(values)
            out["MinValue"] = min_values
            out["SpreadAbs"] = spread_abs
            out["SpreadPct"] = spread_pct
            out["MaxDiffPathway"] = max_diff_pathway
            out["MaxAbsDiffVsBaseline"] = max_abs_diff_num
            out["MaxPctDiffVsBaseline"] = max_pct_diff_num
            out["HasUndefinedPctDiff"] = has_undefined_pct
            out["ExpectedPathwayCount"] = expected_count
            out["PresentPathwayCount"] = present_counts
            out["IncompleteCoverage"] = incomplete_coverage
            out["MissingPathways"] = missing_pathways
            out["AbsDeviationThreshold"] = abs_thr
            out["PctDeviationThreshold"] = pct_thr
            out["SignificantDeviation"] = significant

            for pathway_name in expected_pathways:
                column_name = safe_name(pathway_name)
                out[f"Value__{column_name}"] = pd.to_numeric(
                    pivot[pathway_name],
                    errors="coerce",
                )
                out[f"DiffVsBaseline__{column_name}"] = diff_vs_baseline[pathway_name]
                out[f"PctDiffVsBaseline__{column_name}"] = pct_diff_vs_baseline[
                    pathway_name
                ]

            summary_frames.append(out)

    if summary_frames:
        summary_df = pd.concat(summary_frames, ignore_index=True)
        summary_df = summary_df.sort_values(
            [
                "SignificantDeviation",
                "MaxPctDiffVsBaseline",
                "MaxAbsDiffVsBaseline",
                "SpreadPct",
                "SpreadAbs",
            ],
            ascending=[False, False, False, False, False],
        )
    else:
        summary_df = pd.DataFrame(
            columns=[
                "Table",
                "Metric",
                "Group",
                "BaselinePathway",
                "BaselineValue",
                "MaxPathway",
                "MaxValue",
                "MinPathway",
                "MinValue",
                "SpreadAbs",
                "SpreadPct",
                "MaxDiffPathway",
                "MaxAbsDiffVsBaseline",
                "MaxPctDiffVsBaseline",
                "HasUndefinedPctDiff",
                "ExpectedPathwayCount",
                "PresentPathwayCount",
                "IncompleteCoverage",
                "MissingPathways",
                "AbsDeviationThreshold",
                "PctDeviationThreshold",
                "SignificantDeviation",
            ]
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_csv, index=False)
    return summary_df
