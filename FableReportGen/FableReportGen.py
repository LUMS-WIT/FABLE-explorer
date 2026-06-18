#!/usr/bin/env python
"""
FableReportGen — AI-Ready Analysis & Report Generator

Takes a FableVisualizerV4 'all_pathways_run_*' output folder and produces:
  - graphs/01_ghg_total_emissions.png … 10_pathway_overview_radar.png
  - ai_briefing.md   (structured markdown — paste into Claude / ChatGPT)
  - detailed_metrics.csv  (per-domain per-pathway statistics)

Usage:
  python FableReportGen.py
  → File picker opens; select the 'all_pathways_run_…' folder.
"""

from __future__ import annotations

import os
import sys
import textwrap
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must come before pyplot import
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tkinter as tk
from matplotlib.ticker import MaxNLocator
from tkinter import filedialog, messagebox

# ── Import shared utilities from FableVisualizerV4 if available ────────────
_HERE = Path(__file__).parent
_V4_DIR = _HERE.parent / "FableVisualizerV4"
if str(_V4_DIR) not in sys.path:
    sys.path.insert(0, str(_V4_DIR))

try:
    from FableVisualizerV4_Comparison import (
        choose_baseline_pathway,
        detect_pathway_col,
        detect_year_col,
    )
except ImportError:
    def detect_pathway_col(columns):
        for c in columns:
            if str(c) in ("RunPathway", "_RunPathway"):
                return str(c)
        return None

    def detect_year_col(columns):
        for c in columns:
            if str(c).strip().lower() == "year":
                return str(c)
        return None

    def choose_baseline_pathway(names, preferred=None):
        available = sorted([n for n in names if pd.notna(n)], key=str)
        if not available:
            raise ValueError("No pathways found.")
        if preferred in available:
            return preferred
        if "CurrentTrends" in available:
            return "CurrentTrends"
        return available[0]


# ── Visual style & colours ─────────────────────────────────────────────────
_STYLE = "seaborn-v0_8-whitegrid"
_PATHWAY_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf",
]


def _pathway_color_map(pathways: list[str]) -> dict[str, str]:
    return {p: _PATHWAY_COLORS[i % len(_PATHWAY_COLORS)] for i, p in enumerate(pathways)}


def _use_style():
    try:
        plt.style.use(_STYLE)
    except OSError:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_combined_tables(run_dir: Path) -> dict[str, pd.DataFrame]:
    """Load every *__all_pathways.csv from the combined_tables subfolder."""
    combined_dir = run_dir / "combined_tables"
    tables: dict[str, pd.DataFrame] = {}
    for p in sorted(combined_dir.glob("*__all_pathways.csv")):
        key = p.stem.replace("__all_pathways", "")
        tables[key] = pd.read_csv(p)
    return tables


def _find(tables: dict[str, pd.DataFrame], *keys: str) -> pd.DataFrame | None:
    """Return the first table whose name contains any of the given substrings."""
    for key in keys:
        for k, df in tables.items():
            if key.lower() in k.lower():
                return df
    return None


def _prep(df: pd.DataFrame):
    """Return (pathway_col, year_col, sorted_pathways) or (None, None, [])."""
    pcol = detect_pathway_col(df.columns.tolist())
    ycol = detect_year_col(df.columns.tolist())
    if pcol is None:
        return None, None, []
    pathways = sorted(df[pcol].dropna().unique().tolist(), key=str)
    return pcol, ycol, pathways


def _pivot(df: pd.DataFrame, pcol: str, ycol: str, metric: str) -> pd.DataFrame:
    """Return DataFrame indexed by year, columns are pathways."""
    if metric not in df.columns or ycol not in df.columns:
        return pd.DataFrame()
    tmp = df[[ycol, pcol, metric]].copy()
    tmp[ycol] = pd.to_numeric(tmp[ycol], errors="coerce")
    tmp[metric] = pd.to_numeric(tmp[metric], errors="coerce")
    tmp = tmp.dropna(subset=[pcol, ycol, metric])
    if tmp.empty:
        return pd.DataFrame()
    agg = tmp.groupby([ycol, pcol])[metric].sum().reset_index()
    return agg.pivot(index=ycol, columns=pcol, values=metric).sort_index()


def _year_value(df: pd.DataFrame, pcol: str, ycol: str, metric: str, year: int) -> pd.Series:
    """Return per-pathway sum for the year closest to `year`."""
    if metric not in df.columns or ycol not in df.columns:
        return pd.Series(dtype=float)
    tmp = df[[ycol, pcol, metric]].copy()
    tmp[ycol] = pd.to_numeric(tmp[ycol], errors="coerce")
    tmp[metric] = pd.to_numeric(tmp[metric], errors="coerce")
    available = tmp[ycol].dropna().unique()
    if len(available) == 0:
        return pd.Series(dtype=float)
    closest = min(available, key=lambda y: abs(y - year))
    return tmp[tmp[ycol] == closest].groupby(pcol)[metric].sum()


# ══════════════════════════════════════════════════════════════════════════════
# 2. STATISTICS → detailed_metrics.csv
# ══════════════════════════════════════════════════════════════════════════════

_DOMAIN_METRICS = [
    # (domain, table_key_fragment, column, unit)
    ("GHG",          "GHG__ResultsGHG",           "TotalCO2e",              "MtCO2eq/yr"),
    ("GHG",          "GHG__ResultsGHG",           "CropCO2e",               "MtCO2eq/yr"),
    ("GHG",          "GHG__ResultsGHG",           "LiveCO2e",               "MtCO2eq/yr"),
    ("GHG",          "GHG__ResultsGHG",           "DeforCO2",               "MtCO2eq/yr"),
    ("GHG",          "GHG__ResultsGHG",           "LandSeqReg",             "MtCO2eq/yr"),
    ("Land",         "LAND__ResultsLand",          "Forest",                 "million ha"),
    ("Land",         "LAND__ResultsLand",          "Cropland",               "million ha"),
    ("Land",         "LAND__ResultsLand",          "Pasture",                "million ha"),
    ("Land",         "LAND__ResultsLand",          "OtherLand",              "million ha"),
    ("Food",         "FOOD__Total_results_diets",  "kcal_feas",              "kcal/day"),
    ("Food",         "FOOD__Total_results_diets",  "prot_feas",              "g/day"),
    ("Food",         "FOOD__Total_results_diets",  "fat_feas",               "g/day"),
    ("Biodiversity", "ResultsBioScore",            "MeanBioScore",           "score"),
    ("Biodiversity", "ResultsBioScore",            "CropBioScore",           "score"),
    ("Jobs",         "JOBS__ResultsJobs",          "onfarm_crops",           "million FTE"),
    ("Jobs",         "JOBS__ResultsJobs",          "onfarm_livestock",       "million FTE"),
    ("Production",   "TotalResultsProd",           "prodvusd_feas",          "USD"),
    ("Trade",        "TotalResultsTrade",          "TradeBalanceFeas_usd",   "USD"),
    ("Water",        "WATER__ResultsWater",        "CalcIrrWithdrawals",     "km3/yr"),
    ("Water",        "WATER__ResultsWater",        "CalcIrrRequirements",    "km3/yr"),
    ("Nitrogen",     "ResultsNitrogen",            "CalcNsynth",             "1000 tN"),
    ("Nitrogen",     "ResultsNitrogen",            "CalcNAppSoils",          "1000 tN"),
]


def _fmt_num(v) -> str:
    try:
        f = float(v)
        if np.isnan(f):
            return ""
        return f"{f:.4g}"
    except (TypeError, ValueError):
        return ""


def compute_stats(tables: dict[str, pd.DataFrame], baseline: str) -> pd.DataFrame:
    rows = []
    for domain, table_key, metric, unit in _DOMAIN_METRICS:
        df = _find(tables, table_key)
        if df is None or metric not in df.columns:
            continue
        pcol, ycol, pathways = _prep(df)
        if pcol is None or ycol is None:
            continue

        v2020_all = _year_value(df, pcol, ycol, metric, 2020)
        v2035_all = _year_value(df, pcol, ycol, metric, 2035)
        v2050_all = _year_value(df, pcol, ycol, metric, 2050)
        baseline_2050 = float(v2050_all.get(baseline, np.nan))

        for pathway in pathways:
            v20 = float(v2020_all.get(pathway, np.nan))
            v35 = float(v2035_all.get(pathway, np.nan))
            v50 = float(v2050_all.get(pathway, np.nan))

            abs_chg = v50 - v20 if not (np.isnan(v50) or np.isnan(v20)) else np.nan
            pct_chg = (abs_chg / abs(v20) * 100) if (abs_chg is not np.nan and v20 != 0 and not np.isnan(v20)) else np.nan

            abs_dev = v50 - baseline_2050 if not (np.isnan(v50) or np.isnan(baseline_2050)) else np.nan
            pct_dev = (abs_dev / abs(baseline_2050) * 100) if (abs_dev is not np.nan and baseline_2050 != 0 and not np.isnan(baseline_2050)) else np.nan

            rows.append({
                "Domain":                       domain,
                "Table":                        table_key,
                "Metric":                       metric,
                "Unit":                         unit,
                "Pathway":                      pathway,
                "Value_2020":                   _fmt_num(v20),
                "Value_2035":                   _fmt_num(v35),
                "Value_2050":                   _fmt_num(v50),
                "Change_2020_2050_abs":         _fmt_num(abs_chg),
                "Change_2020_2050_pct":         _fmt_num(pct_chg),
                "Deviation_vs_baseline_abs":    _fmt_num(abs_dev),
                "Deviation_vs_baseline_pct":    _fmt_num(pct_dev),
                "BaselinePathway":              baseline,
            })

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 3. GRAPH GENERATION (10 charts, 300 DPI)
# ══════════════════════════════════════════════════════════════════════════════

def _save(fig: plt.Figure, path: Path):
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path.name}")


def _multiline(pivot: pd.DataFrame, title: str, ylabel: str, path: Path,
               ref_lines: dict | None = None):
    """Generic time-series multi-line chart, one line per pathway."""
    if pivot.empty:
        print(f"  Skipped (no data): {path.name}")
        return
    _use_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = _pathway_color_map(list(pivot.columns))
    for col in pivot.columns:
        ax.plot(pivot.index, pivot[col], marker="o", markersize=4,
                linewidth=2, label=col, color=colors.get(col, "gray"))
    if ref_lines:
        for label, (series, color, ls) in ref_lines.items():
            ax.plot(series.index, series.values, linestyle=ls, color=color,
                    linewidth=1.5, label=label, alpha=0.75)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.legend(fontsize=9, loc="best")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, path)


# ── Chart 01: Total GHG ────────────────────────────────────────────────────
def _chart_01(tables, graphs_dir, _pathways):
    df = _find(tables, "GHG__ResultsGHG")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return
    pivot = _pivot(df, pcol, ycol, "TotalCO2e")
    _multiline(pivot, "Total GHG Emissions by Pathway",
               "MtCO₂eq / yr", graphs_dir / "01_ghg_total_emissions.png")


# ── Chart 02: GHG sector breakdown (2050 bar) ─────────────────────────────
def _chart_02(tables, graphs_dir, pathways):
    df = _find(tables, "GHG__ResultsGHG")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    all_sectors = ["CropCO2e", "LiveCO2e", "DeforCO2", "OtherLandCO2", "LandSeqReg", "SOCAgroecoCO2"]
    sectors = [s for s in all_sectors if s in df.columns]
    if not sectors:
        return

    df = df.copy()
    df[ycol] = pd.to_numeric(df[ycol], errors="coerce")
    available = df[ycol].dropna().unique()
    yr = min(available, key=lambda y: abs(y - 2050))

    sub = df[df[ycol] == yr].copy()
    for s in sectors:
        sub[s] = pd.to_numeric(sub[s], errors="coerce")
    agg = sub.groupby(pcol)[sectors].sum()
    agg = agg.reindex([p for p in pathways if p in agg.index])

    _use_style()
    fig, ax = plt.subplots(figsize=(max(10, len(pathways) * 1.8), 6))
    x = np.arange(len(agg))
    w = 0.8 / len(sectors)
    sector_colors = ["#e6ab02", "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e"]
    for i, s in enumerate(sectors):
        ax.bar(x + i * w - (len(sectors) - 1) * w / 2,
               agg[s], w, label=s, color=sector_colors[i % len(sector_colors)])
    ax.set_xticks(x)
    ax.set_xticklabels(agg.index, rotation=20, ha="right")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title(f"GHG Emissions by Sector — {int(yr)}", fontsize=14, fontweight="bold")
    ax.set_ylabel("MtCO₂eq / yr", fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, graphs_dir / "02_ghg_sector_breakdown.png")


# ── Chart 03: Land cover (3-panel) ────────────────────────────────────────
def _chart_03(tables, graphs_dir, pathways):
    df = _find(tables, "LAND__ResultsLand")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    metrics = [m for m in ["Forest", "Cropland", "Pasture"] if m in df.columns]
    if not metrics:
        return

    _use_style()
    fig, axes = plt.subplots(1, len(metrics), figsize=(6 * len(metrics), 5), sharey=False)
    if len(metrics) == 1:
        axes = [axes]
    colors = _pathway_color_map(pathways)

    for ax, metric in zip(axes, metrics):
        piv = _pivot(df, pcol, ycol, metric)
        if piv.empty:
            ax.set_title(metric)
            continue
        for col in piv.columns:
            ax.plot(piv.index, piv[col], marker="o", markersize=3,
                    linewidth=2, label=col, color=colors.get(col, "gray"))
        ax.set_title(metric, fontsize=12, fontweight="bold")
        ax.set_xlabel("Year")
        ax.set_ylabel("Million ha")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    handles = [mpatches.Patch(color=colors.get(p, "gray"), label=p) for p in pathways]
    fig.legend(handles=handles, loc="lower center",
               ncol=min(len(pathways), 5), fontsize=9, bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("Land Cover Change by Pathway", fontsize=14, fontweight="bold")
    fig.tight_layout()
    _save(fig, graphs_dir / "03_land_cover.png")


# ── Chart 04: Food security ────────────────────────────────────────────────
def _chart_04(tables, graphs_dir, _pathways):
    df = _find(tables, "FOOD__Total_results_diets")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None or "kcal_feas" not in df.columns:
        return

    pivot = _pivot(df, pcol, ycol, "kcal_feas")
    ref_lines = {}
    if "kcal_MDER" in df.columns:
        mder = _pivot(df, pcol, ycol, "kcal_MDER")
        if not mder.empty:
            ref_lines["MDER (min. energy requirement)"] = (mder.mean(axis=1), "red", "--")
    _multiline(pivot, "Food Security — Daily Energy Availability",
               "kcal / capita / day", graphs_dir / "04_food_security.png",
               ref_lines=ref_lines)


# ── Chart 05: Biodiversity ─────────────────────────────────────────────────
def _chart_05(tables, graphs_dir, _pathways):
    df = _find(tables, "ResultsBioScore")
    if df is None:
        df = _find(tables, "ResultsBiodiv")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    metric = next((m for m in ["MeanBioScore", "CropBioScore", "CalcBiodivLnd"]
                   if m in df.columns), None)
    if metric is None:
        return

    pivot = _pivot(df, pcol, ycol, metric)
    ref_lines = {}
    if "BiodivTarget" in df.columns:
        tgt = _pivot(df, pcol, ycol, "BiodivTarget")
        if not tgt.empty:
            ref_lines["Biodiversity Target"] = (tgt.mean(axis=1), "green", "--")
    _multiline(pivot, "Biodiversity Score by Pathway", "Score",
               graphs_dir / "05_biodiversity.png", ref_lines=ref_lines)


# ── Chart 06: Agricultural jobs ───────────────────────────────────────────
def _chart_06(tables, graphs_dir, pathways):
    df = _find(tables, "JOBS__ResultsJobs")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    job_cols = [c for c in ["onfarm_crops", "onfarm_livestock"] if c in df.columns]
    if not job_cols:
        return

    df = df.copy()
    df[ycol] = pd.to_numeric(df[ycol], errors="coerce")
    for c in job_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    years = sorted(df[ycol].dropna().unique())

    _use_style()
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = _pathway_color_map(pathways)
    for pathway in pathways:
        sub = df[df[pcol] == pathway].groupby(ycol)[job_cols].sum().reindex(years)
        total = sub.sum(axis=1)
        ax.plot(years, total, marker="o", markersize=4, linewidth=2,
                label=pathway, color=colors.get(pathway, "gray"))
    ax.set_title("Total Agricultural Employment by Pathway", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel("Million FTE Workers", fontsize=11)
    ax.legend(fontsize=9, loc="best")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.tight_layout()
    _save(fig, graphs_dir / "06_agricultural_jobs.png")


# ── Chart 07: Production value ────────────────────────────────────────────
def _chart_07(tables, graphs_dir, _pathways):
    df = _find(tables, "TotalResultsProd")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    metric = next((m for m in ["prodvusd_feas", "prodvusd_targ", "TotalValue"]
                   if m in df.columns), None)
    if metric is None:
        return
    pivot = _pivot(df, pcol, ycol, metric)
    _multiline(pivot, "Agricultural Production Value by Pathway",
               "USD", graphs_dir / "07_production_value.png")


# ── Chart 08: Trade balance ───────────────────────────────────────────────
def _chart_08(tables, graphs_dir, _pathways):
    df = _find(tables, "TotalResultsTrade")
    if df is None:
        df = _find(tables, "TRADE__")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    metric = next((m for m in ["TradeBalanceFeas_usd", "TradeBalance"]
                   if m in df.columns), None)
    if metric is None:
        for col in df.columns:
            if "trade" in col.lower() and "balance" in col.lower():
                metric = col
                break
    if metric is None:
        return
    pivot = _pivot(df, pcol, ycol, metric)
    _multiline(pivot, "Agricultural Trade Balance by Pathway",
               "USD", graphs_dir / "08_trade_balance.png")


# ── Chart 09: Nitrogen ────────────────────────────────────────────────────
def _chart_09(tables, graphs_dir, _pathways):
    df = _find(tables, "ResultsNitrogen")
    if df is None:
        return
    pcol, ycol, _ = _prep(df)
    if pcol is None or ycol is None:
        return

    metric = next((m for m in ["CalcNsynth", "CalcNAppSoils", "HistTotalN"]
                   if m in df.columns), None)
    if metric is None:
        return

    pivot = _pivot(df, pcol, ycol, metric)
    ref_lines = {}
    if "HistTotalN" in df.columns and metric != "HistTotalN":
        hist = _pivot(df, pcol, ycol, "HistTotalN")
        if not hist.empty:
            ref_lines["Historical Total N"] = (hist.mean(axis=1), "brown", ":")
    _multiline(pivot, "Nitrogen Application by Pathway",
               "1 000 tonnes of N", graphs_dir / "09_nitrogen.png",
               ref_lines=ref_lines)


# ── Chart 10: Radar (pathway overview) ───────────────────────────────────
def _chart_10(tables, graphs_dir, pathways, baseline):
    radar_defs = [
        # (table_key, column, label, higher_is_better)
        ("GHG__ResultsGHG",          "TotalCO2e",   "GHG\nEmissions",   False),
        ("LAND__ResultsLand",         "Forest",       "Forest\nArea",     True),
        ("FOOD__Total_results_diets", "kcal_feas",    "Food\nSecurity",   True),
        ("ResultsBioScore",           "MeanBioScore", "Biodiversity",     True),
        ("JOBS__ResultsJobs",         "onfarm_crops", "Jobs",             True),
    ]

    collected: dict[str, list[float]] = {p: [] for p in pathways}
    labels: list[str] = []

    for table_key, col, label, higher_is_better in radar_defs:
        df = _find(tables, table_key)
        if df is None:
            continue
        pcol, ycol, _ = _prep(df)
        if pcol is None or ycol is None or col not in df.columns:
            continue
        vals = _year_value(df, pcol, ycol, col, 2050)
        if vals.empty:
            continue

        mn, mx = vals.min(), vals.max()
        span = mx - mn
        labels.append(label)
        for pathway in pathways:
            raw = float(vals.get(pathway, np.nan))
            if span > 0 and not np.isnan(raw):
                norm = (raw - mn) / span
                if not higher_is_better:
                    norm = 1.0 - norm
            else:
                norm = 0.5
            collected[pathway].append(norm)

    if len(labels) < 3:
        print("  Skipped radar chart (fewer than 3 metrics available).")
        return

    N = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles_closed = angles + angles[:1]

    _use_style()
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    colors = _pathway_color_map(pathways)

    for pathway in pathways:
        vals_n = collected[pathway] + collected[pathway][:1]
        ax.plot(angles_closed, vals_n, "o-", linewidth=2,
                color=colors.get(pathway, "gray"), label=pathway)
        ax.fill(angles_closed, vals_n, alpha=0.08,
                color=colors.get(pathway, "gray"))

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.0"], fontsize=7)
    ax.set_title("Pathway Overview — Normalised 2050 Indicators\n(higher = better in all axes)",
                 fontsize=12, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.38, 1.15), fontsize=9)
    fig.tight_layout()
    _save(fig, graphs_dir / "10_pathway_overview_radar.png")


# ══════════════════════════════════════════════════════════════════════════════
# 4. MARKDOWN BRIEFING
# ══════════════════════════════════════════════════════════════════════════════

def _domain_table(stats_df: pd.DataFrame, domain: str, metric: str, unit: str, baseline: str) -> str:
    sub = stats_df[(stats_df["Domain"] == domain) & (stats_df["Metric"] == metric)]
    if sub.empty:
        return f"_No data available for {metric}._\n"
    lines = [
        f"**{metric}** ({unit})\n",
        "| Pathway | 2020 | 2035 | 2050 | Δ 2020→2050 (%) | vs Baseline 2050 (%) |",
        "|---------|------|------|------|-----------------|----------------------|",
    ]
    for _, row in sub.iterrows():
        tag = " ← baseline" if row["Pathway"] == baseline else ""
        lines.append(
            f"| {row['Pathway']}{tag} "
            f"| {row['Value_2020'] or '—'} "
            f"| {row['Value_2035'] or '—'} "
            f"| {row['Value_2050'] or '—'} "
            f"| {row['Change_2020_2050_pct'] or '—'}% "
            f"| {row['Deviation_vs_baseline_pct'] or '—'}% |"
        )
    return "\n".join(lines) + "\n"


def build_briefing(tables, stats_df: pd.DataFrame, baseline: str,
                   pathways: list[str], run_dir: Path) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pathway_list = "\n".join(
        f"- **{p}**{'  ← baseline (CurrentTrends)' if p == baseline else ''}"
        for p in pathways
    )

    # Domain sections: (heading, [(domain, metric, unit)])
    domain_sections = [
        ("GHG Emissions", [
            ("GHG", "TotalCO2e",   "MtCO₂eq/yr"),
            ("GHG", "CropCO2e",    "MtCO₂eq/yr"),
            ("GHG", "LiveCO2e",    "MtCO₂eq/yr"),
            ("GHG", "DeforCO2",    "MtCO₂eq/yr"),
        ]),
        ("Land Use", [
            ("Land", "Forest",    "million ha"),
            ("Land", "Cropland",  "million ha"),
            ("Land", "Pasture",   "million ha"),
        ]),
        ("Food Security", [
            ("Food", "kcal_feas", "kcal/day"),
            ("Food", "prot_feas", "g/day"),
        ]),
        ("Biodiversity", [
            ("Biodiversity", "MeanBioScore", "score"),
        ]),
        ("Agricultural Employment", [
            ("Jobs", "onfarm_crops",     "million FTE"),
            ("Jobs", "onfarm_livestock", "million FTE"),
        ]),
        ("Agricultural Production & Trade", [
            ("Production", "prodvusd_feas",          "USD"),
            ("Trade",      "TradeBalanceFeas_usd",   "USD"),
        ]),
        ("Water & Nutrients", [
            ("Water",    "CalcIrrWithdrawals", "km³/yr"),
            ("Nitrogen", "CalcNsynth",         "1 000 tN"),
        ]),
    ]

    parts: list[str] = []

    # ── Header & AI instructions ───────────────────────────────────────────
    parts.append(textwrap.dedent(f"""\
        # FABLE Analysis Briefing

        _Generated: {now}_
        _Run directory: {run_dir.name}_

        ---

        ## Instructions for AI

        You are an expert agricultural economist and sustainability researcher.
        Below is structured quantitative output from the FABLE (Food, Agriculture,
        Biodiversity, Land use, and Energy) Calculator — a national-level scenario
        modelling tool used to analyse pathways to sustainability by 2050.

        **Your task:** Write a detailed, well-structured academic paper (~5 000 words)
        that uses the data tables in this briefing as its primary evidence base.
        Be specific — cite numbers, compare pathways, highlight trade-offs, and identify
        which pathways best achieve sustainability targets across all domains.

        Graphs have been generated separately (PNG files in the `graphs/` folder next to
        this file). Reference them in the Results sections as: Figure 1 (GHG Emissions),
        Figure 2 (GHG Sector Breakdown), Figure 3 (Land Cover), Figure 4 (Food Security),
        Figure 5 (Biodiversity), Figure 6 (Jobs), Figure 7 (Production), Figure 8 (Trade),
        Figure 9 (Nitrogen), Figure 10 (Pathway Overview Radar).

        ---

        ## 1. Model and Pathways Overview

        ### What is FABLE?
        The FABLE Calculator is an open-source scenario modelling tool that helps countries
        analyse pathways to simultaneously achieve food-security and land-use sustainability
        goals by 2050. It integrates food demand, agricultural production, land use,
        greenhouse gas emissions, biodiversity, water use, trade, and employment into a
        single coherent national-level framework.

        ### Pathways Analysed
        {pathway_list}

        **Baseline:** {baseline}
        **Time horizon:** 2020 – 2050 (5-year intervals)

        ---

        ## 2. Results by Domain
    """))

    # ── Domain tables ──────────────────────────────────────────────────────
    for heading, metrics in domain_sections:
        parts.append(f"\n### {heading}\n")
        for domain, metric, unit in metrics:
            parts.append(_domain_table(stats_df, domain, metric, unit, baseline))

    # ── Cross-domain trade-offs ────────────────────────────────────────────
    if not stats_df.empty:
        parts.append("\n---\n\n## 3. Cross-Domain Trade-offs\n")
        tmp = stats_df.copy()
        tmp["_v50"] = pd.to_numeric(tmp["Value_2050"], errors="coerce")
        domain_leader: dict[str, str] = {}
        for domain, higher_is_better in [
            ("GHG", False), ("Land", True), ("Food", True),
            ("Biodiversity", True), ("Jobs", True),
        ]:
            sub = tmp[(tmp["Domain"] == domain) & tmp["_v50"].notna()]
            if sub.empty:
                continue
            best = sub.sort_values("_v50", ascending=not higher_is_better).iloc[0]
            domain_leader[domain] = str(best["Pathway"])

        if domain_leader:
            parts.append(
                "The table below shows which pathway leads each domain at 2050:\n\n"
                "| Domain | Best-performing Pathway |\n"
                "|--------|------------------------|\n"
            )
            for dom, leader in domain_leader.items():
                parts.append(f"| {dom} | {leader} |\n")
            top, count = Counter(domain_leader.values()).most_common(1)[0]
            parts.append(
                f"\n**{top}** leads in {count} out of {len(domain_leader)} domains assessed.\n"
            )

    # ── Suggested paper structure ──────────────────────────────────────────
    parts.append(textwrap.dedent("""
        ---

        ## 4. Suggested Paper Structure

        Please write the paper using the following structure. Use the data in Section 2
        as the evidence base for Sections 4 and 5.

        1. **Abstract** (~250 words): model context, pathways analysed, headline findings
        2. **Introduction**: food-land-environment nexus in the national context, why FABLE
        3. **Methodology**: FABLE Calculator overview, pathway definitions, scenario assumptions,
           time horizon, metrics and units
        4. **Results**
           - 4.1 GHG Emissions (Figure 1, Figure 2)
           - 4.2 Land Use Change (Figure 3)
           - 4.3 Food Security (Figure 4)
           - 4.4 Biodiversity (Figure 5)
           - 4.5 Agricultural Employment (Figure 6)
           - 4.6 Production and Trade (Figure 7, Figure 8)
           - 4.7 Water and Nutrient Use (Figure 9)
        5. **Cross-Domain Pathway Comparison** (Figure 10)
        6. **Discussion**: limitations, uncertainties, policy implications
        7. **Conclusions**: headline findings, recommended pathways, next steps

        ---
        _End of briefing_
    """))

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    root.withdraw()

    run_dir_str = filedialog.askdirectory(
        title="Select FableVisualizerV4 run folder  (all_pathways_run_…)"
    )
    if not run_dir_str:
        print("No folder selected. Exiting.")
        return

    run_dir = Path(run_dir_str)
    if not (run_dir / "combined_tables").exists():
        messagebox.showerror(
            "Invalid folder",
            f"No 'combined_tables' subfolder found in:\n{run_dir}\n\n"
            "Please select a valid FableVisualizerV4 run folder."
        )
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = run_dir / f"report_{ts}"
    graphs_dir = out_dir / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nFableReportGen")
    print(f"  Input : {run_dir}")
    print(f"  Output: {out_dir}\n")

    # ── 1. Load ───────────────────────────────────────────────────────────
    print("[1/4] Loading combined tables...")
    tables = load_combined_tables(run_dir)
    if not tables:
        messagebox.showerror("No data",
                             "No combined table CSVs found. Run FableVisualizerV4 first.")
        return

    all_pathways: list[str] = []
    for df in tables.values():
        pcol = detect_pathway_col(df.columns.tolist())
        if pcol:
            all_pathways = sorted(df[pcol].dropna().unique().tolist(), key=str)
            break

    baseline = choose_baseline_pathway(all_pathways)
    print(f"  {len(tables)} tables | pathways: {all_pathways} | baseline: {baseline}")

    # ── 2. Statistics ─────────────────────────────────────────────────────
    print("[2/4] Computing statistics...")
    stats_df = compute_stats(tables, baseline)
    stats_df.to_csv(out_dir / "detailed_metrics.csv", index=False)
    print(f"  detailed_metrics.csv  ({len(stats_df)} rows)")

    # ── 3. Graphs ─────────────────────────────────────────────────────────
    print("[3/4] Generating graphs...")
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

    # ── 4. Markdown briefing ──────────────────────────────────────────────
    print("[4/4] Writing AI briefing...")
    briefing = build_briefing(tables, stats_df, baseline, all_pathways, run_dir)
    briefing_path = out_dir / "ai_briefing.md"
    briefing_path.write_text(briefing, encoding="utf-8")
    print(f"  ai_briefing.md  ({len(briefing):,} chars)")

    print(f"\nDone!  →  {out_dir}\n")
    os.startfile(str(out_dir))


if __name__ == "__main__":
    main()
