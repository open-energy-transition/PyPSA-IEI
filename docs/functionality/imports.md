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
    [f"{node} {tech}" for node, tech in zip(import_nodes_tech_manipulated_pipeline_h2["bus"],
                                            import_nodes_tech_manipulated_pipeline_h2["tech"])],
    bus=[f"{node} H2" for node in import_nodes_tech_manipulated_pipeline_h2["bus"]],
    carrier=[f"import {tech}" for tech in import_nodes_tech_manipulated_pipeline_h2["tech"]],
    p_nom_extendable=True,
    p_nom_max=[f"{p_nom}" for p_nom in import_nodes_tech_manipulated_pipeline_h2["p_nom"]],
    marginal_cost=[f"{marginal_cost}" for marginal_cost in import_nodes_tech_manipulated_pipeline_h2["marginal_cost"]],
    capital_cost=[f"{capital_cost}" for capital_cost in import_nodes_tech_manipulated_pipeline_h2["capital_cost"]],
    p_min_pu=0,
    lifetime=25,
)

# shipping-H2: same structure, shipping_idx appended to name
n.madd(
    "Generator",
    [f"{node} {tech} ({shipping_idx})" for node, tech, shipping_idx in zip(
        import_nodes_tech_manipulated_shipping_h2["bus"],
        import_nodes_tech_manipulated_shipping_h2["tech"],
        import_nodes_tech_manipulated_shipping_h2["shipping_idx"])],
    bus=[f"{node} H2" for node in import_nodes_tech_manipulated_shipping_h2["bus"]],
    carrier=[f"import {tech}" for tech in import_nodes_tech_manipulated_shipping_h2["tech"]],
    p_nom_extendable=True,
    p_nom_max=[f"{p_nom}" for p_nom in import_nodes_tech_manipulated_shipping_h2["p_nom"]],
    marginal_cost=[f"{marginal_cost}" for marginal_cost in import_nodes_tech_manipulated_shipping_h2["marginal_cost"]],
    capital_cost=[f"{capital_cost}" for capital_cost in import_nodes_tech_manipulated_shipping_h2["capital_cost"]],
    p_min_pu=0,
    lifetime=25,
)
```

**Syngas (pipeline and shipping)** — an intermediate `syngas` bus is created
per node, then a link converts syngas → gas with `efficiency2=-CO2_intensity`
on the `co2 atmosphere` bus:

```python title="scripts/prepare_sector_network.py"
# syngas bus — created once for the union of pipeline-syngas and shipping-syngas nodes
n.madd(
    "Bus",
    [f"{node} syngas" for node in pd.concat([
        import_nodes_tech_manipulated_pipeline_syngas["bus"],
        import_nodes_tech_manipulated_shipping_syngas["bus"]
    ]).unique()],
    location=[f"{node}" for node in pd.concat([
        import_nodes_tech_manipulated_pipeline_syngas["bus"],
        import_nodes_tech_manipulated_shipping_syngas["bus"]
    ]).unique()],
    carrier="syngas",
    unit="MWh_LHV",
)
```

**Synfuel** — same pattern: `synfuel` bus → generator → link to `EU oil` with
`efficiency2=-costs.at["oil", "CO2 intensity"]`.

---

## Input CSV Format

`data/import_nodes_tech_manipulated_s_62_<year>.csv` — one row per import node and technology:

```csv
,bus,Hydrogen Derivate,p_nom,note,tech,shipping_idx,marginal_cost,capital_cost
0,IT1 2,0,36721.2,Pipeline Italien: p_nom=existing gas_pipeline*0.6,pipeline-H2,,97,2688.0
1,BE1 0,,18782.8,,pipeline-syngas,,163,0.0
15,BE1 0,,20780.2,,shipping-syngas,,163,0.0
47,EU,,inf,,synfuel,,161,0.0
48,BE1 0,Ammonia,23000.0,Zeebrugge New Molecules development,shipping-H2,new,99,8421.6
```

| Column | Description |
|---|---|
| `bus` | Model cluster node (e.g. `BE1 0`, `DE1 1`) or `EU` for European aggregate |
| `Hydrogen Derivate` | Hydrogen carrier type (e.g. Ammonia, LH2, LOHC) |
| `p_nom` | Maximum import capacity [MW] |
| `note` | Human-readable description of the import project(s) at this node |
| `tech` | Import technology string |
| `shipping_idx` | Unique index for shipping routes |
| `marginal_cost` | Variable cost [EUR/MWh] |
| `capital_cost` | Annualised investment cost [EUR/MW/year] |

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
