# Overall Minimum Capacities

## Overview

Enforces minimum total installed capacity per carrier **across all nodes**
in the model. Unlike per-country expansion limits, this constraint sets a
floor on the **aggregate capacity** for specific generation technologies
across the entire system (e.g., all of Europe).

This is useful for business-as-usual (BAU) scenarios or policy mandates
that require a minimum deployment of certain technologies regardless of
where they are located.

**Example:** Enforce at least 100 GW of OCGT capacity across all nodes —  
the sum of OCGT capacity across all nodes must be ≥ 100,000 MW.

---

## Snakemake Rule

**Script:** `scripts/solve_network.py` — function
`add_overall_min_capacities_constraints`, called from `extra_functionality`  
**Rule:** `solve_sector_network_myopic`

---

## Scenario Behavior

By default, this constraint is **disabled** in all scenarios.

Enable via scenario config:

```yaml
solving:
  constraints:
    overall_min_capacities: true
```

---

## How It Works

For each carrier specified in `electricity.BAU_mincapacities`:

1. Sum the extendable `p_nom` capacity across all generators with that carrier  
2. Constrain the sum to be ≥ the specified minimum (in MW)

Only applies to **extendable generators**. Existing (non-extendable) capacity
is excluded from the constraint.

---

## Config

Add to your config (typically in a scenario file):

```yaml
electricity:
  BAU_mincapacities:
    solar: 50000      # minimum 50 GW solar across all nodes
    onwind: 100000    # minimum 100 GW onshore wind
    OCGT: 20000       # minimum 20 GW OCGT
    offwind-ac: 0     # no minimum (can be omitted)
    offwind-dc: 0     # no minimum (can be omitted)

solving:
  constraints:
    overall_min_capacities: true
```

**Format:** Carrier name → minimum capacity in MW

---

## How to Modify

### Add minimum capacity for a technology

Add an entry to `electricity.BAU_mincapacities`:

```yaml
electricity:
  BAU_mincapacities:
    nuclear: 50000  # enforce at least 50 GW nuclear across Europe
```

### Remove a constraint

Set to `0` or remove the carrier entry:

```yaml
electricity:
  BAU_mincapacities:
    solar: 0  # no minimum solar requirement
```

### Disable the constraint entirely

```yaml
solving:
  constraints:
    overall_min_capacities: false
```
