# Balance Maps

## Overview

Spatial maps of energy balances overlaid on the European grid, produced for
each carrier, scenario, and year. A second set of difference maps compares
the selected reference scenario against all other scenarios.

**Script:** `scripts_analysis/plot_balance_map.py`
**Function:** `plot_balance_map_years()`
**Output:** `balance_maps/`

---

## Carriers

Carriers are defined in `config/config.plotting.yaml` under
`constants.kinds`:

| Carrier | Description |
|---|---|
| `carbon` | Carbon flows (CO₂ capture, stored and sequestered) |
| `co2` | CO₂ emissions |
| `electricity` | Transmission level electricity (AC and DC)|
| `gas` | Natural gas / methane |
| `hydrogen` | Hydrogen |

---

## Output Files

For each carrier, scenario, and year one PNG is saved to `balance_maps/`:

| File | Description |
|---|---|
| `{carrier}_{region}_balance_map_{scenario}_{year}.png` | Single-scenario balance map |
| `{carrier}_{region}_balance_map_{scen1} vs {scen2}_{year}.png` | What is additional in `scen1` relative to `scen2` |
| `{carrier}_{region}_balance_map_{scen2} vs {scen1}_{year}.png` | What is additional in `scen2` relative to `scen1` |

---

## Configuration

### Region

`country_to_plot_networks` in `analysis_main.py` controls which region is
plotted. It is set to `"EU27"` by default. Three regions have dedicated
plot configurations in `config.plotting.yaml`:

| Value | Description |
|---|---|
| `"EU27"` | EU-27 + neighbouring countries (default) |
| `"PL_and_Baltics"` | Poland and the Baltic states (not plotted) |
| `"Benelux"` | Belgium, Netherlands, Luxembourg (not plotted)|

Any other value falls back to the `"EU27"` configuration.

### Reference scenario

`sel_scen` is the reference scenario used for the difference maps. Each
other scenario in `scenarios` is compared against it.

!!! note
    `sel_scen` is set in `analysis_main.py` and shared with other analysis
    functions (system costs, self-sufficiency).
