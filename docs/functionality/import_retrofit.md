# Import Infrastructure Retrofitting

## Overview

Allows **retrofitting of existing natural gas import infrastructure** (both
pipelines and LNG terminals) to hydrogen, and enables **dual use** of gas
infrastructure by syngas. This constraint models the reuse of import capacity
as energy carriers transition from fossil to renewable/synthetic fuels.

Two types of infrastructure can be retrofitted or shared:

1. **Pipeline imports**: CH₄ pipelines → H₂ pipelines  
2. **LNG terminals**: Liquefied natural gas → Liquefied hydrogen  

Additionally, natural gas infrastructure can be **dual-used** by syngas without retrofitting.

This constraint is **always enabled** and applies wherever import generators
for multiple gas types exist at the same location.

---

## Snakemake Rule

**Script:** `scripts/solve_network.py` — function
`add_import_retrofit_constraint`, called from `extra_functionality`  
**Rule:** `solve_sector_network_myopic`

---

## How It Works

### Pipeline Retrofitting

For locations where both `import pipeline gas` and `import pipeline-H2`
generators exist (same cluster), the following constraint applies:

**Constraint:**  
CH₄ capacity + (H₂ capacity / retrofit factor) = Initial CH₄ capacity

Where:  
- CH₄ capacity = optimized natural gas pipeline capacity  
- H₂ capacity = optimized hydrogen pipeline capacity  
- Retrofit factor = `H2_retrofit_capacity_per_CH4` (default: 0.6)  
- Initial CH₄ capacity = existing natural gas pipeline capacity (`p_nom_max`)

**Interpretation:** 1 MW of CH₄ pipeline can transport 0.6 MW of H₂ after
retrofitting (due to lower volumetric energy density). Total usage cannot
exceed the original CH₄ capacity in energy-equivalent terms.

### LNG Terminal Retrofitting

For locations with both `import lng gas` and `import shipping-H2 (retrofitted)`:

**Constraint:**  
LNG capacity + Liquefied H₂ capacity = Initial LNG capacity

LNG terminals can be split between natural gas and liquefied hydrogen imports,
with total capacity constrained to the original LNG terminal size.

### Dual Use by Syngas

Natural gas pipelines and LNG terminals can be **simultaneously used** by
syngas without capacity conversion factors:

**Pipelines:**  
At each time step: CH₄ dispatch + Syngas dispatch ≤ CH₄ installed capacity

**LNG terminals:**  
At each time step: LNG dispatch + Syngas-shipping dispatch ≤ LNG installed capacity

Additionally, the installed capacity of syngas import generators is set equal
to the natural gas capacity to enable dual use.

---

## Config

```yaml
sector:
  H2_retrofit_capacity_per_CH4: 0.6  # 1 MW CH4 → 0.6 MW H2
```

**`H2_retrofit_capacity_per_CH4`**: Ratio of hydrogen transport capacity to
methane capacity after retrofitting a pipeline (unitless, typically 0.5–0.7
due to H₂'s lower volumetric energy density).

---

## How to Modify

### Change H₂ retrofit efficiency

```yaml
sector:
  H2_retrofit_capacity_per_CH4: 0.5  # more conservative (1 MW CH4 → 0.5 MW H2)
```

### Disable retrofitting (not recommended)

The constraint is automatically applied where import generators exist.
To effectively disable:

1. Remove H₂ import generators from `data/import_nodes_tech_manipulated_s_62_<year>.csv`, or  
2. Remove `add_import_retrofit_constraint(n)` call from `extra_functionality`
   in `solve_network.py` (modifies core code)
