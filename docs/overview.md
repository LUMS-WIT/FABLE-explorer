# Overview — FABLE Pakistan

## About FABLE Pakistan

FABLE Pakistan is part of the global Food, Agriculture, Biodiversity, Land-Use, and Energy (FABLE) Consortium — a collaborative network of research teams across more than 20 countries working to design sustainable pathways for food and land systems. The initiative is coordinated by the Food and Land Use Coalition (FOLU) and the International Institute for Applied Systems Analysis (IIASA). More information at [fableconsortium.org](https://fableconsortium.org).

The Pakistan team is led by the Water, Informatics and Technology (WIT) program at the Lahore University of Management Sciences (LUMS), in collaboration with the FABLE Secretariat at IIASA.

## What the FABLE Model Does

The FABLE model is an open-source accounting and scenario analysis tool built in Excel and Python. It quantifies how Pakistan's food, agriculture, land, and energy systems evolve under different policy and climate futures by tracking:

- Food production and demand
- Crop and livestock yields
- Land-use change
- Greenhouse gas emissions
- Biodiversity indicators
- Nutritional outcomes
- Trade and import dependency

The model helps balance priorities such as food security, biodiversity protection, emissions reduction, and sustainable land use — providing a foundation for long-term agricultural planning and policy development.

## Output Domains

Pakistan's FABLE model exports outputs across nine domains:

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

## Current Status

The team is localizing the FABLE Calculator for Pakistan by integrating national data from the Pakistan Bureau of Statistics, the Ministry of National Food Security and Research, SUPARCO, and other key institutions. Datasets are aligned with global standards including FAO and World Bank indicators.

Scenarios are being developed consistent with Pakistan's NDCs, National Adaptation Plan, and Agriculture Policy Framework — spanning reference, sustainable, and high-ambition futures.

The first open-access release of FABLE Pakistan is planned for **March 2026**, including a national report, database, and interactive online dashboard.

## What This Repository Does

This repository is the post-processing and visualization layer for the FABLE Pakistan workbook. It automates the workbook-based workflow:

1. **Run all pathways** — iterates every named scenario, triggers Excel recalculation, and exports all output tables and chart series as CSVs.
2. **Compare pathways** — computes deviation of each scenario from a chosen baseline (`CurrentTrends`) across all output domains and years.
3. **Visualize results** — interactive Streamlit dashboard with curated charts, combined table explorer, and deviation analysis.
4. **GUI launcher** — Tkinter desktop application for non-technical users.

## Pathways

Each pathway represents a distinct scenario for Pakistan's food and land systems — for example, `CurrentTrends` (baseline), `HealthyDiet`, or `AgroEcology`. The model is fully recalculated in Excel for each pathway before export, ensuring consistent outputs.
