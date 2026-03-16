# Transmission Losses

## Overview

Transmission losses are modelled by splitting each bidirectional link into two
unidirectional links with `efficiency < 1.0`. The function
`lossy_bidirectional_links()` is applied to every carrier listed under
`sector.transmission_efficiency` in the config. DC links carry a static
converter loss and a length-dependent resistive loss. H₂ and gas pipelines
carry compression losses, drawn as electricity from the sending node. TYNDP
gas pipelines receive the same loss parameters as standard gas pipelines.

---

## Snakemake Rule

**Rule:** `prepare_sector_network`  
**Script:** `scripts/prepare_sector_network.py` — function
`lossy_bidirectional_links()`

---

## Carriers with Losses

| Carrier | `efficiency_static` | `efficiency_per_1000km` | `compression_per_1000km` |
|---|---|---|---|
| DC | 0.98 | 0.977 | — |
| H2 pipeline | — | 1.0 | 0.019 |
| gas pipeline | — | 1.0 | 0.010 |
| electricity distribution grid | 1.0 | — | — |

---

## Implementation

Each bidirectional link is split into a forward link (efficiency applied by
length and static factor) and a reversed copy (`capital_cost = 0`,
`length = 0`). For H₂ and gas pipelines, a secondary electricity bus (`bus2`)
is attached at the sending node and `efficiency2` is set to a negative value
proportional to pipeline length, representing compression energy consumption.

The function is called in a loop over all configured carriers:

```python title="scripts/prepare_sector_network.py"
for k, v in options["transmission_efficiency"].items():
    lossy_bidirectional_links(n, k, v)
```

TYNDP gas pipelines receive an additional dedicated call using the same
`gas pipeline` efficiencies:

```python title="scripts/prepare_sector_network.py"
losses = snakemake.config["sector"]["transmission_efficiency"]["gas pipeline"]
lossy_bidirectional_links(n, "gas pipeline tyndp", losses)
```

---

## Configuration

Efficiency parameters are set under `sector.transmission_efficiency`:

```yaml title="config/config.agora.yaml"
sector:
  transmission_efficiency:
    DC:
      efficiency_static: 0.98
      efficiency_per_1000km: 0.977
    H2 pipeline:
      efficiency_per_1000km: 1      # 0.979 commented out
      compression_per_1000km: 0.019
    gas pipeline:
      efficiency_per_1000km: 1      # 0.977 commented out
      compression_per_1000km: 0.01
    electricity distribution grid:
      efficiency_static: 1          # 0.97 commented out
```

!!! note
    `solving.options.transmission_losses` does **not** control whether
    losses are applied. It only triggers removal of AC lines with
    `num_parallel == 0` that would conflict with the loss-aware solver:

    ```yaml
    solving:
      options:
        transmission_losses: 2
    ```

---

## How to Change Transmission Loss Values

Edit the efficiency values under `sector.transmission_efficiency` in
`config/config.agora.yaml` or a scenario override file. Setting
`efficiency_per_1000km: 1` and `compression_per_1000km: 0` for a carrier
effectively disables losses for that carrier.
