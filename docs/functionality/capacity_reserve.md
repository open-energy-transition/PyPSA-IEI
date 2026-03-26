# Capacity Reserve Margin

## Overview

Enforces a **capacity reserve margin** as a percentage above peak demand,
requiring sufficient dispatchable generation capacity to cover peak load
plus a safety margin. Only **conventional (dispatchable) generation**
counts toward the reserve; renewable and storage units are excluded.

**Origin:** This constraint is from **PyPSA-Eur**, where it was originally
called "SAFE" (capacity reserve). It has been renamed to `capacity_reserve`
for clarity.

This constraint models security-of-supply requirements or capacity markets
where a minimum firm capacity must be maintained regardless of renewables
penetration.

**Example:** 10% reserve margin means total conventional capacity must be
≥110% of peak demand.

---

## Snakemake Rule

**Script:** `scripts/solve_network.py` — function
`add_capacity_reserve_constraints`, called from `extra_functionality`  
**Rule:** `solve_sector_network_myopic`

---

## Scenario Behavior

By default, this constraint is **disabled** in all scenarios.

Enable via scenario config:

```yaml
solving:
  constraints:
    capacity_reserve: true
```

---

## How It Works

1. Calculate peak demand as the maximum total load across all time steps  
2. Apply reserve margin: Required capacity = Peak demand × (1 + margin)  
3. Sum existing + extendable conventional generation capacity  
4. Constrain: Total conventional capacity ≥ Required capacity

**Conventional carriers** are defined in `electricity.conventional_carriers`:
- `nuclear`, `coal`, `lignite`, `oil`, `OCGT`, `CCGT`, `geothermal`, `biomass`  

**Excluded** from the constraint:  
- Renewable generators (solar, wind)  
- Storage units (batteries, hydro)  
- Transmission capacity  

---

## Config

Add to your config (typically in a scenario file):

```yaml
electricity:
  capacity_reserve_margin: 0.1  # 10% reserve above peak demand
  conventional_carriers:
    - nuclear
    - oil
    - OCGT
    - CCGT
    - coal
    - lignite
    - geothermal
    - biomass

solving:
  constraints:
    capacity_reserve: true
```

**`capacity_reserve_margin`**: Fraction above peak demand (0.1 = 10%, 0.15 = 15%, etc.)

---

## How to Modify

### Change the reserve margin

```yaml
electricity:
  capacity_reserve_margin: 0.15  # increase to 15%
```

### Define which carriers count as "conventional"

Edit the list to include/exclude specific technologies:

```yaml
electricity:
  conventional_carriers:
    - nuclear
    - CCGT  # exclude OCGT and coal from reserve requirement
```

### Disable the constraint

```yaml
solving:
  constraints:
    capacity_reserve: false
```
