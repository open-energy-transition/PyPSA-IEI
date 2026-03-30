# Model Functionality Overview

This section describes the key extensions and modifications made to the
[PyPSA-Eur v0.10.0](https://github.com/PyPSA/pypsa-eur/tree/v0.10.0) base model for the PyPSA-IEI study.
Each sub-page covers one topic with a description, the relevant Snakemake rule(s), and code/config snippets for reproducibility and future modification.

---

## Contents

| Topic | Description |
|---|---|
| [Costs](costs.md) | Custom cost assumptions from config and technology-data |
| [Lifetimes](lifetimes.md) | Country- and plant-level powerplant lifetime adjustments |
| [Gas](gas.md) | TYNDP gas pipelines, Russian import removal |
| [Hydrogen](hydrogen.md) | Wasserstoffkernnetz, ENTSO-G network, retrofitting |
| [Industrial Demand](industry.md) | TransHyDe-based industrial energy demand |
| [Imports](imports.md) | H₂, syngas, and synfuel import nodes |
| [Losses](losses.md) | Transmission efficiency and compression losses |
| [TYNDP Electricity Projects](electricity.md) | Cross-border TYNDP transmission enforcement |
| [National Grid Plans](national_grid_plans.md) | National transmission expansion factors per country |
| [Myopic Optimization](myopic.md) | Brownfield capacity accounting across horizons |
| [Expansion Limits](expansion.md) | Min/max capacity constraints per carrier and country |
| [Self-Sufficiency Constraints](self_sufficiency.md) | Minimum/maximum self-sufficiency targets per region |
| [Overall Minimum Capacities](overall_min_capacities.md) | System-wide minimum capacity per carrier |
| [Capacity Reserve Margin](capacity_reserve.md) | Reserve margin above peak demand for conventional generation |
| [Import Infrastructure Retrofitting](import_retrofit.md) | Gas import infrastructure reuse for H₂ and syngas |
| [Curtailment Mode](curtailment_load_shedding.md) | Explicit renewable curtailment modeling |
