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
| [CO₂ Pipeline Network](co2_pipeline.md) | Spatial CO₂ tracking, bidirectional pipeline links, sequestration caps |
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

---

## Where to Make Changes

The table below shows at a glance where each type of assumption is adjusted.

| Parameter | Change location |
|---|---|
| Investment costs | `config/config.agora.yaml` or scenario override under `costs.investment` |
| Transmission efficiency / losses | `config/config.agora.yaml` under `sector.transmission_efficiency` |
| Powerplant lifetimes | `data/powerplant_lifetime.csv` (data file) |
| Self-sufficiency targets | `data/self_sufficiency_limits.csv` (data file); enable per scenario via `solving.constraints.self_sufficiency` |
| Expansion limits (renewables, H₂, gas) | `data/agg_p_nom_minmax_european.csv` or `_national.csv` (data file); active file set via `policy_plans.agg_p_nom_limits` |
| National grid expansion factors | `data/national_line_expansions.csv` (data file); enable per scenario via `solving.constraints.national_grid_plans` |

!!! note "Finding the right technology name for cost overrides"
    Technology names must exactly match the `technology` column in
    `data/costs_<planning_horizon>.csv` (e.g. `data/costs_2030.csv`), derived from
    [technology-data v0.9.0](https://github.com/PyPSA/technology-data/blob/v0.9.0/outputs/).
    Browse it to find the exact string to use as a key under `costs.investment.<year>` in the config.
