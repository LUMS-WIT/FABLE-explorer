"""Pathway designs (no workbook needed) and large runs (synthetic, no Excel)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from fable.compute.bundle import MAX_TABLE_PATHWAYS, build_bundle
from fable.compute.design import Lever, PathwayTable, factorial, load_design, sample
from fable.compute.pipeline import bundle_from_run_dir
from fable.iamc import IamcOptions, build_iamc
from fable.tests.synthetic import make


@pytest.fixture()
def table() -> PathwayTable:
    levers = [
        Lever("S0", "BaseYear", 3, [2010, 2015, 2020]),
        Lever("S1", "Diet", 4, ["NoChange", "EATLancetAverage", "FatDiet"]),
        Lever("S2", "Land", 5, ["NoExpansion", "FreeExpansion"]),
        Lever("S3", "GWP", 6, ["AR5", "AR6"]),
    ]
    df = pd.DataFrame([
        {"PATHWAY": "Current Trends", "BaseYear": 2020, "Diet": "NoChange", "Land": "FreeExpansion", "GWP": "AR6"},
        {"PATHWAY": "Green", "BaseYear": 2020, "Diet": "EATLancetAverage", "Land": "NoExpansion", "GWP": "AR6"},
    ])
    return PathwayTable(levers, 2, 1, 10, 20, df, [10, 11])


def test_factorial_counts_and_fills_from_base(table):
    df = factorial(table, ["Diet", "Land"], base="Current Trends")
    assert len(df) == 6
    assert set(df["BaseYear"]) == {2020} and set(df["GWP"]) == {"AR6"}
    assert df["PATHWAY"].is_unique


def test_sample_is_distinct_and_skips_settings(table):
    df = sample(table, 6, base="Current Trends", seed=3)
    assert len(df) == 6
    assert len(df[["Diet", "Land"]].drop_duplicates()) == 6
    assert set(df["GWP"]) == {"AR6"}  # reporting setting not varied by default
    with pytest.raises(ValueError, match="only 6 distinct"):
        sample(table, 7)


def test_load_design_validates(tmp_path, table):
    good = tmp_path / "good.csv"
    pd.DataFrame([{"PATHWAY": "A", "Diet": "fatdiet"}, {"PATHWAY": "B", "Land": "NoExpansion"}]).to_csv(good, index=False)
    rows = load_design(good, table, base="Current Trends")
    assert rows[0] == ("A", (2020, "FatDiet", "FreeExpansion", "AR6"))  # case-insensitive, typed
    assert rows[1][1][2] == "NoExpansion"

    bad = tmp_path / "bad.csv"
    pd.DataFrame([{"PATHWAY": "A", "Diet": "Pizza", "Colour": "red"},
                  {"PATHWAY": "A", "Diet": "NoChange"}]).to_csv(bad, index=False)
    with pytest.raises(ValueError) as e:
        load_design(bad, table)
    msg = str(e.value)
    assert "unknown lever column" in msg and "Pizza" in msg and "duplicate PATHWAY" in msg


@pytest.fixture(scope="module")
def big_run(tmp_path_factory) -> Path:
    return make(tmp_path_factory.mktemp("big") / "run", n=40, seed=2)


def test_large_run_caps_tables_but_not_iamc(big_run, tmp_path):
    b = build_bundle(big_run, country="Pakistan", baseline_pathway="Current Trends")
    assert len(b.pathways) == 40
    assert b.table_pathways is not None and len(b.table_pathways) == MAX_TABLE_PATHWAYS
    assert b.table_pathways[0] == "Current Trends"
    for t in b.tables:
        idx = t.columns.index(t.pathway_col)
        assert {r[idx] for r in t.rows} <= set(b.table_pathways)
    assert not any(c.startswith("Value__") for c in b.deviation_summary.columns)
    assert b.run_quality.status == "ok"

    r = build_iamc(big_run, IamcOptions(model="m", region="Pakistan"))
    assert len(r.scenario_to_pathway) == 40 and r.invalid == []
    assert r.levers["P0001"].keys() >= {"Diet", "Land", "Afforestation"}


def test_large_run_bundle_passes_gate_with_levers(big_run, tmp_path):
    _, gate = bundle_from_run_dir(big_run, tmp_path / "out", country="Pakistan",
                                  baseline_pathway="Current Trends",
                                  iamc=IamcOptions(model="m", region="Pakistan", out_dir=tmp_path / "iamc"))
    assert gate.publishable and gate.schema_ok, gate.render()
    doc = json.loads((tmp_path / "out" / "bundle.json").read_text())
    assert len(doc["table_pathways"]) == MAX_TABLE_PATHWAYS
    assert "levers" in doc["iamc"]["scenarios"][1]
    meta = pd.read_excel(tmp_path / "iamc" / "m_iamc.xlsx", sheet_name="meta")
    assert {"Diet", "Land"} <= set(meta.columns) and len(meta) == 40
