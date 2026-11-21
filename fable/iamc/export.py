"""FABLE CSV run directory -> IAMC-format timeseries.

Reads the ``combined_tables/*__all_pathways.csv`` files written by any recalc
engine and maps them onto variables from IAMconsortium/common-definitions
(agriculture, food, land cover, AFOLU emissions, nutrients, water, labour).

    model     user-chosen (``--model`` / config ``iamc.model``), else ``FABLE-<country>``
    scenario  pathway name (optionally renamed via config ``iamc.scenario_names``)
    region    config ``iamc.region``, else the workbook country (IAMC country name)

Every emitted (variable, unit) pair is checked against ``iamc_variables.csv``,
a vendored snapshot of common-definitions (see ``refresh_definitions.py``).
A missing source table skips its variables and is noted in the mapping report;
it never raises.

Unit assumptions for FABLE outputs (Calculator conventions):
    production, trade, N flows     1000 t        -> /1000 (million t, Tg)
    land areas                     1000 ha       -> /1000 (million ha)
    GHG by gas                     Mt CO2e       -> back to mass with the run's GWP
    irrigation water               million m3    -> /1000 (km3)
    jobs, active population        1000 persons  -> /1000 (million)
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
PRODUCTS_CSV = HERE / "products.csv"
VARIABLES_CSV = HERE / "iamc_variables.csv"
COMBINED = "combined_tables"

MDM = "million t DM/yr"
MHA = "million ha"
PRICE_BASE_YEAR = 2020

# Fallback GWP-100 values if the run has no GWP_Conversion table.
GWP_FALLBACK = {
    "SAR": (21.0, 310.0), "AR4": (25.0, 298.0),
    "AR5": (28.0, 265.0), "AR6": (27.2, 273.0),
}

# FABLE diet groups -> IAMC food-system path below "Food Availability".
# None = counted only in the grand total (no matching IAMC commodity).
DIET_GROUPS = {
    "CEREALS": "Crops|Cereals",
    "OLSOIL": "Crops|Oil Crops",
    "SUGAR": "Crops|Sugar Crops",
    "FRUVEG": "Crops|Other Crops",
    "PULSES": "Crops|Other Crops",
    "ROOTS": "Crops|Other Crops",
    "NUTS": "Crops|Other Crops",
    "BEVSPICES": "Crops|Other Crops",
    "ALCOHOL": "Crops",
    "MILK": "Livestock|Ruminant|Dairy",
    "REDMEAT": "Livestock|Ruminant|Meat",
    "PORK": "Livestock|Non-Ruminant|Meat|Pig",
    "POULTRY": "Livestock|Non-Ruminant|Meat|Poultry",
    "EGGS": "Livestock|Non-Ruminant|Eggs",
    "ANIMFAT": "Livestock",
    "FISH": None,
    "OTHER": None,
}

CROP_TYPES = ["Cereals", "Oil Crops", "Sugar Crops", "Other Crops"]
LIVESTOCK_LEAVES = [
    "Ruminant|Meat", "Ruminant|Dairy",
    "Non-Ruminant|Meat|Pig", "Non-Ruminant|Meat|Poultry", "Non-Ruminant|Eggs",
]
LIVESTOCK_PARENTS = {
    "Ruminant": ["Ruminant|Meat", "Ruminant|Dairy"],
    "Non-Ruminant|Meat": ["Non-Ruminant|Meat|Pig", "Non-Ruminant|Meat|Poultry"],
    "Non-Ruminant": ["Non-Ruminant|Meat|Pig", "Non-Ruminant|Meat|Poultry", "Non-Ruminant|Eggs"],
}
PRICE_CROPS = {"Wheat": "wheat", "Rice": "rice", "Maize": "corn", "Soybean": "soyabean"}


# --------------------------------------------------------------------------
# options / naming
# --------------------------------------------------------------------------
@dataclass
class IamcOptions:
    model: str
    region: str
    scenario_names: Dict[str, str] = field(default_factory=dict)
    kyoto_gwp: str = "AR4"  # common-definitions note: prefer AR4 GWP-100 for Kyoto Gases
    out_dir: Optional[Path] = None  # default: <run_dir>/iamc


def suggest_model_name(country: str) -> str:
    country = (country or "").strip()
    return f"FABLE-{country}" if country and country != "Unknown" else "FABLE"


def resolve_model_name(
    explicit: Optional[str],
    configured: Optional[str],
    country: str,
    *,
    interactive: bool = False,
) -> str:
    """CLI flag > config > ask the user (TTY only) > ``FABLE-<country>``."""
    for name in (explicit, configured):
        if name and name.strip():
            return name.strip()
    suggestion = suggest_model_name(country)
    if interactive:
        try:
            got = input(
                f"IAMC model name (may include a version, e.g. '{suggestion} v1') "
                f"[{suggestion}]: "
            ).strip()
        except EOFError:
            got = ""
        if got:
            return got
    return suggestion


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "_", text).strip("_") or "model"


# --------------------------------------------------------------------------
# reference data
# --------------------------------------------------------------------------
def load_products() -> pd.DataFrame:
    df = pd.read_csv(PRODUCTS_CSV, comment="#", dtype={"iamc_group": str})
    df["iamc_group"] = df["iamc_group"].fillna("")
    return df.set_index("product")


def load_iamc_variables() -> Dict[str, set]:
    out: Dict[str, set] = {}
    with VARIABLES_CSV.open(encoding="utf-8") as fh:
        rows = (line for line in fh if not line.startswith("#"))
        for r in csv.DictReader(rows):
            out.setdefault(r["variable"], set()).add(r["unit"])
    return out


def definitions_revision() -> str:
    first = VARIABLES_CSV.read_text(encoding="utf-8").splitlines()[0]
    return first.lstrip("# ").strip()


# --------------------------------------------------------------------------
# collector
# --------------------------------------------------------------------------
class _Collector:
    def __init__(self) -> None:
        self.frames: List[pd.DataFrame] = []
        self.report: Dict[Tuple[str, str], Tuple[str, str]] = {}
        self.notes: List[str] = []

    def emit(self, variable: str, unit: str, s: pd.Series, source: str, note: str = "") -> None:
        """``s`` is indexed by (pathway, year)."""
        s = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if s.empty:
            return
        df = s.rename("value").reset_index()
        df.columns = ["pathway", "year", "value"]
        df["variable"], df["unit"] = variable, unit
        self.frames.append(df)
        self.report.setdefault((variable, unit), (source, note))


def _read(run_dir: Path, sheet: str, table: str, col: _Collector) -> Optional[pd.DataFrame]:
    p = Path(run_dir) / COMBINED / f"{sheet}__{table}__all_pathways.csv"
    if not p.exists():
        col.notes.append(f"missing table {sheet}/{table}: its IAMC variables were skipped")
        return None
    df = pd.read_csv(p)
    df = df.rename(columns={"RunPathway": "pathway", "Year": "year", "YEAR": "year"})
    if "pathway" not in df or "year" not in df:
        col.notes.append(f"table {sheet}/{table} has no RunPathway/Year column: skipped")
        return None
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    return df


def _idx(df: pd.DataFrame, values) -> pd.Series:
    return pd.Series(np.asarray(values, dtype=float),
                     index=pd.MultiIndex.from_frame(df[["pathway", "year"]]))


def _sum_by(df: pd.DataFrame, value_col: str, key_col: str) -> pd.DataFrame:
    """(pathway, year) x key wide table of sums."""
    return df.pivot_table(index=["pathway", "year"], columns=key_col,
                          values=value_col, aggfunc="sum", fill_value=0.0)


def _col(wide: pd.DataFrame, key: str) -> pd.Series:
    return wide[key] if key in wide.columns else pd.Series(0.0, index=wide.index)


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------
def _land(run_dir: Path, c: _Collector) -> None:
    L = _read(run_dir, "LAND", "ResultsLand", c)
    if L is None:
        return
    src = "LAND/ResultsLand"
    forest = L["Forest"] + L.get("NewForest", 0.0)
    c.emit("Land Cover", MHA, _idx(L, L["TOTAL"] / 1e3), f"{src}.TOTAL")
    c.emit("Land Cover|Cropland", MHA, _idx(L, L["Cropland"] / 1e3), f"{src}.Cropland")
    c.emit("Land Cover|Pasture", MHA, _idx(L, L["Pasture"] / 1e3), f"{src}.Pasture")
    c.emit("Land Cover|Forest", MHA, _idx(L, forest / 1e3), f"{src}.Forest + NewForest")
    c.emit("Land Cover|Built-Up Area", MHA, _idx(L, L["Urban"] / 1e3), f"{src}.Urban")
    c.emit("Land Cover|Other Natural", MHA, _idx(L, L["OtherLand"] / 1e3), f"{src}.OtherLand",
           "FABLE 'other land' = natural non-forest land (grassland, shrubland, sparse/bare)")

    # Changes are per model period; convert to per-year rates, first year dropped.
    L = L.assign(_forest=forest, _new=L.get("NewForest", 0.0)).sort_values(["pathway", "year"])
    g = L.groupby("pathway")
    dt = g["year"].diff()
    ok = dt > 0
    rate = "million ha/yr"
    Lk = L[ok]
    c.emit("Forest Area Change", rate,
           _idx(Lk, (g["_forest"].diff()[ok] / dt[ok] / 1e3)),
           f"{src}: d(Forest + NewForest)/dt", "first model year has no prior period and is omitted")
    if "MatureForest" in L:
        c.emit("Forest Area Change|Deforestation", rate,
               _idx(Lk, (-L.loc[ok, "MatureForest"]).clip(lower=0) / dt[ok] / 1e3),
               f"{src}: loss of MatureForest per period / dt", "reported as positive area lost")
    c.emit("Forest Area Change|Forest Expansion", rate,
           _idx(Lk, g["_new"].diff()[ok].clip(lower=0) / dt[ok] / 1e3),
           f"{src}: increase of NewForest per period / dt")


def _production_trade_demand(run_dir: Path, prods: pd.DataFrame, c: _Collector):
    P = _read(run_dir, "PRODUCTION", "ResultsProd", c)
    T = _read(run_dir, "TRADE", "ResultsTrade", c)

    def classify(df: pd.DataFrame, pcol: str) -> pd.DataFrame:
        df = df.copy()
        df["product"] = df[pcol].astype(str).str.strip().str.lower()
        unknown = sorted(set(df["product"]) - set(prods.index))
        if unknown:
            c.notes.append(f"products not in products.csv (ignored): {', '.join(unknown)}")
        df = df[df["product"].isin(prods.index)]
        df = df.join(prods, on="product")
        return df[df["kind"] != "exclude"]

    def first_scen(df: pd.DataFrame) -> pd.DataFrame:
        if "PriceScen" in df and df["PriceScen"].nunique() > 1:
            keep = df["PriceScen"].iloc[0]
            c.notes.append(f"several PriceScen values; used '{keep}'")
            df = df[df["PriceScen"] == keep]
        return df

    prod_tot = trade_tot = None
    if P is not None:
        P = classify(first_scen(P), "Product")
        P["dm"] = P["prodq_feas"].astype(float) * P["dm_share"] / 1e3
        prim = P[P["kind"].isin(["crop", "livestock"])]
        src = "PRODUCTION/ResultsProd.prodq_feas x DM share (products.csv)"
        prod_tot = _emit_commodity_tree(c, "Agricultural Production", prim, src,
                                        "primary products only; processed products excluded to avoid double counting")
        _prices(c, P)
    if T is not None:
        T = classify(first_scen(T), "PRODUCT")
        T = T[T["kind"].isin(["crop", "livestock", "processed"])]
        T["dm"] = (T["ExportQ_feas"].astype(float) - T["ImportQ_feas"].astype(float)) * T["dm_share"] / 1e3
        src = "TRADE/ResultsTrade (ExportQ_feas - ImportQ_feas) x DM share"
        trade_tot = _emit_commodity_tree(c, "Trade|Agriculture", T, src,
                                         "net exports; processed products (oils, cakes, raw sugar) counted in their own DM under the parent crop type")
    if prod_tot is not None and trade_tot is not None:
        src = "Agricultural Production - Trade|Agriculture (apparent consumption)"
        note = "total use (food+feed+other); FABLE has no use split at product level"
        for key in ("", "|Crops", "|Livestock"):
            p, t = prod_tot[key], trade_tot[key]
            d = p.sub(t, fill_value=0.0).loc[p.index]
            c.emit(f"Agricultural Demand{key}", MDM, d, src, note)


def _emit_commodity_tree(c: _Collector, root: str, df: pd.DataFrame, src: str, note: str):
    crops = df[df["kind"].isin(["crop", "processed"])]
    live = df[df["kind"] == "livestock"]
    totals = {}
    cw = _sum_by(crops.assign(g=crops["iamc_group"]), "dm", "g")
    lw = _sum_by(live.assign(g=live["iamc_group"]), "dm", "g")
    for ct in CROP_TYPES:
        c.emit(f"{root}|Crops|{ct}", MDM, _col(cw, ct), src, note)
    for leaf in LIVESTOCK_LEAVES:
        c.emit(f"{root}|Livestock|{leaf}", MDM, _col(lw, leaf), src, note)
    for parent, kids in LIVESTOCK_PARENTS.items():
        c.emit(f"{root}|Livestock|{parent}", MDM, sum(_col(lw, k) for k in kids), src, note)
    totals["|Crops"] = cw.sum(axis=1)
    totals["|Livestock"] = lw.sum(axis=1)
    totals[""] = totals["|Crops"].add(totals["|Livestock"], fill_value=0.0)
    c.emit(f"{root}|Crops", MDM, totals["|Crops"], src, note)
    c.emit(f"{root}|Livestock", MDM, totals["|Livestock"], src,
           note + "; total includes products without an IAMC sub-category (e.g. other meat, honey)")
    c.emit(root, MDM, totals[""], src, note)
    return totals


def _prices(c: _Collector, P: pd.DataFrame) -> None:
    unit = f"Index ({PRICE_BASE_YEAR} = 1)"
    src = f"PRODUCTION/ResultsProd.price_usd, base year {PRICE_BASE_YEAR}"
    P = P[P["kind"].isin(["crop", "livestock"])].copy()
    P["price_usd"] = pd.to_numeric(P["price_usd"], errors="coerce")
    base = P[P["year"] == PRICE_BASE_YEAR][["pathway", "product", "price_usd", "prodq_feas"]]
    base = base.rename(columns={"price_usd": "p0", "prodq_feas": "q0"})
    P = P.merge(base, on=["pathway", "product"], how="inner")
    P = P[(P["p0"] > 0) & P["price_usd"].notna()]
    if P.empty:
        c.notes.append(f"no prices for base year {PRICE_BASE_YEAR}: price indices skipped")
        return
    for iamc, prod in PRICE_CROPS.items():
        x = P[P["product"] == prod]
        if not x.empty:
            c.emit(f"Price|Agriculture|Food Products|Crops|{iamc} [Index]", unit,
                   _idx(x, x["price_usd"] / x["p0"]), src)
    note = f"Laspeyres index, weights = {PRICE_BASE_YEAR} production quantity x price"
    P["num"], P["den"] = P["price_usd"] * P["q0"], P["p0"] * P["q0"]
    for name, mask in (("Food Products|Crops", P["kind"] == "crop"),
                       ("Food Products|Livestock", P["kind"] == "livestock"),
                       ("Food Products", P["kind"].notna())):
        g = P[mask].groupby(["pathway", "year"])[["num", "den"]].sum()
        c.emit(f"Price|Agriculture|{name} [Index]", unit, g["num"] / g["den"], src, note)


def _yields(run_dir: Path, prods: pd.DataFrame, c: _Collector) -> None:
    A = _read(run_dir, "LAND", "ResultsCropArea", c)
    if A is None:
        return
    A = A.assign(product=A["CROP"].astype(str).str.strip().str.lower())
    A = A[A["product"].isin(prods.index)].join(prods, on="product")
    A = A[A["kind"] == "crop"]
    A["dm"] = A["FeasProd"].astype(float) * A["dm_share"]  # kt DM
    A["ha"] = A["FeasHarvarea"].astype(float)  # kha
    g = A.groupby(["pathway", "year", "iamc_group"])[["dm", "ha"]].sum()
    y = (g["dm"] / g["ha"].where(g["ha"] > 0)).unstack("iamc_group")
    for ct in CROP_TYPES:
        if ct in y:
            c.emit(f"Yield|Cropland|{ct} [Harvested Area]", "t DM/ha/yr", y[ct],
                   "LAND/ResultsCropArea: sum(FeasProd x DM) / sum(FeasHarvarea)")


def _food(run_dir: Path, c: _Collector) -> None:
    D = _read(run_dir, "FOOD", "Results_Diets", c)
    if D is None:
        return
    unknown = sorted(set(D["PROD_GROUP"]) - set(DIET_GROUPS))
    if unknown:
        c.notes.append(f"diet groups not mapped (total only): {', '.join(unknown)}")
    D = D.assign(path=D["PROD_GROUP"].map(DIET_GROUPS))
    w = _sum_by(D.assign(path=D["path"].fillna("_total_only")), "kcal_calc", "path")
    src, unit = "FOOD/Results_Diets.kcal_calc", "kcal/cap/day"

    def tot(prefix: str) -> pd.Series:
        cols = [k for k in w.columns if k == prefix or k.startswith(prefix + "|")]
        return w[cols].sum(axis=1) if cols else pd.Series(0.0, index=w.index)

    def name(path: str) -> str:
        return f"Food Availability|{path} [per capita]"

    for ct in CROP_TYPES:
        c.emit(name(f"Crops|{ct}"), unit, tot(f"Crops|{ct}"), src)
    for leaf in LIVESTOCK_LEAVES:
        c.emit(name(f"Livestock|{leaf}"), unit, tot(f"Livestock|{leaf}"), src)
    for parent in LIVESTOCK_PARENTS:
        c.emit(name(f"Livestock|{parent}"), unit, tot(f"Livestock|{parent}"), src)
    c.emit(name("Crops"), unit, tot("Crops"), src, "includes alcoholic beverages")
    c.emit(name("Livestock"), unit, tot("Livestock"), src, "includes animal fats")
    c.emit("Food Availability [per capita]", unit, w.sum(axis=1), src,
           "FABLE computed diet (kcal_calc); total also includes fish and other items")


def _gwps(run_dir: Path, c: _Collector) -> Dict[Tuple[str, str], Tuple[float, float]]:
    out = {}
    G = Path(run_dir) / COMBINED / "GHG__GWP_Conversion__all_pathways.csv"
    if G.exists():
        g = pd.read_csv(G)
        for r in g.itertuples(index=False):
            out[(r.RunPathway, r.GWP_Scen)] = (float(r.CH4), float(r.N2O))
    return out


def _ghg(run_dir: Path, opts: IamcOptions, c: _Collector) -> None:
    G = _read(run_dir, "GHG", "ResultsGHG", c)
    if G is None:
        return
    table = _gwps(run_dir, c)
    if G["GWP_Scen"].nunique() > 1:  # one GWP basis is enough to recover gas masses
        keep = "AR6" if (G["GWP_Scen"] == "AR6").any() else G["GWP_Scen"].iloc[0]
        G = G[G["GWP_Scen"] == keep].reset_index(drop=True)

    def gwp(pathway: str, scen: str) -> Tuple[float, float]:
        return table.get((pathway, scen)) or GWP_FALLBACK[scen]

    gwp_run = np.array([gwp(p, s) for p, s in zip(G["pathway"], G["GWP_Scen"])])
    gwp_ky = np.array([gwp(p, opts.kyoto_gwp) for p in G["pathway"]])
    ch4_live = G["LiveCH4"] / gwp_run[:, 0]  # Mt CH4
    ch4_crop = G["CropCH4"] / gwp_run[:, 0]
    n2o_live = G["LiveN2O"] / gwp_run[:, 1] * 1e3  # kt N2O
    n2o_crop = G["CropN2O"] / gwp_run[:, 1] * 1e3
    co2_agri = G["CropCO2"]
    co2_land = G["LandCO2"]
    src = "GHG/ResultsGHG (CO2e / GWP of the run's GWP_Scen)"

    E = lambda v, u, x, s=src, n="": c.emit(v, u, _idx(G, x), s, n)  # noqa: E731
    E("Emissions|CH4|AFOLU", "Mt CH4/yr", ch4_live + ch4_crop)
    E("Emissions|CH4|AFOLU|Agriculture", "Mt CH4/yr", ch4_live + ch4_crop, n="livestock + crops (rice, residue burning)")
    E("Emissions|CH4|AFOLU|Agriculture|Livestock", "Mt CH4/yr", ch4_live)
    E("Emissions|N2O|AFOLU", "kt N2O/yr", n2o_live + n2o_crop)
    E("Emissions|N2O|AFOLU|Agriculture", "kt N2O/yr", n2o_live + n2o_crop)
    E("Emissions|N2O|AFOLU|Agriculture|Livestock", "kt N2O/yr", n2o_live)
    E("Emissions|N2O|AFOLU|Agriculture|Managed Soils", "kt N2O/yr", n2o_crop,
      n="FABLE crop N2O (synthetic fertiliser, manure applied, residues)")
    E("Emissions|CO2|AFOLU|Agriculture", "Mt CO2/yr", co2_agri, n="FABLE crop CO2 (CropCO2)")
    E("Emissions|CO2|AFOLU|Land", "Mt CO2/yr", co2_land, n="deforestation, other-land change, sequestration, SOC")
    E("Emissions|CO2|AFOLU", "Mt CO2/yr", co2_agri + co2_land)

    parts = [p for p in ("DeforCO2", "OtherLandCO2", "LandSeqReg", "LandSeqAffor",
                         "SOCLandCO2", "SOCAgroecoCO2") if p in G]
    comp = pd.concat([G[parts].astype(float), co2_agri.rename("CropCO2")], axis=1)
    resid = (G[parts].sum(axis=1) - co2_land).abs().max()
    if resid > 1e-6:
        c.notes.append(f"LandCO2 != sum of land components (max diff {resid:.3g}); gross split approximate")
    E("Gross Emissions|CO2|AFOLU", "Mt CO2/yr", comp.clip(lower=0).sum(axis=1),
      n="sum of positive CO2 components")
    E("Gross Removals|CO2|AFOLU", "Mt CO2/yr", comp.clip(upper=0).sum(axis=1),
      n="sum of negative CO2 components (sign as in common-definitions: net = gross emissions + gross removals)")

    k_ch4, k_n2o = gwp_ky[:, 0], gwp_ky[:, 1]
    ksrc = f"GHG/ResultsGHG gases re-aggregated with {opts.kyoto_gwp} GWP-100"
    live_k = ch4_live * k_ch4 + n2o_live / 1e3 * k_n2o
    agri_k = live_k + ch4_crop * k_ch4 + n2o_crop / 1e3 * k_n2o + co2_agri
    E("Emissions|Kyoto Gases|AFOLU|Agriculture|Livestock", "Mt CO2-equiv/yr", live_k, ksrc)
    E("Emissions|Kyoto Gases|AFOLU|Agriculture|Managed Soils", "Mt CO2-equiv/yr", n2o_crop / 1e3 * k_n2o, ksrc)
    E("Emissions|Kyoto Gases|AFOLU|Agriculture", "Mt CO2-equiv/yr", agri_k, ksrc)
    E("Emissions|Kyoto Gases|AFOLU|Land", "Mt CO2-equiv/yr", co2_land, ksrc)
    E("Emissions|Kyoto Gases|AFOLU", "Mt CO2-equiv/yr", agri_k + co2_land, ksrc)


def _simple(run_dir: Path, c: _Collector) -> None:
    N = _read(run_dir, "N_and_P", "ResultsNitrogen", c)
    if N is not None:
        src, u = "N_and_P/ResultsNitrogen", "Tg N/yr"
        syn, org = N["CalcNsynth"] / 1e3, N["CalcNAppSoils"] / 1e3
        c.emit("Fertilizer Use|Nitrogen|Synthetic", u, _idx(N, syn), f"{src}.CalcNsynth")
        c.emit("Fertilizer Use|Nitrogen|Organic", u, _idx(N, org), f"{src}.CalcNAppSoils",
               "manure applied to soils (excludes manure left on pasture)")
        c.emit("Fertilizer Use|Nitrogen", u, _idx(N, syn + org), f"{src}: synthetic + organic")

    W = _read(run_dir, "WATER", "ResultsWater", c)
    if W is not None:
        src = "WATER/ResultsWater"
        c.emit("Water Consumption|Irrigation", "km3/yr", _idx(W, W["CalcIrrRequirements"] / 1e3),
               f"{src}.CalcIrrRequirements", "crop irrigation water requirement, million m3 -> km3")
        if (W["CalcIrrWithdrawals"].fillna(0) != 0).any():
            c.emit("Water Withdrawal|Irrigation", "km3/yr", _idx(W, W["CalcIrrWithdrawals"] / 1e3),
                   f"{src}.CalcIrrWithdrawals")
        else:
            c.notes.append("Irrigation withdrawals are zero in this workbook (WATER/ResultsWater."
                           "CalcIrrWithdrawals), so Water Withdrawal|Irrigation is not reported")

    J = _read(run_dir, "JOBS", "ResultsJobs", c)
    if J is not None:
        src = "JOBS/ResultsJobs"
        c.emit("Labor Force|Employed|Agriculture", "million full-time equivalent workers",
               _idx(J, J["onfarm_total"] / 1e3), f"{src}.onfarm_total", "on-farm crop + livestock jobs")
        c.emit("Labor Force|Active", "million", _idx(J, J["ActivePop"] / 1e3), f"{src}.ActivePop")


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------
@dataclass
class IamcResult:
    data: pd.DataFrame  # long: model, scenario, region, variable, unit, year, value
    mapping: pd.DataFrame  # variable, unit, source, note
    notes: List[str]
    invalid: List[Tuple[str, str]]
    scenario_to_pathway: Dict[str, str] = field(default_factory=dict)
    # scenario -> {lever: value}, from <run_dir>/pathway_levers.csv when present
    levers: Dict[str, Dict[str, str]] = field(default_factory=dict)


def build_iamc(run_dir: Path, opts: IamcOptions) -> IamcResult:
    run_dir = Path(run_dir)
    c = _Collector()
    prods = load_products()
    for section in (
        lambda: _land(run_dir, c),
        lambda: _production_trade_demand(run_dir, prods, c),
        lambda: _yields(run_dir, prods, c),
        lambda: _food(run_dir, c),
        lambda: _ghg(run_dir, opts, c),
        lambda: _simple(run_dir, c),
    ):
        try:
            section()
        except Exception as exc:  # one bad table must not sink the rest
            c.notes.append(f"section failed: {type(exc).__name__}: {exc}")

    cols = ["model", "scenario", "region", "variable", "unit", "year", "value"]
    if not c.frames:
        return IamcResult(pd.DataFrame(columns=cols), pd.DataFrame(), c.notes, [])
    df = pd.concat(c.frames, ignore_index=True)
    df["model"], df["region"] = opts.model, opts.region
    df["scenario"] = df["pathway"].map(lambda p: opts.scenario_names.get(p, p))
    scen_map = dict(zip(df["scenario"], df["pathway"]))  # workbook pathway order
    order = {s: i for i, s in enumerate(scen_map)}
    df = (df.assign(_o=df["scenario"].map(order))
            .sort_values(["_o", "variable", "year"])[cols].reset_index(drop=True))

    allowed = load_iamc_variables()
    invalid = sorted({(v, u) for v, u in zip(df["variable"], df["unit"])
                      if u not in allowed.get(v, ())})
    mapping = pd.DataFrame(
        [(v, u, s, n) for (v, u), (s, n) in sorted(c.report.items())],
        columns=["variable", "unit", "source", "note"],
    )
    levers: Dict[str, Dict[str, str]] = {}
    try:
        from fable.compute.design import read_levers

        lv = read_levers(run_dir)
        if lv is not None and "PATHWAY" in lv.columns:
            by_path = {str(r["PATHWAY"]): {k: str(v) for k, v in r.items() if k != "PATHWAY"}
                       for r in lv.to_dict("records")}
            levers = {s: by_path[p] for s, p in scen_map.items() if p in by_path}
    except Exception as exc:  # meta is a bonus; never fail the export on it
        c.notes.append(f"lever settings not read: {exc}")
    return IamcResult(df, mapping, c.notes, invalid, scen_map, levers)


def to_wide(long: pd.DataFrame) -> pd.DataFrame:
    """IAMC wide layout; rows keep the scenario order of ``long``."""
    order = {s: i for i, s in enumerate(dict.fromkeys(long["scenario"]))}
    w = long.pivot_table(index=["model", "scenario", "region", "variable", "unit"],
                         columns="year", values="value", aggfunc="first")
    w.columns = [int(y) for y in w.columns]
    w = w.reset_index()
    w = (w.assign(_o=w["scenario"].map(order)).sort_values(["_o", "variable"])
          .drop(columns="_o").reset_index(drop=True))
    w.columns = [str(col).capitalize() if isinstance(col, str) else col for col in w.columns]
    return w


ABOUT_TEXT = [
    ("Format", "IAMC wide format: one row per Model, Scenario, Region, Variable, Unit; one column per year."),
    ("Variable names", "Names and units follow IAMconsortium/common-definitions "
                  "(https://github.com/IAMconsortium/common-definitions)."),
    ("Scenario names", "One scenario per FABLE pathway; the meta sheet links each scenario to its pathway."),
    ("Dry matter", "Production, trade and demand are in million t dry matter. FABLE fresh-weight "
                   "quantities are multiplied by product dry-matter shares (fable/iamc/products.csv)."),
    ("Trade and demand", "Trade is net exports. Oils, cakes and raw sugar count in trade only, under their "
                         "parent crop type. Demand = production - net exports (total use)."),
    ("Food", "Food Availability is the FABLE computed diet in kcal per person per day."),
    ("Emissions", "Gas masses are recovered from FABLE CO2e with the run's GWP values; "
                  "Kyoto Gases are re-aggregated with the GWP-100 basis given below."),
    ("Mapping", "The mapping sheet lists the FABLE table, column and conversion behind every variable."),
]


def _format_xlsx(path: Path) -> None:
    """Readable defaults for people opening the file in Excel."""
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font

    wb = load_workbook(path)
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(bold=True)
        widths: Dict[int, int] = {}
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 400)):
            for cell in row:
                if cell.value is not None and not isinstance(cell.value, float):
                    widths[cell.column] = max(widths.get(cell.column, 0), len(str(cell.value)))
        for col, w in widths.items():
            ws.column_dimensions[ws.cell(1, col).column_letter].width = min(max(w + 2, 9), 70)
    if "data" in wb.sheetnames:
        ws = wb["data"]
        ws.freeze_panes = "F2"
        ws.auto_filter.ref = ws.dimensions
        if ws.max_row <= 20_000:  # per-cell formats are slow; large files keep Excel's default
            for row in ws.iter_rows(min_row=2, min_col=6):
                for cell in row:
                    cell.number_format = "#,##0.000"
        for col in range(6, ws.max_column + 1):
            ws.column_dimensions[ws.cell(1, col).column_letter].width = 11
    if "about" in wb.sheetnames:
        ws = wb["about"]
        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["B"].width = 110
        for row in ws.iter_rows(min_row=2):
            row[1].alignment = Alignment(wrap_text=True, vertical="top")
            row[0].alignment = Alignment(vertical="top")
    wb.save(path)


def write_iamc(result: IamcResult, out_dir: Path, opts: IamcOptions,
               source: Optional[Dict[str, str]] = None) -> Dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{_slug(opts.model)}_iamc"
    wide = to_wide(result.data) if not result.data.empty else pd.DataFrame()
    paths = {"csv": out_dir / f"{stem}.csv", "xlsx": out_dir / f"{stem}.xlsx",
             "mapping": out_dir / "iamc_mapping.csv"}
    wide.to_csv(paths["csv"], index=False)

    scen = list(result.scenario_to_pathway)
    meta = pd.DataFrame({
        "Model": opts.model, "Scenario": scen,
        "fable_pathway": [result.scenario_to_pathway.get(s, s) for s in scen],
        "exclude": False,
    })
    if result.levers:  # one column per scenario lever, as pyam meta indicators
        keys = list(next(iter(result.levers.values())).keys())
        for k in keys:
            meta[k] = [result.levers.get(s, {}).get(k, "") for s in scen]
    about = [("Model", opts.model), ("Region", opts.region)]
    about += [(k, v) for k, v in (source or {}).items() if v]
    about += [("Scenarios", ", ".join(scen)),
              ("Variables", str(wide["Variable"].nunique()) if "Variable" in wide else "0"),
              ("Kyoto Gases GWP-100", opts.kyoto_gwp),
              ("common-definitions", definitions_revision())]
    about += ABOUT_TEXT
    about += [("Note", n) for n in result.notes]
    about += [("Not in common-definitions", f"{v} [{u}]") for v, u in result.invalid]
    with pd.ExcelWriter(paths["xlsx"], engine="openpyxl") as xw:
        pd.DataFrame(about, columns=["item", "value"]).to_excel(xw, sheet_name="about", index=False)
        wide.to_excel(xw, sheet_name="data", index=False)
        meta.to_excel(xw, sheet_name="meta", index=False)
        result.mapping.to_excel(xw, sheet_name="mapping", index=False)
    try:
        _format_xlsx(paths["xlsx"])
    except Exception:  # formatting is cosmetic; the data is already written
        pass
    result.mapping.to_csv(paths["mapping"], index=False)
    return paths


def bundle_section(result: IamcResult, opts: IamcOptions) -> Dict[str, object]:
    """The ``iamc`` block embedded in bundle.json (schema >= 1.1.0)."""
    from fable.compute.model import _clean

    wide = to_wide(result.data) if not result.data.empty else pd.DataFrame(
        columns=["Model", "Scenario", "Region", "Variable", "Unit"])
    notes = list(result.notes) + [f"not in common-definitions: {v} [{u}]" for v, u in result.invalid]
    return {
        "model": opts.model,
        "region": opts.region,
        "kyoto_gwp": opts.kyoto_gwp,
        "definitions": definitions_revision(),
        "scenarios": [
            {"scenario": s, "pathway": p, **({"levers": result.levers[s]} if s in result.levers else {})}
            for s, p in result.scenario_to_pathway.items()
        ],
        "data": {
            "columns": [str(c) for c in wide.columns],
            "rows": [[_clean(v) for v in r] for r in wide.astype(object).itertuples(index=False)],
        },
        "mapping": {
            "columns": list(result.mapping.columns),
            "rows": [[_clean(v) for v in r] for r in result.mapping.astype(object).itertuples(index=False)],
        },
        "notes": notes,
    }


def _source_info(run_dir: Path, workbook: Optional[Path]) -> Dict[str, str]:
    from datetime import datetime, timezone

    info = {"FABLE workbook": Path(workbook).name if workbook else "",
            "Run": Path(run_dir).name,
            "Exported": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    manifest = Path(run_dir) / "run_manifest.csv"
    if manifest.exists():
        try:
            m = pd.read_csv(manifest)
            ok = (m["Status"].astype(str).str.lower() == "ok").sum()
            info["Pathways recalculated"] = f"{ok} of {len(m)} OK"
        except Exception:
            pass
    return info


def export_iamc(run_dir: Path, opts: IamcOptions, *, log=None,
                result: Optional[IamcResult] = None,
                workbook: Optional[Path] = None) -> Dict[str, Path]:
    """Build + write; prints a one-line summary and any notes to ``log`` (stderr)."""
    log = log or (lambda m: print(m, file=sys.stderr))
    result = result if result is not None else build_iamc(run_dir, opts)
    out = Path(opts.out_dir) if opts.out_dir else Path(run_dir) / "iamc"
    paths = write_iamc(result, out, opts, source=_source_info(run_dir, workbook))
    n_var = result.data["variable"].nunique() if not result.data.empty else 0
    n_scen = len(result.scenario_to_pathway)
    log(f"IAMC: {n_var} variables x {n_scen} scenarios -> {paths['csv']}")
    for note in result.notes:
        log(f"  note: {note}")
    for v, u in result.invalid:
        log(f"  WARNING not in common-definitions: {v} [{u}]")
    return paths
