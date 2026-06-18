#!/usr/bin/env python
"""
Streamlit dashboard for exploring FableVisualizerV4 all-pathways outputs.

Run:
  streamlit run FableVisualizerV4_Dashboard.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from FableVisualizerV4_Comparison import (
    DEFAULT_BASELINE_PATHWAY,
    apply_baseline_mode,
    choose_baseline_pathway,
    detect_pathway_col,
    detect_year_col,
    export_scenario_deviation_summary,
    safe_name,
)

DEVIATION_SUMMARY_FILE = "scenario_deviation_summary.csv"


def find_run_dirs(search_root: Path, max_depth: int = 4) -> List[Path]:
    if not search_root.exists():
        return []
    runs: List[Path] = []
    root = search_root.resolve()
    for dirpath, dirnames, _ in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) > max_depth:
            dirnames[:] = []
            continue
        name = Path(dirpath).name
        if name.startswith("all_pathways_run_"):
            runs.append(Path(dirpath))
            dirnames[:] = []
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs

@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_table(run_dir: Path, table_name: str) -> Optional[pd.DataFrame]:
    path = run_dir / "combined_tables" / f"{table_name}__all_pathways.csv"
    if not path.exists():
        return None
    return load_csv(path)


def prepare_curated_chart_df(
    df: pd.DataFrame,
    year_col: str,
    numeric_cols: List[str],
) -> pd.DataFrame:
    out = df.copy()
    for column in [year_col] + numeric_cols:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=[year_col])
    return out

def compute_deviation_summary(
    run_dir: Path,
    baseline_pathway: Optional[str] = DEFAULT_BASELINE_PATHWAY,
    default_abs_threshold: float = 0.0,
    default_pct_threshold: float = 15.0,
) -> Tuple[pd.DataFrame, Path]:
    combined_dir = run_dir / "combined_tables"
    output_csv = run_dir / DEVIATION_SUMMARY_FILE
    summary_df = export_scenario_deviation_summary(
        combined_dir=combined_dir,
        output_csv=output_csv,
        baseline_pathway=baseline_pathway,
        default_abs_threshold=default_abs_threshold,
        default_pct_threshold=default_pct_threshold,
    )
    return summary_df, output_csv


def build_deviation_candidates(df_summary: pd.DataFrame) -> pd.DataFrame:
    if df_summary.empty:
        return pd.DataFrame()
    if "Table" not in df_summary.columns or "Metric" not in df_summary.columns:
        return pd.DataFrame()

    work = df_summary.copy()
    if "MaxPctDiffVsBaseline" in work.columns:
        work["MaxPctDiffVsBaseline"] = pd.to_numeric(
            work["MaxPctDiffVsBaseline"],
            errors="coerce",
        ).fillna(0.0)
    else:
        work["MaxPctDiffVsBaseline"] = pd.to_numeric(
            work.get("SpreadPct", 0.0),
            errors="coerce",
        ).fillna(0.0)
    if "MaxAbsDiffVsBaseline" in work.columns:
        work["MaxAbsDiffVsBaseline"] = pd.to_numeric(
            work["MaxAbsDiffVsBaseline"],
            errors="coerce",
        ).fillna(0.0)
    else:
        work["MaxAbsDiffVsBaseline"] = pd.to_numeric(
            work.get("SpreadAbs", 0.0),
            errors="coerce",
        ).fillna(0.0)
    if "SignificantDeviation" in work.columns:
        work["SignificantDeviation"] = work["SignificantDeviation"].astype(str).str.lower().isin(
            ["true", "1", "yes"]
        )
    else:
        work["SignificantDeviation"] = False
    if "IncompleteCoverage" in work.columns:
        work["IncompleteCoverage"] = work["IncompleteCoverage"].astype(str).str.lower().isin(
            ["true", "1", "yes"]
        )
    else:
        work["IncompleteCoverage"] = False

    candidates = (
        work.groupby(["Table", "Metric"], as_index=False)
        .agg(
            MaxBaselinePct=("MaxPctDiffVsBaseline", "max"),
            MaxBaselineAbs=("MaxAbsDiffVsBaseline", "max"),
            SignificantRows=("SignificantDeviation", "sum"),
            IncompleteRows=("IncompleteCoverage", "sum"),
            Rows=("Metric", "size"),
        )
        .sort_values(["MaxBaselinePct", "MaxBaselineAbs"], ascending=[False, False])
    )
    candidates["Label"] = candidates.apply(
        lambda r: (
            f"{r['Table']} | {r['Metric']} | "
            f"max baseline %: {r['MaxBaselinePct']:.2f} | "
            f"significant rows: {int(r['SignificantRows'])} | "
            f"incomplete rows: {int(r['IncompleteRows'])}"
        ),
        axis=1,
    )
    return candidates.reset_index(drop=True)


def build_deviation_figure(
    run_dir: Path,
    summary_df: pd.DataFrame,
    table_name: str,
    metric: str,
) -> Optional[go.Figure]:
    df = load_table(run_dir, table_name)
    if df is None or df.empty or metric not in df.columns:
        return None

    pathway_col = detect_pathway_col(df.columns.tolist())
    if pathway_col is None:
        return None

    year_col = detect_year_col(df.columns.tolist())
    df = df.copy()
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[pathway_col, metric])
    if df.empty:
        return None

    summary_sub = summary_df[
        (summary_df["Table"] == table_name) & (summary_df["Metric"] == metric)
    ].copy()
    if "MaxPctDiffVsBaseline" in summary_sub.columns:
        summary_sub["MaxPctDiffVsBaseline"] = pd.to_numeric(
            summary_sub["MaxPctDiffVsBaseline"], errors="coerce"
        ).fillna(0.0)
    else:
        summary_sub["MaxPctDiffVsBaseline"] = pd.to_numeric(
            summary_sub.get("SpreadPct", 0.0), errors="coerce"
        ).fillna(0.0)
    if "MaxAbsDiffVsBaseline" in summary_sub.columns:
        summary_sub["MaxAbsDiffVsBaseline"] = pd.to_numeric(
            summary_sub["MaxAbsDiffVsBaseline"], errors="coerce"
        ).fillna(0.0)
    else:
        summary_sub["MaxAbsDiffVsBaseline"] = pd.to_numeric(
            summary_sub.get("SpreadAbs", 0.0), errors="coerce"
        ).fillna(0.0)
    if "IncompleteCoverage" in summary_sub.columns:
        summary_sub["IncompleteCoverage"] = summary_sub["IncompleteCoverage"].astype(
            str
        ).str.lower().isin(["true", "1", "yes"])
    else:
        summary_sub["IncompleteCoverage"] = False
    if "SignificantDeviation" in summary_sub.columns:
        summary_sub["SignificantDeviation"] = summary_sub[
            "SignificantDeviation"
        ].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        summary_sub["SignificantDeviation"] = False
    summary_sub = summary_sub.sort_values(
        [
            "SignificantDeviation",
            "IncompleteCoverage",
            "MaxPctDiffVsBaseline",
            "MaxAbsDiffVsBaseline",
        ],
        ascending=[False, True, False, False],
    )

    filtered_df = df.copy()
    if not summary_sub.empty:
        top_row = summary_sub.iloc[0]
        meta_cols = {
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
        }
        filter_cols = [
            c
            for c in summary_sub.columns
            if c not in meta_cols
            and not c.startswith("Value__")
            and not c.startswith("DiffVsBaseline__")
            and not c.startswith("PctDiffVsBaseline__")
            and c != year_col
            and c in filtered_df.columns
        ]
        for col in filter_cols:
            value = top_row[col]
            if pd.isna(value):
                filtered_df = filtered_df[filtered_df[col].isna()]
            else:
                if filtered_df[col].dtype == object:
                    filtered_df = filtered_df[
                        filtered_df[col].astype(str) == str(value)
                    ]
                else:
                    filtered_df = filtered_df[filtered_df[col] == value]

    if filtered_df.empty:
        filtered_df = df

    if year_col and filtered_df[year_col].nunique() > 1:
        plot_df = filtered_df.groupby([pathway_col, year_col], as_index=False)[metric].sum()
        fig = px.line(
            plot_df,
            x=year_col,
            y=metric,
            color=pathway_col,
            markers=True,
            title=f"{table_name} - {metric} (deviation view)",
        )
    else:
        plot_df = filtered_df.groupby([pathway_col], as_index=False)[metric].sum()
        fig = px.bar(
            plot_df,
            x=pathway_col,
            y=metric,
            color=pathway_col,
            barmode="group",
            title=f"{table_name} - {metric} (deviation view)",
        )
    return fig


def filter_pathway(df: pd.DataFrame, pathway: str) -> pd.DataFrame:
    col = detect_pathway_col(df.columns.tolist())
    if col and pathway in df[col].unique().tolist():
        return df[df[col] == pathway].copy()
    return df.copy()


def get_pathways_from_tables(run_dir: Path) -> List[str]:
    for name in [
        "GHG__ResultsGHG",
        "PRODUCTION__TotalResultsProd",
        "JOBS__ResultsJobs",
    ]:
        df = load_table(run_dir, name)
        if df is not None:
            col = detect_pathway_col(df.columns.tolist())
            if col:
                return sorted(df[col].dropna().unique().tolist())
    return []


@st.cache_data(show_spinner=False)
def build_chart_index(run_dir: Path) -> pd.DataFrame:
    base = run_dir / "charts_per_pathway"
    if not base.exists():
        return pd.DataFrame()
    rows: List[Dict[str, str]] = []
    for path in base.rglob("chart_*__series_*.csv"):
        try:
            pathway = path.parent.parent.name
            sheet = path.parent.name
            stem = path.stem
            m = re.match(r"chart_(\d+)_(.*)__series_(\d+)", stem)
            if not m:
                continue
            chart_idx = m.group(1)
            title = m.group(2).replace("_", " ").strip()
            series_idx = m.group(3)
            rows.append(
                {
                    "path": str(path),
                    "pathway": pathway,
                    "sheet": sheet,
                    "chart_idx": chart_idx,
                    "chart_title": title,
                    "series_idx": series_idx,
                }
            )
        except Exception:
            continue
    return pd.DataFrame(rows)


def sidebar_run_selector() -> Optional[Path]:
    st.sidebar.header("Data")
    default_root = Path(__file__).resolve().parents[1]
    search_root = st.sidebar.text_input(
        "Search root for exports", value=str(default_root)
    )
    run_dirs = find_run_dirs(Path(search_root))
    if run_dirs:
        options = ["Latest"] + [str(p) for p in run_dirs]
        choice = st.sidebar.selectbox("Run folder", options)
        if choice == "Latest":
            return run_dirs[0]
        return Path(choice)
    manual = st.sidebar.text_input("Run folder path (manual)")
    return Path(manual) if manual else None


def prep_plot_df(
    df: pd.DataFrame,
    pathway_col: Optional[str],
    year_col: Optional[str],
    category_col: Optional[str],
    category_values: Optional[List[str]],
    pathways: Optional[List[str]],
) -> pd.DataFrame:
    out = df.copy()
    if pathway_col and pathways:
        out = out[out[pathway_col].isin(pathways)]
    if category_col and category_values:
        out = out[out[category_col].isin(category_values)]

    group_cols: List[str] = []
    if pathway_col:
        group_cols.append(pathway_col)
    if year_col:
        group_cols.append(year_col)
    if category_col:
        group_cols.append(category_col)

    # Numeric columns
    numeric_cols: List[str] = []
    for c in out.columns:
        if c in group_cols:
            continue
        if out[c].dtype == object:
            continue
        numeric_cols.append(c)

    # Coerce to numeric where possible
    for c in out.columns:
        if c in group_cols:
            continue
        if out[c].dtype == object:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    numeric_cols = [c for c in out.columns if c not in group_cols and out[c].dtype != object]
    if group_cols:
        out = out.groupby(group_cols, as_index=False)[numeric_cols].sum()
    return out


def build_curated_figures(run_dir: Path, pathway: str) -> List[Tuple[str, go.Figure]]:
    figs: List[Tuple[str, go.Figure]] = []

    # Production costs (stacked bars + total value line)
    df = load_table(run_dir, "PRODUCTION__ResultsProdCosts")
    if df is not None:
        df = filter_pathway(df, pathway)
        year_col = detect_year_col(df.columns.tolist())
        if year_col and not df.empty:
            bar_cols = [
                "FertilizerCost",
                "LabourCost",
                "MachineryRunningCost",
                "DieselCost",
            ]
            line_col = "TotalValue"
            df = prepare_curated_chart_df(df, year_col, bar_cols + [line_col])
            if df.empty:
                pass
            df = df.sort_values(year_col)
            scale = 1000.0
            fig = make_subplots(specs=[[{"secondary_y": False}]])
            for col in bar_cols:
                if col in df.columns:
                    fig.add_bar(
                        x=df[year_col],
                        y=df[col] / scale,
                        name=col,
                    )
            if line_col in df.columns:
                fig.add_scatter(
                    x=df[year_col],
                    y=df[line_col] / scale,
                    mode="lines+markers",
                    name=line_col,
                )
            fig.update_layout(
                title="Evolution of total production costs from the main crops",
                barmode="stack",
            )
            fig.update_yaxes(title_text="billion USD")
            figs.append(("production_costs", fig))

    # Production value (grouped bars)
    df = load_table(run_dir, "PRODUCTION__TotalResultsProd")
    if df is not None:
        df = filter_pathway(df, pathway)
        if "Product" in df.columns:
            df = df[df["Product"] == "TOTAL"]
        year_col = detect_year_col(df.columns.tolist())
        if year_col and not df.empty:
            value_cols = ["prodvusd_hist", "prodvusd_targ", "prodvusd_feas"]
            df = prepare_curated_chart_df(df, year_col, value_cols)
            if df.empty:
                pass
            df = df.sort_values(year_col)
            scale = 1_000_000.0
            fig = go.Figure()
            for col, label in [
                ("prodvusd_hist", "historical prod value"),
                ("prodvusd_targ", "target prod value"),
                ("prodvusd_feas", "feasible prod value"),
            ]:
                if col in df.columns:
                    fig.add_bar(
                        x=df[year_col],
                        y=df[col] / scale,
                        name=label,
                    )
            fig.update_layout(
                title="Production value",
                barmode="group",
                yaxis_title="billion USD",
            )
            figs.append(("production_value", fig))

    # Trade balance
    df = load_table(run_dir, "TRADE__TotalResultsTrade")
    if df is not None:
        df = filter_pathway(df, pathway)
        year_col = detect_year_col(df.columns.tolist())
        if year_col and "TradeBalanceFeas_usd" in df.columns and not df.empty:
            df = prepare_curated_chart_df(df, year_col, ["TradeBalanceFeas_usd"])
            if df.empty:
                pass
            df = df.sort_values(year_col)
            scale = 1_000_000.0
            fig = go.Figure()
            fig.add_bar(
                x=df[year_col],
                y=df["TradeBalanceFeas_usd"] / scale,
                name="Trade balance",
            )
            fig.update_layout(
                title="Trade balance",
                yaxis_title="billion USD",
            )
            figs.append(("trade_balance", fig))

    # Jobs evolution (stacked bars)
    df = load_table(run_dir, "JOBS__ResultsJobs")
    if df is not None:
        df = filter_pathway(df, pathway)
        year_col = detect_year_col(df.columns.tolist())
        if year_col and not df.empty:
            job_cols = [
                "onfarm_crops",
                "onfarm_livestock",
                "sh_agrijobs",
                "histsh_agrijobs",
            ]
            df = prepare_curated_chart_df(df, year_col, job_cols)
            if df.empty:
                pass
            df = df.sort_values(year_col)
            scale = 1000.0
            fig = go.Figure()
            for col, label in [
                ("onfarm_crops", "jobs in crop"),
                ("onfarm_livestock", "jobs in livestock"),
            ]:
                if col in df.columns:
                    fig.add_bar(
                        x=df[year_col],
                        y=df[col] / scale,
                        name=label,
                    )
            fig.update_layout(
                title="Number of full time equivalent (FTE) workers",
                barmode="stack",
                yaxis_title="million workers FTE",
            )
            figs.append(("jobs_evolution", fig))

    # Jobs share (bars + markers)
    if df is not None:
        year_col = detect_year_col(df.columns.tolist())
        if year_col and "sh_agrijobs" in df.columns:
            df = df.sort_values(year_col)
            fig = make_subplots(specs=[[{"secondary_y": False}]])
            fig.add_bar(
                x=df[year_col],
                y=df["sh_agrijobs"] * 100.0,
                name="calc % of on farm jobs in FTE",
            )
            if "histsh_agrijobs" in df.columns:
                fig.add_scatter(
                    x=df[year_col],
                    y=df["histsh_agrijobs"] * 100.0,
                    mode="markers",
                    name="hist % of agri jobs in nb",
                )
            fig.update_layout(
                title="Number of full time equivalent (FTE) workers",
                yaxis_title="percent",
            )
            figs.append(("jobs_share", fig))

    # Food totals (kcal, fat, protein)
    df_total = load_table(run_dir, "FOOD__Total_results_diets")
    if df_total is not None:
        df_total = filter_pathway(df_total, pathway)
        if "PROD_GROUP" in df_total.columns:
            df_total = df_total[df_total["PROD_GROUP"] == "TOTAL"]
        year_col = detect_year_col(df_total.columns.tolist())
        if year_col and not df_total.empty:
            df_total = prepare_curated_chart_df(
                df_total,
                year_col,
                [
                    "kcal_target",
                    "kcal_feas",
                    "kcal_hist",
                    "kcal_MDER",
                    "Kcal_min",
                    "Kcal_max",
                    "fat_target",
                    "fat_feas",
                    "fat_hist",
                    "fat_rec_low",
                    "fat_rec_up",
                    "prot_target",
                    "prot_feas",
                    "prot_hist",
                    "prot_rec_low",
                    "prot_rec_up",
                ],
            )
            if df_total.empty:
                pass
            df_total = df_total.sort_values(year_col)

            # Daily food intake per capita (kcal)
            fig = go.Figure()
            for col, label in [
                ("kcal_target", "kcal target"),
                ("kcal_feas", "kcal feas"),
                ("kcal_hist", "kcal FAO"),
            ]:
                if col in df_total.columns:
                    fig.add_bar(x=df_total[year_col], y=df_total[col], name=label)
            for col, label, style in [
                ("kcal_MDER", "MDER", "dash"),
                ("Kcal_min", "Kcal_min", "solid"),
                ("Kcal_max", "Kcal_max", "solid"),
            ]:
                if col in df_total.columns:
                    fig.add_scatter(
                        x=df_total[year_col],
                        y=df_total[col],
                        mode="lines",
                        name=label,
                        line={"dash": style},
                    )
            fig.update_layout(
                title="Daily food intake per capita",
                barmode="group",
                yaxis_title="kcal per capita per day",
            )
            figs.append(("food_kcal", fig))

            # Daily fat intake per capita
            fig = go.Figure()
            for col, label in [
                ("fat_target", "fat_target"),
                ("fat_feas", "fat_feas"),
                ("fat_hist", "fat_hist"),
            ]:
                if col in df_total.columns:
                    fig.add_bar(x=df_total[year_col], y=df_total[col], name=label)
            for col, label, style in [
                ("fat_rec_low", "fat_rec_low", "dash"),
                ("fat_rec_up", "fat_rec_up", "dot"),
            ]:
                if col in df_total.columns:
                    fig.add_scatter(
                        x=df_total[year_col],
                        y=df_total[col],
                        mode="lines",
                        name=label,
                        line={"dash": style},
                    )
            fig.update_layout(
                title="Daily fat intake per capita",
                barmode="group",
                yaxis_title="grammes p.c per day",
            )
            figs.append(("food_fat", fig))

            # Daily protein intake per capita
            fig = go.Figure()
            for col, label in [
                ("prot_target", "prot_target"),
                ("prot_feas", "prot_feas"),
                ("prot_hist", "prot_hist"),
            ]:
                if col in df_total.columns:
                    fig.add_bar(x=df_total[year_col], y=df_total[col], name=label)
            for col, label, style in [
                ("prot_rec_low", "prot_rec_low", "dash"),
                ("prot_rec_up", "prot_rec_up", "dot"),
            ]:
                if col in df_total.columns:
                    fig.add_scatter(
                        x=df_total[year_col],
                        y=df_total[col],
                        mode="lines",
                        name=label,
                        line={"dash": style},
                    )
            fig.update_layout(
                title="Daily protein intake per capita",
                barmode="group",
                yaxis_title="grammes p.c per day",
            )
            figs.append(("food_protein", fig))

    # Food composition (diet mix + reference views)
    df_diets = load_table(run_dir, "FOOD__Results_Diets")
    if df_diets is not None:
        df_diets = filter_pathway(df_diets, pathway)
        year_col = detect_year_col(df_diets.columns.tolist())
        if year_col and "PROD_GROUP" in df_diets.columns and not df_diets.empty:
            df_diets = prepare_curated_chart_df(
                df_diets,
                year_col,
                ["kcal_calc", "kcal_healthy", "kcal_hist"],
            )
            if df_diets.empty:
                pass
            # Diet mix (pie chart, latest modeled year)
            if "kcal_calc" in df_diets.columns:
                latest_year = int(df_diets[year_col].max())
                df_mix = (
                    df_diets[df_diets[year_col] == latest_year]
                    .copy()
                    .groupby("PROD_GROUP", as_index=False)["kcal_calc"]
                    .sum()
                )
                df_mix["kcal_calc"] = pd.to_numeric(df_mix["kcal_calc"], errors="coerce")
                df_mix = df_mix.dropna(subset=["kcal_calc"])
                df_mix = df_mix[df_mix["kcal_calc"] > 0]
                if not df_mix.empty:
                    fig = px.pie(
                        df_mix,
                        names="PROD_GROUP",
                        values="kcal_calc",
                        title=f"Diet mix ({latest_year})",
                    )
                    fig.update_traces(textposition="inside", textinfo="percent+label")
                    figs.append(("diet_mix_pie", fig))

            # Composition of healthy food consumption (single year)
            if "kcal_healthy" in df_diets.columns:
                latest_year = int(df_diets[year_col].max())
                df_h = df_diets[df_diets[year_col] == latest_year]
                fig = px.bar(
                    df_h,
                    x=[str(latest_year)] * len(df_h),
                    y="kcal_healthy",
                    color="PROD_GROUP",
                    barmode="stack",
                    title="Composition of healthy food consumption",
                )
                fig.update_yaxes(title_text="kcal per capita per day")
                figs.append(("food_healthy", fig))

            # Historical composition (2000-2010)
            if "kcal_hist" in df_diets.columns:
                df_hist = df_diets[df_diets[year_col] <= 2010]
                fig = px.bar(
                    df_hist,
                    x=year_col,
                    y="kcal_hist",
                    color="PROD_GROUP",
                    barmode="stack",
                    title="Historical",
                )
                fig.update_yaxes(title_text="kcal per capita per day")
                figs.append(("food_historical", fig))

    # Biodiversity share (stacked bars + target line)
    df_bio = load_table(run_dir, "BIODIVERSITY__ResultsBiodiv")
    if df_bio is not None:
        df_bio = filter_pathway(df_bio, pathway)
        year_col = detect_year_col(df_bio.columns.tolist())
        if year_col and not df_bio.empty:
            df_bio = prepare_curated_chart_df(
                df_bio,
                year_col,
                [
                    "CalcBiodivForest",
                    "BiodivNewForest",
                    "CalcBiodivOtherLand",
                    "BiodivTarget",
                    "CalcForest",
                    "CalcNewForest",
                    "CalcOtherLand",
                    "CalcBiodivLnd",
                ],
            )
            if df_bio.empty:
                pass
            df_bio = df_bio.sort_values(year_col)
            fig = make_subplots(specs=[[{"secondary_y": False}]])
            for col, label in [
                ("CalcBiodivForest", "Calc Mature Forest Share"),
                ("BiodivNewForest", "Calc Young Forest share"),
                ("CalcBiodivOtherLand", "Calc other land share"),
            ]:
                if col in df_bio.columns:
                    fig.add_bar(
                        x=df_bio[year_col],
                        y=df_bio[col] * 100.0,
                        name=label,
                    )
            if "BiodivTarget" in df_bio.columns:
                fig.add_scatter(
                    x=df_bio[year_col],
                    y=df_bio["BiodivTarget"] * 100.0,
                    mode="lines",
                    name="Biodiv target",
                )
            fig.update_layout(
                title="Evolution of the share of the terrestrial land which can support biodiversity conservation",
                barmode="stack",
                yaxis_title="percent",
            )
            figs.append(("biodiv_share", fig))

            # Land where natural processes predominate
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for col, label in [
                ("CalcForest", "Mature Forest"),
                ("CalcNewForest", "Young Forest"),
                ("CalcOtherLand", "Otherland"),
            ]:
                if col in df_bio.columns:
                    fig.add_bar(
                        x=df_bio[year_col],
                        y=df_bio[col] / 1000.0,
                        name=label,
                    )
            if "CalcBiodivLnd" in df_bio.columns:
                fig.add_scatter(
                    x=df_bio[year_col],
                    y=df_bio["CalcBiodivLnd"] * 100.0,
                    mode="lines+markers",
                    name="Share total land",
                    secondary_y=True,
                )
            fig.update_layout(
                title="Land where natural processes predominate",
                barmode="stack",
            )
            fig.update_yaxes(title_text="million ha", secondary_y=False)
            fig.update_yaxes(title_text="percent", secondary_y=True)
            figs.append(("biodiv_natural", fig))

    # Land cover area in protected areas
    df_prot = load_table(run_dir, "BIODIVERSITY__ResultsProtectedAreas")
    if df_prot is not None:
        df_prot = filter_pathway(df_prot, pathway)
        year_col = detect_year_col(df_prot.columns.tolist())
        if year_col and not df_prot.empty:
            df_prot = prepare_curated_chart_df(
                df_prot,
                year_col,
                ["Forest", "Otherland", "Cropland", "Grassland", "NotRelevant", "ShTotalLand"],
            )
            if df_prot.empty:
                pass
            df_prot = df_prot.sort_values(year_col)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for col in ["Forest", "Otherland", "Cropland", "Grassland", "NotRelevant"]:
                if col in df_prot.columns:
                    fig.add_bar(
                        x=df_prot[year_col],
                        y=df_prot[col] / 1000.0,
                        name=col,
                    )
            if "ShTotalLand" in df_prot.columns:
                fig.add_scatter(
                    x=df_prot[year_col],
                    y=df_prot["ShTotalLand"] * 100.0,
                    mode="lines+markers",
                    name="Share of total land in protected areas",
                    secondary_y=True,
                )
            fig.update_layout(
                title="Land cover area in protected areas",
                barmode="stack",
            )
            fig.update_yaxes(title_text="million ha", secondary_y=False)
            fig.update_yaxes(title_text="percent", secondary_y=True)
            figs.append(("biodiv_protected", fig))

    # Agroecological practices
    df_ag = load_table(run_dir, "BIODIVERSITY__ResultsAgPrac")
    if df_ag is not None:
        df_ag = filter_pathway(df_ag, pathway)
        year_col = detect_year_col(df_ag.columns.tolist())
        if year_col and not df_ag.empty:
            df_ag = prepare_curated_chart_df(
                df_ag,
                year_col,
                [
                    "CalcAgroecoLand",
                    "CalcNonAgroecoLand",
                    "HistCropland",
                    "AgroecoSh",
                ],
            )
            if df_ag.empty:
                pass
            df_ag = df_ag.sort_values(year_col)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for col, label in [
                ("CalcAgroecoLand", "CalcAgroecoLand"),
                ("CalcNonAgroecoLand", "CalcNonAgroecoLand"),
            ]:
                if col in df_ag.columns:
                    fig.add_bar(
                        x=df_ag[year_col],
                        y=df_ag[col] / 1000.0,
                        name=label,
                    )
            if "HistCropland" in df_ag.columns:
                fig.add_scatter(
                    x=df_ag[year_col],
                    y=df_ag["HistCropland"] / 1000.0,
                    mode="markers",
                    name="HistCropland",
                )
            if "AgroecoSh" in df_ag.columns:
                fig.add_scatter(
                    x=df_ag[year_col],
                    y=df_ag["AgroecoSh"] * 100.0,
                    mode="lines+markers",
                    name="AgroecoSh",
                    secondary_y=True,
                )
            fig.update_layout(
                title="Share of cropland with agroecological farming practices",
                barmode="stack",
            )
            fig.update_yaxes(title_text="thousand ha", secondary_y=False)
            fig.update_yaxes(title_text="percent", secondary_y=True)
            figs.append(("biodiv_agroeco", fig))

    # Biodiversity score
    df_score = load_table(run_dir, "BIODIVERSITY__ResultsBioScore")
    if df_score is not None:
        df_score = filter_pathway(df_score, pathway)
        year_col = detect_year_col(df_score.columns.tolist())
        if year_col and not df_score.empty:
            df_score = prepare_curated_chart_df(
                df_score,
                year_col,
                ["CropBioScore", "MeanBioScore"],
            )
            if df_score.empty:
                pass
            df_score = df_score.sort_values(year_col)
            fig = go.Figure()
            for col, label in [
                ("CropBioScore", "Biodiversity on Cropland"),
                ("MeanBioScore", "Overall biodiversity"),
            ]:
                if col in df_score.columns:
                    fig.add_scatter(
                        x=df_score[year_col],
                        y=df_score[col],
                        mode="lines+markers",
                        name=label,
                    )
            fig.update_layout(title="Biodiversity score", yaxis_title="score")
            figs.append(("biodiv_score", fig))

    # Land cover (calc + FAO markers)
    df_land = load_table(run_dir, "LAND__ResultsLand")
    if df_land is not None:
        df_land = filter_pathway(df_land, pathway)
        year_col = detect_year_col(df_land.columns.tolist())
        if year_col and not df_land.empty:
            df_land = prepare_curated_chart_df(
                df_land,
                year_col,
                [
                    "Forest",
                    "NewForest",
                    "OtherLand",
                    "Cropland",
                    "Pasture",
                    "Urban",
                    "FAOForest",
                    "FAOOtherLand",
                    "FAOCropland",
                    "FAOPasture",
                    "MatureForest",
                    "YoungForest",
                    "NetForestChange",
                    "FAOForestChange",
                    "OtherLandChange",
                    "CroplandChange",
                    "PastureChange",
                    "UrbanChange",
                ],
            )
            if df_land.empty:
                pass
            df_land = df_land.sort_values(year_col)
            fig = go.Figure()
            for col, label in [
                ("Forest", "Forest"),
                ("NewForest", "New Forest"),
                ("OtherLand", "OtherLand"),
                ("Cropland", "Cropland"),
                ("Pasture", "Pasture"),
                ("Urban", "Urban"),
            ]:
                if col in df_land.columns:
                    fig.add_scatter(
                        x=df_land[year_col],
                        y=df_land[col] / 1000.0,
                        mode="lines+markers",
                        name=label,
                    )
            for col, label, symbol in [
                ("FAOForest", "Forest_FAO", "triangle-up"),
                ("FAOOtherLand", "Other Land_FAO", "triangle-up"),
                ("FAOCropland", "Cropland_FAO", "triangle-up"),
                ("FAOPasture", "Pasture_FAO", "triangle-up"),
            ]:
                if col in df_land.columns:
                    fig.add_scatter(
                        x=df_land[year_col],
                        y=df_land[col] / 1000.0,
                        mode="markers",
                        name=label,
                        marker={"symbol": symbol},
                    )
            fig.update_layout(
                title="Area by land cover",
                yaxis_title="million ha",
            )
            figs.append(("land_cover", fig))

            # Forest cover change
            df_chg = df_land[df_land[year_col] >= 2005]
            fig = go.Figure()
            for col, label in [
                ("MatureForest", "Mature Forest"),
                ("YoungForest", "Young Forest"),
            ]:
                if col in df_chg.columns:
                    fig.add_bar(
                        x=df_chg[year_col],
                        y=df_chg[col] / 1000.0,
                        name=label,
                    )
            if "NetForestChange" in df_chg.columns:
                fig.add_scatter(
                    x=df_chg[year_col],
                    y=df_chg["NetForestChange"] / 1000.0,
                    mode="lines+markers",
                    name="Net Forest Change",
                )
            if "FAOForestChange" in df_chg.columns:
                fig.add_scatter(
                    x=df_chg[year_col],
                    y=df_chg["FAOForestChange"] / 1000.0,
                    mode="markers",
                    name="Historical Deforestation",
                )
            fig.update_layout(
                title="Forest Cover Change",
                barmode="stack",
                yaxis_title="million ha / 5yr time step",
            )
            figs.append(("forest_change", fig))

            # Land use change
            df_chg = df_land[df_land[year_col] >= 2005]
            fig = go.Figure()
            for col, label in [
                ("NetForestChange", "NetForestChange"),
                ("OtherLandChange", "OtherLandChange"),
                ("CroplandChange", "CroplandChange"),
                ("PastureChange", "PastureChange"),
                ("UrbanChange", "UrbanChange"),
            ]:
                if col in df_chg.columns:
                    fig.add_bar(
                        x=df_chg[year_col],
                        y=df_chg[col] / 1000.0,
                        name=label,
                    )
            fig.update_layout(
                title="Land Use Change",
                barmode="stack",
                yaxis_title="million ha / 5yr time step",
            )
            figs.append(("land_use_change", fig))

    # GHG emissions by sector (stacked bars + FAO markers)
    df_ghg = load_table(run_dir, "GHG__ResultsGHG")
    if df_ghg is not None:
        df_ghg = filter_pathway(df_ghg, pathway)
        year_col = detect_year_col(df_ghg.columns.tolist())
        if year_col and not df_ghg.empty:
            df_ghg = prepare_curated_chart_df(
                df_ghg,
                year_col,
                [
                    "CropCO2e",
                    "LiveCO2e",
                    "DeforCO2",
                    "OtherLandCO2",
                    "BiofuelSavings",
                    "LandSeqReg",
                    "LandSeqAffor",
                    "SOCLandCO2",
                    "SOCAgroecoCO2",
                    "FAOTotalCO2e",
                    "TotalCO2e",
                ],
            )
            if df_ghg.empty:
                pass
            df_ghg = df_ghg.sort_values(year_col)
            fig = go.Figure()
            for col, label in [
                ("CropCO2e", "Crops"),
                ("LiveCO2e", "Livestock"),
                ("DeforCO2", "Deforestation"),
                ("OtherLandCO2", "OtherLandEmissions"),
                ("BiofuelSavings", "Biofuel Savings"),
                ("LandSeqReg", "Sequestr. on abandoned agri. land"),
                ("LandSeqAffor", "Sequestr. on afforested land"),
                ("SOCLandCO2", "Emis/Sequestr. of SOC due to LUC"),
                ("SOCAgroecoCO2", "Sequestr. SOC on agroeco. cropland"),
            ]:
                if col in df_ghg.columns:
                    fig.add_bar(
                        x=df_ghg[year_col],
                        y=df_ghg[col],
                        name=label,
                    )
            if "FAOTotalCO2e" in df_ghg.columns:
                fig.add_scatter(
                    x=df_ghg[year_col],
                    y=df_ghg["FAOTotalCO2e"],
                    mode="markers",
                    name="FAO agriculture",
                )
            fig.update_layout(
                title="Computed GHG by sector",
                barmode="relative",
                yaxis_title="MtCO2eq/yr",
            )
            figs.append(("ghg_sectors", fig))

            # Total GHG line
            if "TotalCO2e" in df_ghg.columns:
                fig = px.line(
                    df_ghg,
                    x=year_col,
                    y="TotalCO2e",
                    markers=True,
                    title="Total GHG emissions (all sectors)",
                )
                fig.update_yaxes(title_text="MtCO2eq/yr")
                figs.append(("ghg_total_line", fig))

    # N inputs
    df_n = load_table(run_dir, "N_and_P__ResultsNitrogen")
    if df_n is not None:
        df_n = filter_pathway(df_n, pathway)
        year_col = detect_year_col(df_n.columns.tolist())
        if year_col and not df_n.empty:
            df_n = prepare_curated_chart_df(
                df_n,
                year_col,
                ["CalcNAppSoils", "CalcNLeftPast", "CalcNsynth", "HistTotalN"],
            )
            if df_n.empty:
                pass
            df_n = df_n.sort_values(year_col)
            fig = go.Figure()
            for col, label in [
                ("CalcNAppSoils", "Manure applied to soils"),
                ("CalcNLeftPast", "Manure left on pasture"),
                ("CalcNsynth", "Synthetic fertilizers applied to soils"),
            ]:
                if col in df_n.columns:
                    fig.add_bar(
                        x=df_n[year_col],
                        y=df_n[col],
                        name=label,
                    )
            if "HistTotalN" in df_n.columns:
                fig.add_scatter(
                    x=df_n[year_col],
                    y=df_n["HistTotalN"],
                    mode="lines+markers",
                    name="Total historical",
                )
            fig.update_layout(
                title="N inputs",
                barmode="stack",
                yaxis_title="1000 tons N",
            )
            figs.append(("n_inputs", fig))

    return figs


def curated_charts_tab(run_dir: Path) -> None:
    st.subheader("Curated Charts")
    pathways = get_pathways_from_tables(run_dir)
    if not pathways:
        st.warning("No pathways found in combined tables.")
        return

    default = "CurrentTrends" if "CurrentTrends" in pathways else pathways[0]
    pathway = st.selectbox("Pathway", pathways, index=pathways.index(default))

    export_for_all = st.checkbox("Export for all pathways", value=False)
    export_clicked = st.button("Export curated charts (HTML)")

    fig_list = build_curated_figures(run_dir, pathway)
    for _, fig in fig_list:
        st.plotly_chart(fig, use_container_width=True)

    if export_clicked:
        out_root = run_dir / "plotly_curated"
        out_root.mkdir(parents=True, exist_ok=True)
        targets = pathways if export_for_all else [pathway]
        for path_name in targets:
            figs = build_curated_figures(run_dir, path_name)
            out_dir = out_root / safe_name(path_name)
            out_dir.mkdir(parents=True, exist_ok=True)
            for name, fig in figs:
                out_path = out_dir / f"{safe_name(name)}.html"
                fig.write_html(out_path)
        st.success(f"Saved curated charts to: {out_root}")


def combined_tables_tab(run_dir: Path) -> None:
    st.subheader("Combined Tables")
    combined_dir = run_dir / "combined_tables"
    if not combined_dir.exists():
        st.error(f"combined_tables not found in: {run_dir}")
        return

    table_paths = sorted(combined_dir.glob("*.csv"))
    if not table_paths:
        st.warning("No combined tables found.")
        return

    table_map = {
        p.stem.replace("__all_pathways", ""): p for p in table_paths
    }
    table_name = st.selectbox("Table", sorted(table_map.keys()))
    df = load_csv(table_map[table_name])
    st.caption(f"Rows: {len(df):,} | Columns: {len(df.columns)}")

    pathway_col = detect_pathway_col(df.columns.tolist())
    year_col = detect_year_col(df.columns.tolist())
    cat_cols = [
        c
        for c in df.columns
        if c not in {pathway_col, year_col} and df[c].dtype == object
    ]
    numeric_cols: List[str] = []
    for c in df.columns:
        if c in {pathway_col, year_col}:
            continue
        series = pd.to_numeric(df[c], errors="coerce")
        if series.notna().any():
            numeric_cols.append(c)

    col1, col2, col3 = st.columns(3)
    with col1:
        metric = st.selectbox(
            "Metric", numeric_cols if numeric_cols else df.columns.tolist()
        )
    with col2:
        category_col = st.selectbox("Category column", ["(none)"] + cat_cols)
    with col3:
        pathways = None
        if pathway_col:
            all_paths = sorted(df[pathway_col].dropna().unique().tolist())
            pathways = st.multiselect("Pathways", all_paths, default=all_paths)

    if category_col == "(none)":
        category_col = None
        category_values = None
    else:
        values = sorted(df[category_col].dropna().unique().tolist())
        category_values = st.multiselect(
            "Category values",
            values,
            default=values[: min(6, len(values))],
        )

    plot_df = prep_plot_df(
        df,
        pathway_col=pathway_col,
        year_col=year_col,
        category_col=category_col,
        category_values=category_values,
        pathways=pathways,
    )
    if plot_df.empty:
        st.warning("No data after filtering.")
        return

    compare = False
    baseline = None
    mode = "Absolute"
    if pathway_col and year_col:
        compare = st.checkbox("Compare to baseline", value=False)
        if compare:
            unique_paths = sorted(plot_df[pathway_col].unique().tolist())
            default_base = choose_baseline_pathway(unique_paths)
            baseline = st.selectbox(
                "Baseline pathway",
                unique_paths,
                index=unique_paths.index(default_base),
            )
            mode = st.radio("View", ["Absolute", "Delta", "% Delta"], horizontal=True)
            if mode != "Absolute":
                key_cols = [year_col]
                if category_col:
                    key_cols.append(category_col)
                plot_df = apply_baseline_mode(
                    plot_df,
                    pathway_col=pathway_col,
                    key_cols=key_cols,
                    metric=metric,
                    baseline=baseline,
                    mode=mode,
                )

    if year_col:
        fig = px.line(
            plot_df,
            x=year_col,
            y=metric,
            color=pathway_col if pathway_col else None,
            line_dash=category_col if category_col else None,
            markers=True,
            title=f"{table_name} - {metric}",
        )
    else:
        x_col = category_col or pathway_col
        fig = px.bar(
            plot_df,
            x=x_col,
            y=metric,
            color=pathway_col if pathway_col and pathway_col != x_col else None,
            barmode="group",
            title=f"{table_name} - {metric}",
        )

    st.plotly_chart(fig, use_container_width=True)

    if st.button("Export chart as HTML"):
        out_dir = run_dir / "plotly_dashboard"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{safe_name(table_name)}__{safe_name(metric)}.html"
        fig.write_html(out_path)
        st.success(f"Saved: {out_path}")


def deviation_analysis_tab(run_dir: Path) -> None:
    st.subheader("Scenario Deviation Analysis")
    st.caption("Review pathway differences and view only the charts with strongest deviations.")

    available_pathways = get_pathways_from_tables(run_dir)
    default_baseline = (
        choose_baseline_pathway(available_pathways)
        if available_pathways
        else DEFAULT_BASELINE_PATHWAY
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        abs_thr = st.number_input(
            "Absolute deviation threshold",
            min_value=0.0,
            value=0.0,
            step=1.0,
            help="A row is significant when the max baseline delta exceeds both thresholds.",
        )
    with col2:
        pct_thr = st.number_input(
            "Percent deviation threshold",
            min_value=0.0,
            value=15.0,
            step=1.0,
        )
    with col3:
        baseline_pathway = st.selectbox(
            "Baseline pathway",
            available_pathways if available_pathways else [default_baseline],
            index=(
                available_pathways.index(default_baseline)
                if available_pathways and default_baseline in available_pathways
                else 0
            ),
        )
    with col4:
        regenerate = st.button("Generate / refresh summary", key="deviation_generate")

    summary_path = run_dir / DEVIATION_SUMMARY_FILE
    if summary_path.exists() and not regenerate:
        df_summary = pd.read_csv(summary_path)
    else:
        with st.spinner("Building deviation summary from combined tables..."):
            df_summary, summary_path = compute_deviation_summary(
                run_dir=run_dir,
                baseline_pathway=baseline_pathway,
                default_abs_threshold=float(abs_thr),
                default_pct_threshold=float(pct_thr),
            )
        st.success(f"Saved: {summary_path}")

    if df_summary.empty:
        st.warning("No comparable multi-pathway numeric data found.")
        return

    baseline_values = sorted(df_summary.get("BaselinePathway", pd.Series(dtype="object")).dropna().unique().tolist())
    if baseline_values:
        st.caption(
            f"Summary file: `{summary_path}` | baseline: {', '.join(map(str, baseline_values))}"
        )
        if baseline_pathway not in baseline_values and summary_path.exists() and not regenerate:
            st.info("Regenerate the summary to apply the selected baseline.")
    else:
        st.caption(f"Summary file: `{summary_path}`")
    st.download_button(
        "Download deviation CSV",
        data=summary_path.read_bytes(),
        file_name=summary_path.name,
        mime="text/csv",
        key="deviation_download_csv",
    )

    view_df = df_summary.copy()
    if "SignificantDeviation" in view_df.columns:
        view_df["SignificantDeviation"] = view_df["SignificantDeviation"].astype(str).str.lower().isin(
            ["true", "1", "yes"]
        )
    else:
        view_df["SignificantDeviation"] = False

    show_significant_only = st.checkbox(
        "Show significant rows only",
        value=True,
        key="deviation_show_sig_only",
    )
    if show_significant_only:
        view_df = view_df[view_df["SignificantDeviation"]]

    preview_cols = [
        c
        for c in [
            "Table",
            "Metric",
            "Group",
            "MaxDiffPathway",
            "MaxAbsDiffVsBaseline",
            "MaxPctDiffVsBaseline",
            "IncompleteCoverage",
            "MissingPathways",
            "SignificantDeviation",
        ]
        if c in view_df.columns
    ]
    st.dataframe(view_df[preview_cols], use_container_width=True, height=280)

    candidates = build_deviation_candidates(view_df)
    if candidates.empty:
        st.info("No deviating charts available for the current filters.")
        return

    selected_idx = st.selectbox(
        "Select deviating chart",
        options=candidates.index.tolist(),
        format_func=lambda idx: candidates.loc[idx, "Label"],
        key="deviation_chart_select",
    )
    selected = candidates.loc[selected_idx]
    table_name = str(selected["Table"])
    metric = str(selected["Metric"])

    fig = build_deviation_figure(
        run_dir=run_dir,
        summary_df=view_df,
        table_name=table_name,
        metric=metric,
    )
    if fig is None:
        st.warning(f"Could not build chart for {table_name} / {metric}.")
        return

    st.plotly_chart(fig, use_container_width=True)

    if st.button("Export selected deviation chart as HTML", key="deviation_export_html"):
        out_dir = run_dir / "plotly_deviation"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{safe_name(table_name)}__{safe_name(metric)}.html"
        fig.write_html(out_path)
        st.success(f"Saved: {out_path}")


def chart_series_tab(run_dir: Path) -> None:
    st.subheader("Chart Series (from Excel charts)")
    meta = build_chart_index(run_dir)
    if meta.empty:
        st.warning("No chart series found.")
        return

    sheets = sorted(meta["sheet"].unique().tolist())
    sheet = st.selectbox("Sheet", sheets)
    meta_sheet = meta[meta["sheet"] == sheet]

    chart_titles = sorted(meta_sheet["chart_title"].unique().tolist())
    chart_title = st.selectbox("Chart title", chart_titles)
    meta_chart = meta_sheet[meta_sheet["chart_title"] == chart_title]

    series_list = sorted(meta_chart["series_idx"].unique().tolist())
    series_idx = st.selectbox("Series", series_list)
    meta_series = meta_chart[meta_chart["series_idx"] == series_idx]

    pathways = sorted(meta_series["pathway"].unique().tolist())
    selected_paths = st.multiselect("Pathways", pathways, default=pathways)
    meta_series = meta_series[meta_series["pathway"].isin(selected_paths)]

    dfs = []
    for p in meta_series["path"]:
        df = load_csv(Path(p))
        dfs.append(df)
    if not dfs:
        st.warning("No data for selection.")
        return
    df = pd.concat(dfs, ignore_index=True)

    # Coerce numeric
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Value"])
    x_col = "Category"

    compare = st.checkbox("Compare to baseline (chart series)", value=False)
    if compare and "RunPathway" in df.columns:
        unique_paths = sorted(df["RunPathway"].unique().tolist())
        default_base = choose_baseline_pathway(unique_paths)
        baseline = st.selectbox(
            "Baseline pathway",
            unique_paths,
            index=unique_paths.index(default_base),
        )
        mode = st.radio("View", ["Absolute", "Delta", "% Delta"], horizontal=True, key="chart_series_view")
        if mode != "Absolute":
            df = apply_baseline_mode(
                df,
                pathway_col="RunPathway",
                key_cols=[x_col],
                metric="Value",
                baseline=baseline,
                mode=mode,
            )

    # Try to sort x as numeric
    try:
        df[x_col] = pd.to_numeric(df[x_col], errors="ignore")
    except Exception:
        pass

    fig = px.line(
        df,
        x=x_col,
        y="Value",
        color="RunPathway",
        markers=True,
        title=f"{sheet} - {chart_title} (Series {series_idx})",
    )
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Export chart series HTML"):
        out_dir = run_dir / "plotly_dashboard"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{safe_name(sheet)}__{safe_name(chart_title)}__series_{series_idx}.html"
        fig.write_html(out_path)
        st.success(f"Saved: {out_path}")


def main() -> None:
    st.set_page_config(page_title="FABLE All-Pathways Dashboard", layout="wide")
    st.title("FABLE All-Pathways Dashboard")
    st.caption("Explore combined tables, deviations, and chart-series outputs with Plotly.")

    run_dir = sidebar_run_selector()
    if run_dir is None or not run_dir.exists():
        st.info("Select a valid run folder to begin.")
        return

    st.write(f"Using run folder: `{run_dir}`")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Curated Charts", "Combined Tables", "Deviation Analysis", "Chart Series"]
    )
    with tab1:
        curated_charts_tab(run_dir)
    with tab2:
        combined_tables_tab(run_dir)
    with tab3:
        deviation_analysis_tab(run_dir)
    with tab4:
        chart_series_tab(run_dir)


if __name__ == "__main__":
    main()
