# Curtailment Mode

## Overview

An optional solver feature that explicitly models renewable curtailment by
adding virtual generators with negative costs. When enabled, all renewable
generators are forced to track their maximum availability (`p_min_pu = p_max_pu`)
and negative-cost virtual generators absorb excess electricity that cannot be
consumed or stored.

This makes curtailment volumes directly visible in the optimization results,
useful for analyzing renewable integration and grid flexibility constraints.

The feature is **disabled by default** and can be enabled in the config file.

---

## Snakemake Rule

**Rule:** `solve_elec_networks` / `solve_sector_networks`  
**Script:** `scripts/solve_network.py` — function `prepare_network()`

---

## Implementation

!!! info "PyPSA per-unit dispatch parameters"
    - **`p_max_pu`** — upper bound on dispatch in each time step, as a fraction of `p_nom` (e.g. `0.8` = the generator can produce at most 80% of its capacity in that hour). For renewables this is the availability profile.
    - **`p_min_pu`** — lower bound on dispatch, also as a fraction of `p_nom`. Setting `p_min_pu = p_max_pu` forces the generator to run at exactly its available capacity (no curtailment allowed unless a curtailment generator absorbs the excess).

    These are **time-varying dispatch bounds**, distinct from `p_nom_min`/`p_nom_max` which are bounds on the *installed* capacity chosen by the optimizer.

When enabled, curtailment is modeled explicitly rather than implicitly:

1. All renewable generators have their `p_min_pu` set equal to `p_max_pu`
   (forcing them to "commit" to their full available capacity)
2. Virtual curtailment generators are added at all AC buses with:
   - Negative marginal cost (-0.1 EUR/MWh) to incentivize curtailment
   - Negative dispatch range (`p_min_pu = -1`, `p_max_pu = 0`)
   - Large nominal capacity (1,000 GW)

This allows the optimizer to explicitly curtail renewables when grid
constraints or storage limitations prevent full utilization, making curtailment
volumes directly visible in the results.

### Code

```python title="scripts/solve_network.py"
if solve_opts.get("curtailment_mode"):
    n.add("Carrier", "curtailment", color="#fedfed", nice_name="Curtailment")
    n.generators_t.p_min_pu = n.generators_t.p_max_pu
    buses_i = n.buses.query("carrier == 'AC'").index
    n.madd(
        "Generator",
        buses_i,
        suffix=" curtailment",
        bus=buses_i,
        p_min_pu=-1,
        p_max_pu=0,
        marginal_cost=-0.1,
        carrier="curtailment",
        p_nom=1e6,
    )
```

---

## Configuration

The feature is controlled under `solving.options`:

```yaml title="config/config.agora.yaml"
solving:
  options:
    curtailment_mode: false   # boolean
```

---

## How to Enable

To enable curtailment mode for a specific scenario:

1. **Edit config file** — Set `curtailment_mode: true` in
   `config/config.agora.yaml` under `solving.options`, or

2. **Override in scenario config** — Add the option to a scenario-specific
   YAML file if using scenario overrides

The feature applies to all planning years in the optimization run. Curtailment
results will appear in the network outputs under the `curtailment` carrier and
can be analyzed via:

- `n.generators_t.p` (negative values for curtailment generators)
- `n.statistics()` with carrier filtering
- Post-processing scripts that aggregate by carrier
