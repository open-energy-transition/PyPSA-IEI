# Energy Imports

## Overview

Energy imports are modelled as **extendable generators** (with supporting
buses and links where needed), covering five import technologies: hydrogen
(pipeline and shipping), syngas (pipeline and shipping), and synfuel.
Import capacities, costs, and node assignments are loaded from a
planning-year-specific CSV file derived from the
[TransHyDe project](https://www.wasserstoff-leitprojekte.de/lw_resource/datapool/systemfiles/cbox/2662/live/lw_datei/transhyde_kurzanalyse_h2-beschleunigungsg.pdf).

---

## Snakemake Rule

**Rule:** `prepare_sector_network`  
**Script:** `scripts/prepare_sector_network.py` — function `add_import()`  
**Data:** `data/import_nodes_tech_manipulated_s_62_<year>.csv`

---

## Import Technologies

| Technology | Components added | Carrier |
|---|---|---|
| `pipeline-H2` | Generator → `{node} H2` bus | `import pipeline-H2` |
| `shipping-H2` | Generator → `{node} H2` bus | `import shipping-H2` |
| `pipeline-syngas` | Bus (`syngas`) + Generator + Link (`syngas→gas`) | `import pipeline-syngas` |
| `shipping-syngas` | Generator → existing `syngas` bus + Link (`syngas→gas`) | `import shipping-syngas` |
| `synfuel` | Bus (`synfuel`) + Generator + Link (`synfuel→EU oil`) | `synfuel` |

For H₂ (pipeline and shipping), only a generator is needed since H₂ buses
already exist. For syngas and synfuel, an intermediate bus is created and a
link converts to the model's gas/oil network with a **negative CO₂ efficiency**
on the `co2 atmosphere` bus — this cancels out the emissions that would
otherwise be attributed when the synthetic fuel is eventually consumed.

---

## Implementation

**H₂ (pipeline and shipping)** — generator only, injecting directly into the
node's existing H₂ bus. Shipping routes include `shipping_idx` in the
component name to distinguish multiple routes to the same node:

```python title="scripts/prepare_sector_network.py"
# pipeline-H2: generator → {node} H2
n.madd(
    "Generator",
    [f"{node} {tech}" for node, tech in zip(df_pipeline_h2["bus"], df_pipeline_h2["tech"])],
    bus=[f"{node} H2" for node in df_pipeline_h2["bus"]],
    carrier=[f"import {tech}" for tech in df_pipeline_h2["tech"]],
    p_nom_extendable=True,
    p_nom_max=df_pipeline_h2["p_nom"],
    marginal_cost=df_pipeline_h2["marginal_cost"],
    capital_cost=df_pipeline_h2["capital_cost"],
    p_min_pu=0,
    lifetime=25,
)

# shipping-H2: same structure, shipping_idx appended to name
n.madd(
    "Generator",
    [f"{node} {tech} ({idx})" for node, tech, idx in zip(
        df_shipping_h2["bus"], df_shipping_h2["tech"], df_shipping_h2["shipping_idx"])],
    bus=[f"{node} H2" for node in df_shipping_h2["bus"]],
    ...
)
```

**Syngas (pipeline and shipping)** — an intermediate `syngas` bus is created
per node, then a link converts syngas → gas with `efficiency2=-CO2_intensity`
on the `co2 atmosphere` bus:

```python title="scripts/prepare_sector_network.py"
# syngas bus
n.madd("Bus", [f"{node} syngas" for node in syngas_nodes], carrier="syngas", unit="MWh_LHV")

# generator → syngas bus
n.madd("Generator", ..., bus=[f"{node} syngas" for node in ...])

# link: syngas → gas, with negative CO2 efficiency to cancel combustion emissions
n.madd(
    "Link",
    [f"{node} syngas" for node in syngas_nodes],
    bus0=[f"{node} syngas" for node in syngas_nodes],
    bus1=[f"{node} gas" for node in syngas_nodes],
    bus2="co2 atmosphere",
    carrier="syngas to gas",
    efficiency2=-costs.at["gas", "CO2 intensity"],
    p_nom_extendable=True,
)
```

**Synfuel** — same pattern: `synfuel` bus → generator → link to `EU oil` with
`efficiency2=-costs.at["oil", "CO2 intensity"]`.

---

## Input CSV Format

`data/import_nodes_tech_manipulated_s_62_<year>.csv`:

| Column | Description |
|---|---|
| `bus` | Model cluster node (e.g. `DE0 0`) or `EU` for European aggregate |
| `tech` | Import technology string |
| `p_nom` | Maximum import capacity [MW] |
| `marginal_cost` | Variable cost [EUR/MWh] |
| `capital_cost` | Annualised investment cost [EUR/MW/year] |
| `shipping_idx` | Unique index for shipping routes |

---

## How to Modify Imports

### Import Capacities and Costs
To change import capacities or costs, edit the relevant year file:

```
data/import_nodes_tech_manipulated_s_62_2030.csv
data/import_nodes_tech_manipulated_s_62_2035.csv
...
```
### Import nodes
To add a new import node, add a row with the correct bus name, technology,
and capacity. Bus names must match nodes in the clustered network
(`s_62` = 62-node clustering). To disable all imports, remove or comment out
the `add_import(n)` call in `prepare_sector_network.py`.
