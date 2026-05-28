<!--
SPDX-FileCopyrightText: Open Energy Transition GmbH and contributors
SPDX-License-Identifier: MIT
-->

# Grid Emission Factors

## Overview

Hourly average grid emission factors [tCO₂/MWh_el] are computed per AC bus
node for all scenarios and planning years. The factor at each node reflects
the generation-weighted average CO₂ intensity of local electricity production
at each time step.

**Script:** `scripts_analysis/grid_emission_factors.py`  
**Function:** `analyze_grid_emission_factors()`  
**Output:** `grid_emission_factors/`

---

## Output Files

| File | Description |
|---|---|
| `grid_emission_factors.xlsx` | Hourly emission factors per AC node, one sheet per bus |

Each sheet corresponds to one AC bus node, sorted alphabetically. Rows are
hourly time steps and columns form a `MultiIndex(scenario, year)`. Values are
in tCO₂/MWh_el. Hours with no local generation yield `NaN`.

---

## Emission Factor Definition

The emission factor at node $b$ at time $t$ is the generation-weighted
average CO₂ intensity across all local generators:

$$
EF_b(t) = \frac{\sum_g p_g(t) \cdot \alpha_g}{\sum_g p_g(t)}
$$

where $p_g(t)$ is the dispatch [MW] and $\alpha_g$ is the CO₂ emission
intensity [tCO₂/MWh_el] of generator $g$'s carrier. Hours with zero total
local generation yield `NaN`.

---

## How It Works

`analyze_grid_emission_factors()` calls two internal functions:

### `extract_grid_emission_factors()`

Three component types contribute to both the electricity and CO₂ numerator:

| Component | Electricity | CO₂ |
|---|---|---|
| **Generators** | `n.generators_t.p` | `n.carriers.co2_emissions` × dispatch |
| **Links** (local generation only) | AC output port | CO₂-atmosphere port |
| **StorageUnits** | `n.storage_units_t.p` clipped to ≥ 0 | 0 (no direct emissions) |

**Link filtering:** Links whose `bus0` is an AC bus (e.g. HVDC, back-to-back
converters) are excluded — these are transmission, not local generation.
Only links with an AC output port that do not start from an AC bus are
included.

**CO₂ port detection:** The script identifies the single port per link that
connects to a `co2` atmosphere bus. CCS plants' "CO₂ stored" ports have a
different carrier and are therefore never matched.

Values near zero (< 1×10⁻⁴) are set to zero to suppress numerical noise.

### `write_grid_emission_factors()`

Writes one sheet per AC bus to a single Excel file, sorted alphabetically
by bus name:

```python
for bus, df in sorted(emission_factors.items()):
    df.to_excel(writer, sheet_name=str(bus))
```

---

## Configuration

`analyze_grid_emission_factors()` is called from `analysis_main.py`:

```python
analyze_grid_emission_factors(
    networks_year=networks,
    years=years,
    scenarios=scenarios,
    resultdir=emission_factors_dir,
)
```
