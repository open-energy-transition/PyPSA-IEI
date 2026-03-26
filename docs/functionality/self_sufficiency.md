# Self-Sufficiency Constraints

## Overview

Minimum and maximum self-sufficiency constraints can be enforced for energy
carriers at the country, regional cluster, or EU-wide level. The
constraint ensures that a specified fraction of total demand is met by
domestic generation rather than imports.

**Self-sufficiency** is the ratio of local generation to total demand  
(local generation + net imports). For example, 70% self-sufficiency means
that 70% of demand is met by domestic sources and 30% by imports.

The constraint is enforced on **annual energy** (MWh), not capacity.
It applies to each planning year independently and accounts for:

- Domestic generation from all relevant technologies  
- Cross-border electricity transmission (AC lines and DC links)  
- Pipeline flows (hydrogen, synfuel)  
- External imports from non-European regions  

---

## Snakemake Rule

**Script:** `scripts/solve_network.py` — function
`add_self_sufficiency_constraints`, called from `extra_functionality`  
**Rule:** `solve_sector_network_myopic`  
**Data file:** `data/self_sufficiency_limits.csv` (configured via `policy_plans.self_sufficiency_limits`)

---

## Scenario Behavior

| Scenario | Enabled | Use case |
|---|---|---|
| CE, SE | No | Cross-border planning without self-sufficiency targets |
| CN, SN | Yes | National self-sufficiency targets enforced |

Enable via scenario config:

```yaml
solving:
  constraints:
    self_sufficiency: true
```

---

## Supported Carriers

The constraint independently tracks self-sufficiency for three energy carriers:

| Carrier | ID in CSV | Generation technologies | Import pathways |
|---|---|---|---|
| **Hydrogen** | `H2` | H₂ Electrolysis, SMR, SMR CC | H₂ pipelines, external imports |
| **Electricity** | `AC` | Solar, onwind, offwind, hydro, nuclear, fossil CHP, H₂ fuel cells | AC lines, DC links |
| **Synfuel** | `synfuel` | Fischer-Tropsch, biomass to liquid | (compared to oil demand) |

For **electricity**, generation from the following carriers is counted:
- `offwind-ac`, `offwind-dc`, `onwind`, `solar`, `solar rooftop`, `ror` (run-of-river)
- `hydro` (storage units)
- Conventional plants: `coal`, `lignite`, `OCGT`, `CCGT`, `nuclear`, `oil`, `allam`
- CHPs: gas and biomass variants (residential, services, urban central)
- H₂ conversion: `H2 Fuel Cell`, `H2 turbine`

For **hydrogen**, generation includes:
- `H2 Electrolysis` (electrolyzers)
- `SMR`, `SMR CC` (steam methane reforming with/without carbon capture)

For **synfuel**, the constraint compares:
- Synfuel generation: `Fischer-Tropsch`, `biomass to liquid`
- Oil demand: land transport oil, shipping oil, aviation kerosene, residential/services oil boilers, industrial naphtha, agriculture machinery oil

---

## Constraint Levels

The function applies constraints at **two levels** independently:

1. **Per-country** (ISO2 codes: `FR`, `DE`, `IT`, etc.)  
   Cross-border flows between countries count as imports/exports.

2. **Per-cluster** (5-character cluster IDs: `DE123`, `FR045`, etc.)  
   Flows between clusters count as imports/exports, even within the same country.

Additionally, if multiple EU countries are specified, the constraint creates an **EU-wide aggregate** by summing generation and trade for all EU27 countries as a single entity.

---

## Minimum and Maximum Constraints

Both lower and upper bounds can be specified:

- **Minimum self-sufficiency** (`min` column): Enforces at least X% domestic generation  
  Local generation must be greater than or equal to (Total demand × min value).

- **Maximum self-sufficiency** (`max` column): Prevents over-generation (exports above threshold)  
  Local generation must be less than or equal to (Total demand × max value).

Leave `min` or `max` blank (or empty rows) for no constraint in that direction.

---

## CSV Format

**File:** `data/self_sufficiency_limits.csv`

| Column | Description |
|---|---|
| `country` | ISO2 country code (e.g. `DE`, `FR`), cluster ID (e.g. `DE123`), or `EU` for EU-wide |
| `carrier` | Carrier: `H2`, `AC`, or `synfuel` |
| `year` | Planning year (integer) |
| `min` | Minimum self-sufficiency fraction [0–1] — blank = no minimum |
| `max` | Maximum self-sufficiency fraction [0–1 or >1 for net exporters] — blank = no maximum |

Example rows:

```csv
country,carrier,year,min,max
DE,H2,2030,0.7,
FR,AC,2040,,1.2
EU,H2,2050,0.5,
PL123,AC,2030,0.8,
```

In this example:
- Germany must produce ≥70% of H₂ demand in 2030  
- France may produce up to 120% of electricity demand in 2040 (20% net exports allowed)  
- EU-wide H₂ self-sufficiency must be ≥50% in 2050  
- Cluster `PL123` must produce ≥80% of electricity demand in 2030  

---

## Config

Base config location:

```yaml
policy_plans:
  self_sufficiency_limits: data/self_sufficiency_limits.csv
```

Enable in scenario config:

```yaml
solving:
  constraints:
    self_sufficiency: true
```

---

## How to Modify

### Add self-sufficiency target for a country

Add a row to `data/self_sufficiency_limits.csv`:

```csv
DE,H2,2030,0.6,
```

This enforces ≥60% domestic H₂ generation in Germany in 2030.

### Change EU-wide electricity target

```csv
EU,AC,2050,0.75,1.0
```

EU must generate 75–100% of electricity demand in 2050 (no net imports, limited net exports).

### Relax constraint for a specific year

Remove the corresponding row or leave both `min` and `max` blank:

```csv
FR,H2,2035,,
```

### Apply cluster-level constraints

For finer-grained regional policy:

```csv
DE123,AC,2030,0.9,
DE456,AC,2030,0.5,
```

---

## Notes

!!! info "Energy vs. Capacity"
    Unlike the [expansion limits](expansion.md) which constrain installed **capacity** (MW),
    self-sufficiency constraints operate on annual **energy** (MWh) generation and demand.

!!! warning "Empty CSV"
    If `self_sufficiency_limits.csv` contains only headers (no constraint rows) and
    the constraint is enabled, the optimization proceeds without self-sufficiency constraints.

!!! note "External imports"
    External imports (from non-European regions) are represented by generators with carriers
    like `import pipeline-H2` and `import shipping-H2`. These count as imports for
    the purpose of self-sufficiency calculation.

!!! tip "Interaction with other constraints"
    Self-sufficiency constraints are independent of:
    - [Expansion limits](expansion.md) (capacity bounds per technology)  
    - [National grid plans](national_grid_plans.md) (transmission expansion factors)  
    - [TYNDP projects](electricity.md) (cross-border transmission projects)  
    
    All constraints are applied simultaneously during optimization.
