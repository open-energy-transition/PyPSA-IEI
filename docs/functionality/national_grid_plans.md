# National Grid Expansion Plans

## Overview

National electricity transmission expansion is constrained based on country-specific
grid expansion plans (e.g., from Ember study). The feature limits national
AC line and DC link expansion to specified factors relative to base year
capacities.

This applies only to **national** (intra-country) transmission infrastructure.
Cross-border TYNDP projects are handled separately via the
[TYNDP Electricity Projects](electricity.md) functionality.

---

## Snakemake Rule

**Rule:** `solve_elec_networks` / `solve_sector_networks`  
**Script:** `scripts/solve_network.py` — function `add_national_grid_plan_constraints()`

**Input data:**

- `data/national_line_expansions.csv` — Expansion factors per country and year

---

## Scenario Behaviour

The constraint is disabled by default and enabled per scenario via
`solving.constraints.national_grid_plans: true`. The `optimize_after`
parameter controls from which planning horizon national grids become
freely extendable (no longer bound by the CSV expansion factors).

| Scenario | Constraint active | `optimize_after` | Effect |
|---|---|---|---|
| CE | No | — | No national expansion limit applied |
| CN | No | — | No national expansion limit applied |
| SE | Yes | `2040` | Expansion capped by CSV factors; freely extendable from 2040 |
| SN | Yes | `2040` | Expansion capped by CSV factors; freely extendable from 2040 |

When no expansion factor is specified for a country/year:

| Case | Behavior |
|---|---|
| Year before data is available | National transmission fixed (except TYNDP projects) |
| First planning horizon (2020) | All national transmission freely extendable |
| No matching CSV data (not before data range, not first horizon) | Controlled by `optimize_after` setting |

---

## CSV Data Format

### `data/national_line_expansions.csv`

Columns: Country ISO2 code as row index, year columns (e.g., `2025`, `2030`, ...):

```csv
,2025,2030,2035,2040,2045,2050
DE,1.2,1.5,1.8,2.0,2.2,2.5
FR,1.1,1.3,1.5,1.7,1.9,2.1
PL,1.0,1.2,1.4,1.6,1.8,2.0
```

Each cell contains the **expansion factor** (float) relative to base year capacity:

| Value | Meaning |
|---|---|
| `1.0` | No expansion allowed beyond base year |
| `1.5` | 50% expansion allowed (factor × base capacity) |
| `2.0` | Doubling of capacity allowed |
| Empty/NaN | Fallback behavior applies |

---

## Configuration

Default values in `config/config.agora.yaml` — the constraint is off by default:

```yaml title="config/config.agora.yaml"
policy_plans:
  include_national_grid_plans:
    national_grid_plan_data: data/national_line_expansions.csv
    national_expansion_condition: equal  # 'min', 'max', or 'equal'
    optimize_after: true  # true = freely extendable at all horizons (no cap once constraint is off)

solving:
  constraints:
    national_grid_plans: false  # disabled by default; enable per scenario
```

Overrides in SE and SN scenarios — these are the only two scenarios with the
constraint active:

```yaml title="config/scenarios/config.SE.yaml  |  config/scenarios/config.SN.yaml"
policy_plans:
  include_national_grid_plans:
    optimize_after: 2040  # expansion capped by CSV factors until 2040, freely extendable from 2040

solving:
  constraints:
    national_grid_plans: true
```

| Parameter | Options | Description |
|---|---|---|
| `national_grid_plan_data` | File path | CSV with expansion factors per country/year |
| `national_expansion_condition` | `min`, `max`, `equal` | Constraint type: ≥, ≤, or = |
| `optimize_after` | `true` or integer | When national grids become freely extendable |
| `national_grid_plans` (in solving) | Boolean | Enable/disable constraint per scenario |

**Constraint type behavior:**

- **`equal`** (default): National capacity must equal factor × base capacity
- **`min`**: National capacity at least factor × base capacity (allows more)
- **`max`**: National capacity at most factor × base capacity (caps expansion)

---

## How to Modify

### Change expansion factors per country/year

Edit `data/national_line_expansions.csv` with country-specific factors.

### Adjust constraint type

Set `national_expansion_condition` to `min`, `max`, or `equal` in config.

### Control when national grids become freely extendable

Set `optimize_after` to `true` (always) or integer year (e.g., `2040`).

### Enable/disable per scenario

Set `solving.constraints.national_grid_plans: true` in scenario config.

---

!!! note "Interaction with TYNDP"
    National grid plans apply **after** TYNDP electricity constraints.
    Lines/links already fixed by TYNDP (where `p_nom_min = p_nom_max` or
    `s_nom_min = s_nom_max`) are excluded from national grid constraints,
    ensuring TYNDP commitments take precedence.

!!! info "Data Source"
    Default factors based on [Ember transmission grids study](https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fember-climate.org%2Fapp%2Fuploads%2F2024%2F03%2FEmber-Transmission-Grids-Data.xlsx&wdOrigin=BROWSELINK).
