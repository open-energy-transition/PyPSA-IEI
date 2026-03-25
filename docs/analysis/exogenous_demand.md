# Exogenous Demand

## Overview

Analysis of exogenous transport energy demand across planning years for a
selected scenario. Transport demand is broken down by mode (aviation,
shipping, land transport) and energy carrier (kerosene, oil, methanol, EV,
fuel cell).

Results show total annual energy consumption (TWh) for each transport
category, helping track the transition from fossil fuels to electrification
and alternative fuels.

**Script:** `scripts_analysis/exogenous_demand_analyses.py`  
**Function:** `get_transport_demand_plot()`  
**Output:** `ExogenousDemand/`  

---

## Transport Categories

| Mode | Carrier | Description |
|---|---|---|
| Aviation | Kerosene | Kerosene and sustainable aviation fuel (SAF) |
| Shipping | Oil | Conventional marine fuel oil |
| Shipping | Methanol | Methanol-based marine fuel |
| Land transport | Oil | Conventional fossil fuel vehicles |
| Land transport | EV | Battery electric vehicles |
| Land transport | Fuel cell | Hydrogen fuel cell vehicles |

---

## Output Files

| File | Description |
|---|---|
| `Transport_demand_exogenous.png` | Stacked bar chart showing transport demand by mode and carrier across years |
| `Transport_demand_exogenous.xlsx` | Excel data with annual energy demand (TWh) per transport category |
