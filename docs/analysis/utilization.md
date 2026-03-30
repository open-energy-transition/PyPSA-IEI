# Gas Pipeline Utilization

## Overview

Gas pipeline utilization analysis showing how heavily CH₄ pipelines are
used relative to their nominal capacity. Utilization rates are calculated as
mean power flow divided by capacity across all timesteps, weighted by
snapshot duration.

Maps visualize both capacity (linewidth) and utilization (color scale) for
each corridor across planning years and scenarios.

**Script:** `scripts_analysis/line_usage.py`  
**Function:** `evaluate_line_usage()`  
**Output:** `utilization/`  

---

## Output Files

For each scenario and year combination:

| File | Description |
|---|---|
| `ch4_utilization_map_{scenario}_{year}.png` | Map showing gas pipeline capacity (linewidth) and average utilization percentage (color) |

---

## Visualization Details

**Pipeline Capacity (Linewidth)**
- Linewidth scaled by optimal pipeline capacity (`p_nom_opt`)
- Pipelines below 100 MW threshold are not displayed
- Bidirectional flows are aggregated

**Utilization Rate (Color)**
- Color scale from red (low utilization) to green (high utilization)
- Calculated as: mean absolute power flow / (capacity × availability)
- Averaged across the full year weighted by snapshot duration
