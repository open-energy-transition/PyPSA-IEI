# Myopic Optimization (Brownfield)

## Overview

Myopic pathway optimization builds each planning horizon on top of the
previous one. The `add_brownfield` rule manages this transition by:

1. Carrying forward previously built capacity (fixed, non-extendable)
2. Accounting for gas pipeline retrofitting to H₂
3. Adding newly commissioned powerplants
4. Updating import pipeline and terminal retrofit potentials

---

## Snakemake Rule

**Rule:** `add_brownfield`  
**Script:** `scripts/add_brownfield.py` — function `add_brownfield()`

---

## 1. Carrying Forward Previous Capacity

All assets (Generator, Link, Store) from the previous horizon that are still
within their lifetime are imported into the current network with their
**optimized capacity fixed** (non-extendable):

```python title="scripts/add_brownfield.py"
for c in n_p.iterate_components(["Link", "Generator", "Store"]):
    # Remove assets that have expired
    n_p.mremove(c.name, c.df.index[c.df.build_year + c.df.lifetime < year])

    # Remove assets below minimum capacity threshold
    n_p.mremove(c.name, c.df.index[
        c.df[f"{attr}_nom_extendable"] & (c.df[f"{attr}_nom_opt"] < threshold)
    ])

    # Fix capacity at optimized value from previous horizon
    c.df[f"{attr}_nom"] = c.df[f"{attr}_nom_opt"]
    c.df[f"{attr}_nom_extendable"] = False

    n.import_components_from_dataframe(c.df, c.name)
```

---

## 2. Gas Pipeline Retrofitting

When `H2_retrofit: true`, existing gas pipeline capacity is reduced by the
amount already retrofitted to H₂ in previous horizons:

```python title="scripts/add_brownfield.py"
CH4_per_H2 = 1 / snakemake.params.H2_retrofit_capacity_per_CH4

# Already retrofitted H2 capacity from previous years
already_retrofitted = (
    n.links.loc[h2_retrofitted_fixed_i, "p_nom"]
    .rename(lambda x: x.split("-2")[0].replace(fr, to) + f"-{year}")
    .groupby(level=0).sum()
)

# Remaining gas capacity = original - retrofitted (adjusted for energy ratio)
remaining_capacity = (
    pipe_capacity - CH4_per_H2
    * already_retrofitted.reindex(pipe_capacity.index).fillna(0)
)
n.links.loc[gas_pipes_i, "p_nom"] = remaining_capacity
n.links.loc[gas_pipes_i, "p_nom_max"] = remaining_capacity
```

---

## 3. New Powerplants

A base powerplant network is loaded and newly commissioned plants are
added for the current horizon:

```python title="scripts/add_brownfield.py"
n_ppl = pypsa.Network(snakemake.input.base_powerplants)
all_years = snakemake.config["scenario"]["planning_horizons"]
previous_year = str(all_years[all_years.index(year) - 1])

for ppl_component in n_ppl.iterate_components(["Link", "Generator"]):
    # Select plants commissioned between previous and current year
    idx_ppl = ppl_component.df.index[
        ends_with_year(ppl_component.df.index)
        & (ppl_component.df.index.str[-4:] > previous_year)
        & (ppl_component.df.index.str[-4:] <= str(year))
    ]
    n.generators.loc[idx_ppl, 'p_nom'] = ppl_component.df.loc[idx_ppl, 'p_nom']
```

---

## 4. Import Pipeline and Terminal Retrofitting

The same retrofit logic is applied to non-European gas import pipelines and
LNG terminals:

```python title="scripts/add_brownfield.py"
# Remaining gas pipeline capacity after retrofit
remaining_capacity_pipes = (
    full_capacity_pipes
    - CH4_per_H2 * retrofitted_capacity_pipes
      .rename(lambda x: x[:5] + ' import pipeline gas')
      .groupby(level=0).sum()
)
n.generators.loc[filtered_natural_gas_pipes_i, 'p_nom_max'] = remaining_capacity_pipes

# Remaining H2 retrofit potential
remaining_capacity_pipes_retro = (
    max_capacity_retrofit_pipes
    - retrofitted_capacity_pipes
      .rename(lambda x: x[:-4] + str(year))
      .groupby(level=0).sum()
)
n.generators.loc[filtered_h2_pipes_ext_i, 'p_nom_max'] = remaining_capacity_pipes_retro
```

The same pattern applies to LNG → H₂ terminal retrofitting.

---

## How to Configure

```yaml title="config/config.agora.yaml"
sector:
  H2_retrofit: true                      # enable gas-to-H2 retrofitting
  H2_retrofit_capacity_per_CH4: 0.6      # H2 capacity per CH4 capacity unit

existing_capacities:
  threshold_capacity: 10                 # MW — assets below this are dropped
```

Planning horizons are defined in the scenario config:

```yaml title="config/scenarios/config.CE.yaml"
scenario:
  planning_horizons: [2020, 2025, 2030, 2035, 2040, 2045, 2050]
```
