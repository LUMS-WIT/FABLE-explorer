# Pathway Comparisons & Deviation Analysis

## Policy Questions This Addresses

FABLE pathway comparisons are designed to answer questions like:

- How can a country increase food production to meet population growth while keeping emissions within sustainable limits?
- What mix of agricultural and climate policies could help achieve national NDC and adaptation targets?
- How can land-use planning balance crop expansion, forest protection, and biodiversity conservation?
- What are the potential benefits of improving irrigation efficiency and adopting climate-smart farming practices?
- How will changes in diet, population, and income affect food demand, trade, and nutrition outcomes?
- What is the potential role of renewable energy in agriculture?
- How can incentives and subsidies be redesigned to encourage sustainable and resilient farming systems?

---

## Concept

A FABLE Explorer run produces outputs for multiple pathways (scenarios). Comparison analysis measures how each pathway diverges from a chosen **baseline**, typically `CurrentTrends`.

This allows quantifying:
- GHG emissions change under `HealthyDiet` vs. `CurrentTrends`
- Which pathways converge to similar land-use outcomes by 2050
- Trade-offs between biodiversity gain and food production across scenarios

---

## Baseline Selection

Default baseline pathway is `CurrentTrends`.

`src/comparison.py` selects the baseline by:
1. Checking for `CurrentTrends` in available pathway names (exact match)
2. Falling back to the first pathway alphabetically if not found

Pass a custom baseline name to `choose_baseline_pathway()`.

---

## Deviation Summary

`export_scenario_deviation_summary()` computes absolute and percentage deviations between each pathway and the baseline for every output variable and year. Written to `scenario_deviation_summary.csv` in the run directory.

Key columns in the deviation summary:

| Column | Description |
|---|---|
| `Table` | Source output sheet (e.g., GHG, LAND) |
| `Metric` | Output variable name |
| `BaselinePathway` | Reference pathway |
| `BaselineValue` | Baseline value for that variable/year |
| `MaxAbsDiffVsBaseline` | Largest absolute deviation vs. baseline across pathways |
| `MaxPctDiffVsBaseline` | Largest percentage deviation vs. baseline |
| `SignificantDeviation` | Boolean — exceeds both abs and pct thresholds |
| `SpreadAbs` | Max minus min across all pathways |
| `SpreadPct` | Spread as percentage of mean absolute value |

---

## Dashboard Comparison View

`src/dashboard.py` surfaces comparisons interactively across four tabs:

- **Curated Charts** — pre-built charts per output domain for a selected pathway (column names are workbook-specific; adapt for your country)
- **Combined Tables** — explore any output table with pathway overlay, baseline delta, and % delta modes
- **Deviation Analysis** — ranked list of metrics with strongest pathway divergence; drill into charts for top deviations
- **Chart Series** — raw chart series data extracted from Excel, with pathway overlay and baseline comparison

---

## Key Helpers (`src/comparison.py`)

| Function | Purpose |
|---|---|
| `detect_pathway_col(columns)` | Finds the `RunPathway` column in a DataFrame |
| `detect_year_col(columns)` | Finds the `Year` column |
| `choose_baseline_pathway(names)` | Returns the best baseline from available pathways |
| `apply_baseline_mode(df, baseline)` | Reindexes a DataFrame relative to baseline values |
| `export_scenario_deviation_summary(combined_dir, output_csv)` | Writes full deviation CSV |
| `safe_name(text)` | Sanitizes strings for use in filenames |
| `safe_pct_delta(values, baseline)` | Percentage deviation with zero-baseline handling |
