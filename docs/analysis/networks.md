# Network Maps

## Overview

Four scripts produce per-year and per-scenario maps of European transmission
infrastructure. A fifth script compares two scenarios side by side.

**Output:** `network_plots/`

---

## Scripts

| Script | Function | Network |
|---|---|---|
| `plot_elec_network.py` | `plot_map_elec_years()` | Electricity (AC lines + DC links) |
| `plot_h2_network.py` | `plot_h2_map_years()` | Hydrogen pipelines and storage |
| `plot_co2_network.py` | `plot_co2_map_years()` | CO₂ pipelines |
| `plot_ch4_network.py` | `plot_ch4_map_years()` | Methane / gas pipelines |
| `compare_grids.py` | `plot_grid_comparisons()` | Scenario difference maps |

---

## Output Files

### Electricity

| File | Description |
|---|---|
| `elec_netexpansion_{scenario}_{year}.png` | Post-network + pre-network overlay |
| `pre_elec_netexpansion_{scenario}_{year}.png` | Net expansion (post − pre) |

### Hydrogen

| File | Description |
|---|---|
| `h2_electrolysis_network_{scenario}_{year}.png` | Electrolysis capacity map |
| `h2_all_network_{scenario}_{year}.png` | Full H₂ network |
| `h2_net_flows_network_{scenario}_{year}.png` | Net H₂ flows |
| `h2_storage_{scenario}_{year}.png` | H₂ storage capacity |

### CO₂ and Gas

| File | Description |
|---|---|
| `co2_network_{scenario}_{year}.png` | CO₂ pipeline network |
| `ch4_network_{scenario}_{year}.png` | Methane / gas pipeline network |

### Grid Comparisons

`plot_grid_comparisons()` runs for each scenario paired against `sel_scen`,
producing electricity and H₂ difference maps per year:

| File | Description |
|---|---|
| `diff_elec_{scen1}_{scen2}_{year}.png` | Electricity grid difference |
| `diff_H2_{scen1}_{scen2}_{year}.png` | H₂ grid difference |

---

## Geographic Scope

All network maps use `country_to_plot_networks`, set to `"EU27"` in
`analysis_main.py`.
