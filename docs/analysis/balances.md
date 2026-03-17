# Energy Balances

## Overview

Supply and demand balance charts are produced for 6 carriers across three
regions (all countries, EU27, and one configurable country) per scenario and
year. Results are saved as PNG bar charts, interactive HTML timeseries, and
Excel files.

**Script:** `scripts_analysis/configurable_energy_balances.py`
**Function:** `get_standard_balances()`
**Output:** `Balances/`

---

## Carriers

| Carrier | Description |
|---|---|
| `electricity` | High-voltage electricity |
| `gas` | Natural gas / methane |
| `low voltage` | Residential electricity distribution |
| `H2` | Hydrogen |
| `heat` | Decentral heat |
| `urban central heat` | District heating |

---

## Output Files

For each carrier, the following are produced under `Balances/`:

| File / Folder | Description |
|---|---|
| `balance_{carrier}.xlsx` | Excel with supply/demand data per country and scenario |
| `gas_turbine_backup_capacities.xlsx` | Gas turbine backup capacity data (electricity carrier only) |
| `gas_turbine_backup_costs.xlsx` | Gas turbine backup cost data (electricity carrier only) |
| `bar_plots/` | PNG bar charts per region and scenario mode |
| `timeseries_plots_line_chart/` | Interactive HTML line charts (selectable scenario/year) |
| `timeseries_plots_stacked_bar_chart/` | Interactive HTML stacked bar chart + PNG per scenario/year |

Bar plots are generated for three regions: **All** (33 countries), **EU27**, and the configured country (default `DE`).

---

## Configuration

### Country

`country_to_plot` is set in `analysis_main.py` (currently `"DE"`). Any ISO2 country code in the model scope can be used.

### Scenario comparison mode

`compare_scenarios` controls whether all scenarios are overlaid in one plot (`True`) or plotted individually (`False`). In `analysis_main.py` it is set to `[True, False]` for all carriers, producing both plot styles. `urban central heat` only uses `[True]` because it is not meaningful to plot it per individual scenario.
