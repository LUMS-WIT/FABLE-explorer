"""IAMC export against the frozen 6-pathway Pakistan run."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from fable.compute.cli import main as cli_main
from fable.iamc import (
    IamcOptions,
    build_iamc,
    resolve_model_name,
    suggest_model_name,
    to_wide,
    write_iamc,
)
from fable.iamc.export import load_products

GOLDEN_RUN = Path(__file__).parent / "fixtures" / "golden_run"
PATHWAYS = ["Current Trends", "Balanced", "Export Oriented Growth",
            "Mitigation", "Food Security", "Net-Zero"]


@pytest.fixture(scope="module")
def opts():
    return IamcOptions(model="FABLE-Pakistan v1", region="Pakistan")


@pytest.fixture(scope="module")
def result(opts):
    return build_iamc(GOLDEN_RUN, opts)


@pytest.fixture(scope="module")
def wide(result):
    w = to_wide(result.data)
    return w.set_index(["Scenario", "Variable"])


def val(wide, scen, var, year):
    return float(wide.loc[(scen, var), year])


def test_every_variable_is_in_common_definitions(result):
    assert result.invalid == []


def test_scenarios_model_region(result):
    d = result.data
    assert sorted(d["scenario"].unique()) == sorted(PATHWAYS)
    assert set(d["model"]) == {"FABLE-Pakistan v1"}
    assert set(d["region"]) == {"Pakistan"}
    assert d["variable"].nunique() >= 85
    assert d["value"].notna().all()


def test_no_unexpected_notes(result):
    # Only the known all-zero withdrawals note for this workbook.
    assert all("CalcIrrWithdrawals" in n for n in result.notes), result.notes


def test_scenarios_keep_workbook_order(result, wide):
    assert list(result.scenario_to_pathway) == PATHWAYS
    assert list(dict.fromkeys(to_wide(result.data)["Scenario"])) == PATHWAYS


def test_products_table_covers_fixture():
    prods = load_products()
    run = pd.read_csv(GOLDEN_RUN / "combined_tables" / "PRODUCTION__ResultsProd__all_pathways.csv")
    assert set(run["Product"].str.lower()) <= set(prods.index)
    assert prods.loc[prods["kind"] != "exclude", "dm_share"].between(0.01, 1.0).all()


@pytest.mark.parametrize("scen", PATHWAYS)
@pytest.mark.parametrize("year", [2000, 2020, 2050])
def test_aggregates_are_consistent(wide, scen, year):
    v = lambda name: val(wide, scen, name, year)  # noqa: E731
    land = ["Cropland", "Pasture", "Forest", "Built-Up Area", "Other Natural"]
    assert sum(v(f"Land Cover|{x}") for x in land) == pytest.approx(v("Land Cover"), rel=1e-6)
    for root in ("Agricultural Production", "Trade|Agriculture", "Agricultural Demand"):
        assert v(f"{root}|Crops") + v(f"{root}|Livestock") == pytest.approx(v(root), abs=1e-6)
    crops = sum(v(f"Agricultural Production|Crops|{c}")
                for c in ("Cereals", "Oil Crops", "Sugar Crops", "Other Crops"))
    assert crops == pytest.approx(v("Agricultural Production|Crops"), abs=1e-6)
    assert v("Agricultural Demand") == pytest.approx(
        v("Agricultural Production") - v("Trade|Agriculture"), abs=1e-6)
    assert v("Emissions|Kyoto Gases|AFOLU") == pytest.approx(
        v("Emissions|Kyoto Gases|AFOLU|Agriculture") + v("Emissions|Kyoto Gases|AFOLU|Land"), abs=1e-6)
    assert v("Emissions|CO2|AFOLU") == pytest.approx(
        v("Gross Emissions|CO2|AFOLU") + v("Gross Removals|CO2|AFOLU"), abs=1e-6)
    assert v("Fertilizer Use|Nitrogen") == pytest.approx(
        v("Fertilizer Use|Nitrogen|Synthetic") + v("Fertilizer Use|Nitrogen|Organic"), abs=1e-9)


def test_unit_conversions_against_source(wide):
    raw = pd.read_csv(GOLDEN_RUN / "combined_tables" / "GHG__ResultsGHG__all_pathways.csv")
    r = raw[(raw.RunPathway == "Current Trends") & (raw.Year == 2020)].iloc[0]
    # AR6 GWP in this run: CH4 27.2, N2O 273
    assert val(wide, "Current Trends", "Emissions|CH4|AFOLU|Agriculture|Livestock", 2020) == \
        pytest.approx(r.LiveCH4 / 27.2)
    assert val(wide, "Current Trends", "Emissions|N2O|AFOLU|Agriculture", 2020) == \
        pytest.approx(r.AgriN2O / 273 * 1000)
    land = pd.read_csv(GOLDEN_RUN / "combined_tables" / "LAND__ResultsLand__all_pathways.csv")
    lr = land[(land.RunPathway == "Mitigation") & (land.Year == 2050)].iloc[0]
    assert val(wide, "Mitigation", "Land Cover|Cropland", 2050) == pytest.approx(lr.Cropland / 1000)


def test_forest_change_skips_first_year(wide):
    assert pd.isna(wide.loc[("Current Trends", "Forest Area Change"), 2000])
    assert not pd.isna(wide.loc[("Current Trends", "Forest Area Change"), 2005])


def test_scenario_rename(opts):
    o = IamcOptions(model="m", region="Pakistan", scenario_names={"Current Trends": "Baseline"})
    r = build_iamc(GOLDEN_RUN, o)
    assert "Baseline" in set(r.data["scenario"])
    assert "Current Trends" not in set(r.data["scenario"])
    assert r.scenario_to_pathway["Baseline"] == "Current Trends"


def test_model_name_resolution(monkeypatch):
    assert suggest_model_name("Pakistan") == "FABLE-Pakistan"
    assert resolve_model_name("X v2", "Y", "Pakistan") == "X v2"
    assert resolve_model_name(None, "Y", "Pakistan") == "Y"
    assert resolve_model_name(None, None, "Pakistan") == "FABLE-Pakistan"
    monkeypatch.setattr("builtins.input", lambda *_: "FABLE-PAK v3")
    assert resolve_model_name(None, None, "Pakistan", interactive=True) == "FABLE-PAK v3"
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert resolve_model_name(None, None, "Pakistan", interactive=True) == "FABLE-Pakistan"


def test_write_files(result, opts, tmp_path):
    paths = write_iamc(result, tmp_path, opts)
    df = pd.read_csv(paths["csv"])
    assert list(df.columns[:5]) == ["Model", "Scenario", "Region", "Variable", "Unit"]
    assert [int(c) for c in df.columns[5:]] == list(range(2000, 2051, 5))
    meta = pd.read_excel(paths["xlsx"], sheet_name="meta")
    about = pd.read_excel(paths["xlsx"], sheet_name="about")
    assert "Model" in set(about["item"])
    assert list(meta["Scenario"]) == PATHWAYS
    assert paths["mapping"].exists()


def test_missing_tables_degrade(tmp_path, opts):
    run = tmp_path / "run"
    (run / "combined_tables").mkdir(parents=True)
    src = GOLDEN_RUN / "combined_tables" / "LAND__ResultsLand__all_pathways.csv"
    shutil.copy(src, run / "combined_tables" / src.name)
    r = build_iamc(run, opts)
    assert r.invalid == []
    assert set(r.data["variable"]).issuperset({"Land Cover", "Land Cover|Forest"})
    assert any("missing table" in n for n in r.notes)


def test_cli_iamc_subcommand(tmp_path):
    rc = cli_main(["iamc", str(GOLDEN_RUN), "--model", "FABLE-Pakistan v1",
                   "--iamc-out", str(tmp_path), "--no-input"])
    assert rc == 0
    assert (tmp_path / "FABLE_Pakistan_v1_iamc.csv").exists()


def test_bundle_embeds_iamc_and_passes_gate(tmp_path, opts):
    import json

    from fable.compute.pipeline import bundle_from_run_dir

    run = tmp_path / "run"
    shutil.copytree(GOLDEN_RUN, run)
    o = IamcOptions(model=opts.model, region=opts.region)
    bundle, gate = bundle_from_run_dir(run, tmp_path / "out", country="Pakistan",
                                       baseline_pathway="Current Trends", iamc=o)
    assert gate.publishable and gate.schema_ok, gate.render()
    doc = json.loads((tmp_path / "out" / "bundle.json").read_text())
    block = doc["iamc"]
    assert block["model"] == "FABLE-Pakistan v1"
    assert block["data"]["columns"][:5] == ["Model", "Scenario", "Region", "Variable", "Unit"]
    assert len(block["data"]["rows"]) == len(PATHWAYS) * len({r[3] for r in block["data"]["rows"]})
    assert {s["pathway"] for s in block["scenarios"]} == set(PATHWAYS)
    assert (run / "iamc" / "FABLE_Pakistan_v1_iamc.xlsx").exists()


def test_bundle_without_iamc_has_no_block(tmp_path):
    import json

    from fable.compute.pipeline import bundle_from_run_dir

    run = tmp_path / "run"
    shutil.copytree(GOLDEN_RUN, run)
    _, gate = bundle_from_run_dir(run, tmp_path / "out", country="Pakistan")
    assert gate.publishable
    assert "iamc" not in json.loads((tmp_path / "out" / "bundle.json").read_text())
    assert not (run / "iamc").exists()
