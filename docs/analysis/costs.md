# System Costs

## Overview

Total system cost breakdown per scenario and planning year, covering capital
and operational expenditure by technology group. Costs are shown both as
annual values and as integrated cumulative costs from the start year to each
planning horizon.

**Script:** `scripts_analysis/analyze_total_system_cost.py`
**Function:** `analyze_system_cost()`
**Output:** `costs/`

---

## Output Files

| File | Description |
|---|---|
| `infrastructure_capital_cost.png` | Capital costs of transmission infrastructure (electricity, H₂, gas, CO₂) |
| `absolute_capital_cost.png` | Absolute capital costs by technology group across all scenarios |
| `residual_capital_cost_{sel_scen}_{scenario}.png` | Difference in capital costs vs `sel_scen`, one file per comparison scenario |
| `operational_costs.png` | Operational (marginal) costs by category across all scenarios and years |
| `residual_operational_costs_{sel_scen}_{scenario}.png` | Difference in operational costs vs `sel_scen`, one file per comparison scenario |
| `total_costs.png` | Total annualised costs (capex + opex) per scenario and year |
| `total_overinvestment.png` | System cost difference vs `sel_scen` (bn EUR/yr) |
| `integrated_total_costs.png` | Cumulative total costs from start year per scenario |
| `integrated_difference_costs.png` | Cumulative cost difference vs `sel_scen` (bn EUR) |
| `total_costs.xlsx` | Excel with annualised and integrated costs by category |

!!! note "`sel_scen`"
    `sel_scen` is the primary scenario selected in `analysis_main.py`. It is used as the reference baseline for all residual and difference plots. Files containing `{sel_scen}` and `{scenario}` in their name are generated once per comparison scenario.

The Excel file is also automatically written into
`KPIs/Summary-Results-KPIs.xlsx` if that file already exists.

---

## Technology Mapping

Cost components are mapped to groups via:
```
scripts_analysis/Mapping_system_costs.csv
```

The groups used in plots are:

| Group | Includes |
|---|---|
| `infrastructure` | AC/DC lines, H₂/gas/CO₂ pipelines |
| `power generation` | Solar, wind, nuclear, hydro, etc. |
| `heat generation` | Heat pumps, boilers, CHPs |
| `transformation` | Electrolysers, methanisation, Fischer-Tropsch, etc. |
| `import (capex)` | Import infrastructure capital costs |
| `import (opex)` | Import fuel operational costs |
| `operational costs` | Fuel costs, VOM |
| `others (capex/opex)` | Remaining components |

---

## Backup Capacities

`backup_capas` is hardcoded in `analysis_main.py` (currently `True`). When `True` and the backup cost file exists, gas turbine backup capacity costs are added to `total_overinvestment.png` and `integrated_difference_costs.png`. If the file is missing, the flag is automatically set to `False` by the script.

The costs are read from:

```
{analysis_results_dir}/Balances/gas_turbine_backup_costs.xlsx
```

where `{analysis_results_dir}` is the dated output folder (e.g., `analysis_results_20260311/`).

!!! note
    This file is produced by `get_standard_balances()` for the `gas` carrier.
    The Energy Balances analysis must run before System Costs when `backup_capas=True`.
