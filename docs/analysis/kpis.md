# KPIs

## Overview

Five functions produce key performance indicators covering installed
capacity, infrastructure volume, dispatch, and summary system metrics.

---

## Installed Capacity

**Script:** `installed_capacity.py`  
**Function:** `call_installed_capacity_plot()`  
**Output:** `KPIs/`  

Installed capacity by technology, planning year, and scenario. Controlled
by `plot_backup_capas` (boolean) in `analysis_main.py` to optionally
include backup capacity.

Output files are produced for two scopes (`EU27` and `All`) and three
capacity types (`generation`, `heat`, `storage`):

| File | Description |
|---|---|
| `installed_{type}_capacities_{scope}.png` | All-scenario comparison chart |
| `installed_{type}_capacities_{scope}_{scenario}.png` | Per-scenario chart across years |

---

## Infrastructure Volume (TW·km)

**Script:** `plot_GWkm.py`
**Function:** `plot_TWkm_all_carriers()`
**Output:** `KPIs/`

Installed capacity × line length (TW·km) per carrier (electricity, H₂,
CO₂, gas) across years and scenarios. Plots are produced for four regions:
all modelled countries, EU27, Benelux, and the Baltic cluster.

| File | Description |
|---|---|
| `TWkm_elec_{region}.png` | Electricity TW·km |
| `TWkm_H2_{region}.png` | Hydrogen TW·km |
| `TWkm_CO2_{region}.png` | CO₂ TW·km |
| `TWkm_gas_{region}.png` | Gas TW·km |

Regions: `europe`, `eu27`, `benelux`, `balticum`.

---

## Summary KPIs

**Script:** `summary_KPIs.py`
**Function:** `start_KPI_analysis()`
**Output:** `KPIs/`

Comprehensive Excel workbook covering total costs, emissions, and system
metrics per country, EU27, and selected nodes, across all scenarios and
years.

| File | Description |
|---|---|
| `Summary-Results-KPIs.xlsx` | Full KPI workbook |

---

## Case Study KPIs

**Script:** `plot_cases_KPIs.py`
**Function:** `plot_case_study_KPIs()`
**Output:** `KPIs/`

Bar charts (with cluster map insets) comparing offshore capacity, H₂
storage, CO₂ storage, and H₂ import across scenarios and years for two
predefined regional clusters: `northsea` and `balticum`.

| File | Description |
|---|---|
| `offshore_capacity_{cluster}.png` | Offshore installed capacity |
| `H2_storage_{cluster}.png` | H₂ storage capacity |
| `CO2_storage_{cluster}.png` | CO₂ storage capacity |
| `H2_import_{cluster}.png` | H₂ import (North Sea cluster only) |

---

## Dispatch Barchart

**Script:** `plot_dispatch_barchart.py` — `plot_dispatch_barchart()`

Stacked bar chart of flexibility dispatch (storage, demand response, etc.)
across scenarios and years. The `"flexibility"` argument selects the KPI
type computed inside the script.

| File | Description |
|---|---|
| `flexibility_dispatch.png` | Flexibility dispatch comparison |
