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

!!! info "PyPSA capacity parameters"
    PyPSA uses different capacity attributes depending on component type:

    - **`p_nom`** — nominal power capacity of a **Link** (DC line, converter, etc.) in MW. `p_nom_opt` is the value chosen by the optimizer; `p_nom_min` / `p_nom_max` are the bounds.
    - **`s_nom`** — nominal apparent power capacity of a **Line** (AC transmission) in MVA. `s_nom_opt` is the optimized value; `s_nom_min` / `s_nom_max` are the bounds.
    - **`s_max_pu`** — per-unit loading limit on a Line (typically 0.7), so effective capacity = `s_nom × s_max_pu`.
    - **`p_nom_extendable`** / **`s_nom_extendable`** — if `True`, the optimizer decides the capacity.

**Base year capacities:** The reference capacities that factors are applied to are derived from the
optimized network of the **first planning horizon** (e.g. 2020). They are computed by
`extract_base_year_capacities()` in `scripts/add_brownfield.py` when preparing the second planning
horizon, summing national AC line (`s_nom_opt × s_max_pu`) and DC link (`p_nom_opt`) capacities per
country, and saved to `results/.../base_year_capacities/`. The constraint then enforces
`factor × base_capacity`.

**Factor selection per country:** For each country, the code searches the CSV for data years that fall
in the window `(previous_horizon, current_horizon]`. The most recent year within that window is used as the
expansion factor. Countries with no data in that window are excluded from the constraint.

**Fallback when no country has data in the window** (e.g. all countries lack CSV entries for this period):

| Case | Condition | Behavior |
|---|---|---|
| 1A — Before data range | Current year < first CSV year, and not the first planning horizon | National transmission **fixed** at current capacity (except TYNDP-committed projects) |
| 1B — First planning horizon | Current year is the first in `planning_horizons` | All national transmission **freely extendable** |
| 1C — Beyond data range | Current year > last CSV year (and not first horizon) | Controlled by `optimize_after` setting |

---

## CSV Data Format

### `data/national_line_expansions.csv`

Columns: Country ISO2 code as row index, year columns (e.g., `2026`, `2030`, ...):

```csv
country,2026,2030
DK,1.44,
EE,1.17,1.24
GR,1.16,1.35
DE,1.09,1.2
FR,1.01,1.02
PL,1.12,1.24
LV,1.0,1.0
```

Each cell contains the **expansion factor** (float) relative to base year capacity:

| Value | Meaning |
|---|---|
| `1.0` | No expansion allowed beyond base year (e.g. LV) |
| `1.09` | 9% expansion allowed (e.g. DE in 2026) |
| `1.44` | 44% expansion allowed (e.g. DK in 2026) |
| Empty/NaN | Fallback behavior applies (e.g. DK in 2030) |

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
