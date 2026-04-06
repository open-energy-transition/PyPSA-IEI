# CO₂ Pipeline Network

## Overview

CO₂ pipeline transport is a standard feature of
[PyPSA-Eur v0.10.0](https://github.com/PyPSA/pypsa-eur/tree/v0.10.0), retained
unchanged in PyPSA-IEI. The CO₂ pipeline and submarine pipeline investment
costs are overridden from the technology-data baseline — see [Costs](costs.md)
for details.

When both `co2_spatial: true` and `co2network: true` are set, the model builds
an endogenously expandable CO₂ transport network. Each pipeline is a
**bidirectional PyPSA Link** connecting per-node CO₂ storage tanks, whose
candidate routes are derived automatically from the existing electricity
transmission topology. This allows the optimiser to decide where captured CO₂
is temporarily stored, transported between nodes, and ultimately sequestered
underground — rather than assuming a single, spatially aggregated CO₂ pool.

---

## Snakemake Rule

**Rule:** `prepare_sector_network`
**Script:** `scripts/prepare_sector_network.py`

Two functions are called in sequence:

| Function | Purpose |
|---|---|
| `add_co2_tracking()` | Adds atmospheric and regional CO₂ buses, short-term storage tanks, sequestration stores, and optional vent links |
| `add_co2_network()` | Derives candidate pipeline routes from the electricity network and adds bidirectional pipeline links |

---

## Network Topology

Pipeline routes are derived automatically — no separate pipeline dataset is
required. `create_network_topology()` scans all AC lines and DC links in the
network, groups connections by unique node-pair, and averages their `length`
and `underwater_fraction`:

```python title="scripts/prepare_sector_network.py"
co2_links = create_network_topology(n, "CO2 pipeline ")
```

The resulting pipeline names follow the pattern `CO2 pipeline <nodeA> -> <nodeB>`.
Connections where both ends belong to the same node are dropped automatically.

---

## Cost Calculation

Capital cost per pipeline route combines separate onshore and submarine cost
rates weighted by the route's `underwater_fraction`:

```python title="scripts/prepare_sector_network.py"
cost_onshore = (
    (1 - co2_links.underwater_fraction)
    * costs.at["CO2 pipeline", "fixed"]
    * co2_links.length
)
cost_submarine = (
    co2_links.underwater_fraction
    * costs.at["CO2 submarine pipeline", "fixed"]
    * co2_links.length
)
capital_cost = cost_onshore + cost_submarine
capital_cost *= snakemake.config["sector"]["co2_network_cost_factor"]
```

| Parameter | Source |
|---|---|
| `CO2 pipeline` fixed cost (€/MW/km/yr) | `data/costs_<year>.csv` — overridden, see [Costs](costs.md) |
| `CO2 submarine pipeline` fixed cost (€/MW/km/yr) | `data/costs_<year>.csv` — overridden, see [Costs](costs.md) |
| `CO2 pipeline` lifetime (years) | `data/costs_<year>.csv` |
| `co2_network_cost_factor` | `config.agora.yaml` → `sector:` |

Each pipeline is added as a fully bidirectional link (`p_min_pu=-1`), with
capacity determined endogenously by the optimiser (`p_nom_extendable=True`):

```python title="scripts/prepare_sector_network.py"
n.madd(
    "Link",
    co2_links.index,
    bus0=co2_links.bus0.values + " co2 stored",
    bus1=co2_links.bus1.values + " co2 stored",
    p_min_pu=-1,            # bidirectional: negative flow = reversed direction
    p_nom_extendable=True,
    length=co2_links.length.values,
    capital_cost=capital_cost.values,
    carrier="CO2 pipeline",
    lifetime=costs.at["CO2 pipeline", "lifetime"],
)
```

---

## Regional Sequestration Potential

Underground storage at `<node> co2 sequestered` is capped per node when
`regional_co2_sequestration_potential.enable: true`. Geological potentials are
sourced from the [CO2Stop database](https://setis.ec.europa.eu/european-co2-storage-database_en)
(European Commission) and spatially overlaid with model regions in
`scripts/build_sequestration_potentials.py`. Per-node limits are clipped to
`max_size` and divided by `years_of_storage` to convert a total geological
capacity into an annual flow rate:

```python title="scripts/prepare_sector_network.py"
e_nom_max = (
    e_nom_max
    .reindex(spatial.co2.locations)
    .fillna(0.0)
    .clip(upper=upper_limit)   # max_size in Mt
    .mul(1e6)                  # Mt → t
    / annualiser               # total capacity → annual rate
)
```

| Config key | Value | Meaning |
|---|---|---|
| `regional_co2_sequestration_potential.enable` | `true` | Apply per-node sequestration caps |
| `regional_co2_sequestration_potential.attribute` | `'conservative estimate Mt'` | Column from CO2Stop dataset to use |
| `regional_co2_sequestration_potential.include_onshore` | `true` | Include onshore geological formations |
| `regional_co2_sequestration_potential.min_size` | `3` | Minimum site size to include (Mt CO₂) |
| `regional_co2_sequestration_potential.max_size` | `25` | Hard upper cap per node (Mt CO₂) |
| `regional_co2_sequestration_potential.years_of_storage` | `25` | Annualisation divisor |
| `co2_sequestration_cost` | `10` | Cost (€/t CO₂) |
| `co2_sequestration_lifetime` | `50` | Lifetime (years) |

---

## Configuration

```yaml title="config/config.agora.yaml"
sector:
  co2_spatial: true          # enable per-node CO₂ buses (required for CO₂ network)
  co2network: true           # add CO₂ pipeline links
  co2_network_cost_factor: 1 # cost multiplier (1 = unchanged)
  co2_vent: true             # allow venting of stored CO₂ back to atmosphere
  regional_co2_sequestration_potential:
    enable: true
    attribute: 'conservative estimate Mt'  # column from CO2Stop dataset
    include_onshore: true                  # include onshore formations
    min_size: 3                            # minimum site size (Mt CO₂)
    max_size: 25                           # upper cap per node (Mt CO₂)
    years_of_storage: 25                   # annualisation divisor
  co2_sequestration_potential: 500  # fallback global cap (Mt/yr) if regional disabled
  co2_sequestration_cost: 10        # €/t CO₂
  co2_sequestration_lifetime: 50    # years
```

---

## How to Modify the CO₂ Network

### Disable CO₂ pipelines while keeping spatial tracking

```yaml
sector:
  co2_spatial: true
  co2network: false  # each node stores CO₂ independently, no transport
```

### Disable spatial CO₂ tracking entirely

```yaml
sector:
  co2_spatial: false  # all CO₂ collapses to a single EU-level bus
  co2network: false
```

### Scale all pipeline costs

```yaml
sector:
  co2_network_cost_factor: 1.5  # 50% more expensive pipelines
```

### Remove regional sequestration caps

```yaml
sector:
  regional_co2_sequestration_potential:
    enable: false
  co2_sequestration_potential: .inf  # unlimited global sequestration
```
