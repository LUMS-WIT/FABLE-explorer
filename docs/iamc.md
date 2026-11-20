# IAMC export

Every `bundle` / `run` also writes the FABLE results as IAMC-format timeseries,
using variable names and units from
[IAMconsortium/common-definitions](https://github.com/IAMconsortium/common-definitions).
One row per model × scenario × region × variable, one column per year.

```
<run_dir>/iamc/
  <Model>_iamc.csv       wide IAMC table (Model, Scenario, Region, Variable, Unit, 2000 … 2050)
  <Model>_iamc.xlsx      sheets: about (source, conventions, notes), data,
                         meta (scenario ↔ FABLE pathway), mapping
  iamc_mapping.csv       each variable → FABLE table/column, conversion, caveat
```

The same table is embedded in `bundle.json` (optional `iamc` block, schema
1.1.0). On the website the **IAMC export** tab charts any variable across
scenarios and downloads the CSV, so anyone given a `bundle.json` can get the
IAMC file without Python. A bundle built without the export still opens; the
tab then explains how to rebuild it.

## Running it

```bash
# automatically, with the bundle
python -m fable.compute bundle exports/all_pathways_run_XXXX --model "FABLE-Pakistan v1"
python -m fable.compute run workbooks/FABLEPAKUP50.xlsx --model "FABLE-Pakistan v1"

# IAMC only, from an existing run directory
python -m fable.compute iamc exports/all_pathways_run_XXXX --model "FABLE-Pakistan v1"

# switch it off for one run
python -m fable.compute bundle exports/all_pathways_run_XXXX --no-iamc
```

The desktop launcher has an **IAMC model** field and an on/off checkbox; the
result message shows where the IAMC files went.

## Model, scenario, region

| Column | Rule |
| --- | --- |
| Model | `--model`, else `iamc.model` in `config.yaml`, else you are asked (terminal only), else `FABLE-<country>`. Put a version in the name if you want one, e.g. `FABLE-Pakistan v1`. `--no-input` turns the question off (CI). |
| Scenario | FABLE pathway name as-is. Rename with `iamc.scenario_names` in `config.yaml`. |
| Region | `iamc.region`, else `country`. Use the common-definitions country name, e.g. `Pakistan`. |

## What is mapped (91 variables)

| Block | IAMC variables | FABLE source |
| --- | --- | --- |
| Land cover | `Land Cover` and its `Cropland`, `Pasture`, `Forest`, `Built-Up Area` and `Other Natural` children | LAND/ResultsLand |
| Forest change | `Forest Area Change`, `…\|Deforestation`, `…\|Forest Expansion` (per year, first year omitted) | LAND/ResultsLand |
| Production | `Agricultural Production` for crops by crop type, and for livestock (ruminant/non-ruminant, meat/dairy/pig/poultry/eggs) | PRODUCTION/ResultsProd |
| Trade | `Trade\|Agriculture` (net exports), same tree | TRADE/ResultsTrade |
| Demand | `Agricultural Demand`, `…\|Crops`, `…\|Livestock` = production − net exports | derived |
| Yield | `Yield\|Cropland\|<crop type> [Harvested Area]` | LAND/ResultsCropArea |
| Food | `Food Availability … [per capita]`: total, crops by type, livestock tree | FOOD/Results_Diets |
| Emissions | CH4, N2O and CO2 under `Emissions\|<gas>\|AFOLU` (Agriculture, Livestock, Managed Soils, Land); `Gross Emissions/Removals\|CO2\|AFOLU`; `Emissions\|Kyoto Gases\|AFOLU…` | GHG/ResultsGHG |
| Nitrogen | `Fertilizer Use\|Nitrogen`, `…\|Synthetic`, `…\|Organic` | N_and_P/ResultsNitrogen |
| Water | `Water Consumption\|Irrigation` (`Water Withdrawal\|Irrigation` when non-zero) | WATER/ResultsWater |
| Labour | `Labor Force\|Employed\|Agriculture`, `Labor Force\|Active` | JOBS/ResultsJobs |
| Prices | `Price\|Agriculture\|Food Products … [Index]`, 2020 = 1, for crops, livestock, wheat, rice, maize and soybean | PRODUCTION/ResultsProd |

`iamc_mapping.csv` gives the exact column and conversion for each variable.

## Conversions and assumptions

- **Dry matter.** IAMC reports production, trade and demand in `million t DM/yr`.
  FABLE reports fresh weight. Each product is multiplied by its `dm_share` in
  [`fable/iamc/products.csv`](../fable/iamc/products.csv). These shares are
  indicative literature values. Replace them with your own factors where you
  have better ones.
- **Commodity groups.** `products.csv` also assigns each FABLE product to an
  IAMC crop type or livestock product. Soybean, groundnut and cotton count as
  Oil Crops, following the common-definitions description.
- **Processed products** (oils, cakes, raw sugar) enter trade only, under their
  parent crop type and in their own dry matter. They are left out of production
  so nothing is counted twice.
- **Kyoto Gases** are re-aggregated from gas masses with AR4 GWP-100, as the
  common-definitions note recommends. FABLE's own CO2e uses AR6. Set the basis
  with `iamc.kyoto_gwp`.
- **Assumed FABLE units:** 1000 t, 1000 ha, Mt CO2e per gas, million m³ of
  water, and 1000 persons. If your workbook differs, change the divisors in
  `fable/iamc/export.py`.
- **Not mapped.** FABLE has no data for these variables, so the export leaves
  them out: the food/feed/other split of demand, biodiversity (FABLE's LNPP
  share is not MSA or BII), production costs, irrigated vs rainfed cropland,
  and energy crops.

## Validation

Every (variable, unit) pair the export writes is checked against
[`fable/iamc/iamc_variables.csv`](../fable/iamc/iamc_variables.csv), a snapshot
of common-definitions. Its first line records the commit. If a pair is not in
the snapshot, the run prints a warning. The tests also check that aggregates
add up. To refresh the snapshot:

```bash
git clone --depth 1 https://github.com/IAMconsortium/common-definitions.git /tmp/cd
python -m fable.iamc.refresh_definitions /tmp/cd
```

For a full check with the official tool:
`pip install nomenclature-iamc`, then
`nomenclature.DataStructureDefinition("/tmp/cd/definitions", dimensions=["variable","region"]).validate(pyam.IamDataFrame("<file>.csv"))`.
