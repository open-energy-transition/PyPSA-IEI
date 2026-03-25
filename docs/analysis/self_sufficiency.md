# Self-Sufficiency

## Overview

Regional energy self-sufficiency levels per country and planning year,
showing the ratio of domestic generation to total demand. Analysis is
performed for both hydrogen and electricity carriers across all EU27
countries plus surrounding regions.

The analysis is run pairwise: `sel_scen` is compared against each other
scenario to produce difference maps.

**Script:** `scripts_analysis/regional_self_sufficiency_level.py`  
**Function:** `evaluate_self_sufficiency()`  
**Output:** `self-sufficiency/`  

---

## Carriers

Self-sufficiency is calculated independently for two carriers:

| Carrier | Description |
|---|---|
| `H2` | Hydrogen self-sufficiency based on domestic generation vs demand |
| `Electricity` | Electricity self-sufficiency based on renewable generation vs demand |

For each carrier, self-sufficiency accounts for:
- Domestic generation (electrolysis for H₂, renewables for electricity)
- Cross-border transmission (pipelines for H₂, AC/DC lines for electricity)
- External imports (from outside Europe)

---

## Output Files

For each scenario, year, and carrier, the following files are generated:

| File | Description |
|---|---|
| `{carrier}_self-sufficiency_map_{scenario}_{year}.png` | Map showing self-sufficiency percentage per country |
| `{carrier}_self-sufficiency_{scenario}_{year}.png` | Bar chart comparing self-sufficiency across countries, with EU27 aggregate |
| `{carrier}_self-sufficiency_diff_{scenario1}_{scenario2}_{year}.png` | Difference map comparing two scenarios |

Where `{carrier}` is either `h2` or `elec`.

!!! note "`sel_scen`"
    `sel_scen` is the primary scenario selected in `analysis_main.py`. Difference maps are produced comparing `sel_scen` against each other scenario.

---

## Regions

Self-sufficiency is calculated for:

- All 25 EU27 countries (excl. Malta and Cyprus)
- EU27 aggregate
- Surrounding countries (Balkans, UK, Norway, Switzerland)

The bar charts include an exogenous minimum self-sufficiency constraint line for scenarios `CN` and `SN` (years after 2025).
