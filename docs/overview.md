# Overview — FABLE Country Explorer

## About FABLE

The Food, Agriculture, Biodiversity, Land-Use, and Energy (FABLE) Consortium is a collaborative network of research teams across more than 20 countries working to design sustainable pathways for food and land systems. The initiative is coordinated by the Food and Land Use Coalition (FOLU) and the International Institute for Applied Systems Analysis (IIASA). More information at [fableconsortium.org](https://fableconsortium.org).

Each country team develops a national FABLE workbook — an Excel-based model calibrated to local data and policy contexts — and uses it to explore how food, agriculture, land, and energy systems evolve under different scenarios.

## What the FABLE Model Does

The FABLE model is an open-source accounting and scenario analysis tool built in Excel. It quantifies how a country's food, agriculture, land, and energy systems evolve under different policy and climate futures by tracking:

- Food production and demand
- Crop and livestock yields
- Land-use change
- Greenhouse gas emissions
- Biodiversity indicators
- Nutritional outcomes
- Trade and import dependency

The model helps balance priorities such as food security, biodiversity protection, emissions reduction, and sustainable land use — providing a foundation for long-term agricultural planning and policy development.

## Output Domains

The FABLE workbook exports outputs across nine domains:

| Domain | What it tracks |
|---|---|
| GHG | Greenhouse gas emissions from agriculture and land use |
| PRODUCTION | Crop and livestock production volumes |
| TRADE | Import/export balances for key commodities |
| JOBS | Agricultural employment |
| FOOD | Food availability and dietary outcomes |
| LAND | Land-use change and agricultural area |
| WATER | Water use and irrigation demand |
| N and P | Nitrogen and phosphorus flows |
| BIODIVERSITY | Habitat pressure and biodiversity indicators |

## What This Repository Does

This repository is the post-processing and visualization layer for any FABLE country workbook. It automates the workbook-based workflow:

1. **Run all pathways** — iterates every named scenario in your workbook, triggers Excel recalculation, and exports all output tables and chart series as CSVs.
2. **Compare pathways** — computes deviation of each scenario from a chosen baseline (e.g. `CurrentTrends`) across all output domains and years.
3. **Visualize results** — interactive Streamlit dashboard with curated charts, combined table explorer, pathway comparison plots, and deviation analysis.
4. **GUI launcher** — Tkinter desktop application for non-technical users.

## Pathways

Each pathway represents a distinct scenario for a country's food and land systems — for example, `CurrentTrends` (baseline), `HealthyDiet`, or `AgroEcology`. The model is fully recalculated in Excel for each pathway before export, ensuring consistent outputs across all scenarios.

The runner discovers pathway names automatically from your workbook — no hardcoding required.

## Adapting for Your Country

The tool is designed to work with any FABLE country workbook:

1. Place your country's `.xlsx` workbook in `workbooks/` and update `config.yaml` with the path.
2. The runner discovers pathways and output tables automatically — no code changes needed for the runner, comparison, or dashboard tabs (Combined Tables, Pathway Comparison, Deviation Analysis).
3. The **Curated Charts** tab contains charts with column names specific to the workbook it was built with. For other countries, use the generic dashboard tabs, which work with any FABLE output structure.
