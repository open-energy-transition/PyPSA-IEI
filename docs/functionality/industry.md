# Industrial Energy Demand

## Overview

Industry demand is updated from the standard PyPSA-Eur values using data
from the [TransHyDe](https://www.transhyde.eu) project. Two modifications
are made relative to base PyPSA-Eur:

1. **Carrier ratios** for high-temperature processes are remapped to hydrogen
   to better reflect intra-country spatial distribution
2. **Absolute country totals** are scaled to match TransHyDe demand values

---

## Snakemake Rules

| Rule | Script | Purpose |
|---|---|---|
| `build_industry_sector_ratios` | `scripts/build_industry_sector_ratios.py` | Set carrier ratios per industry sector |
| `build_industrial_energy_demand_per_node` | `scripts/build_industrial_energy_demand_per_node.py` | Scale absolute demands to TransHyDe totals |

---

## Demand Scenarios

Three demand scenarios are defined in `build_industry_sector_ratios.py`:

| `demand_scenario` | Description |
|---|---|
| `original` | Reverts to base PyPSA-Eur v0.10.0 carrier ratios |
| `high-temperature` | Hydrogen replaces fossil fuels in furnaces and smelters — reflects TransHyDe Scenario 1.5 (Mid Demand) |
| `high-temperature+steam` | As above, plus hydrogen replaces steam processing — reflects TransHyDe Scenario 2 (High Demand) |

The carrier ratio scenario is selected via `transhyde_processes` in the config:

```yaml title="config/config.agora.yaml"
industry:
  transhyde_data: true
  transhyde_processes: high_temp_only  # use "high-temperature" ratios
  transhyde_scenario: 1.5             # selects input CSV: TH_S1.5_demand.csv
```

`transhyde_scenario` (`1.5` or `2`) and `transhyde_processes` are **independent**:
`transhyde_scenario` selects which TransHyDE CSV is loaded for absolute demand scaling;
`transhyde_processes` controls carrier ratios. They can be combined freely — for example,
the `CE_TranshydeS2` scenario uses `transhyde_scenario: 2` with the default
`transhyde_processes: high_temp_only`.

---

## Hydrogen Demand Distribution

When `transhyde_data: true`, carrier ratios for high-temperature industrial
processes (furnaces, smelters) are remapped to hydrogen. This only affects
**spatial distribution** within a country — the absolute country totals are
overwritten in the next step. From the script docstring:

> When `transhyde_data` is True, processes (mostly heat) are mapped from
> originally electricity/biomass/gas to hydrogen. The mapping is not precise;
> the aim is to get a more realistic distribution of the demand within a country.

---

## Scaling to TransHyDe Totals

`build_industrial_energy_demand_per_node` reads TransHyDe CSV data and scales
PyPSA-Eur's country-level totals to match. The scaling preserves the
intra-country distribution from `build_industry_sector_ratios`:

```python title="scripts/build_industrial_energy_demand_per_node.py"
# Calculate per-carrier scaling factor: TransHyDe total / PyPSA total
factor = (demand_th_p / nodal_df_grp_m).fillna(1.0)

# Apply factor to all nodes, preserving intra-country distribution
nodal_df *= factor

# Where PyPSA has zero demand but TransHyDe has non-zero,
# distribute TransHyDe total using node weights
```

The TransHyDe data files are in `data/transhyde/`.

---

## Ammonia and Methanol Imports

The model can reduce industrial energy demand when ammonia or methanol are
imported rather than produced domestically. Both are disabled by default:

```yaml title="config/config.agora.yaml"
sector:
  ammonia: false
  ammonia_import: false
  ammonia_import_share: 50   # % of demand met by imports, if enabled
  methanol_import: false
  methanol_import_share: 50  # % of demand met by imports, if enabled
```

---

## How to Change the TransHyDe Scenario

Set `transhyde_processes` to control carrier ratios, and `transhyde_scenario` to
select the input CSV for absolute scaling:

```yaml
industry:
  transhyde_processes: high_temp_only  # default; or: with_steam
  transhyde_scenario: 1.5              # default (Mid Demand); or: 2 (High Demand)
```

### Using a custom demand file

`transhyde_scenario` is used directly to build the input file paths:

```
data/transhyde/TH_S{transhyde_scenario}_demand.csv
data/transhyde/TH_S{transhyde_scenario}_process_emissions.csv
```

You can create a custom variant of either file and point to it by choosing
any string as the scenario name. Both files must exist under the same name.

1. Copy both base files and give them a shared custom suffix:

    ```
    cp data/transhyde/TH_S1.5_demand.csv             data/transhyde/TH_Scustom_demand.csv
    cp data/transhyde/TH_S1.5_process_emissions.csv  data/transhyde/TH_Scustom_process_emissions.csv
    ```

2. Edit the demand or emissions file with the scenario-specific values.

3. Point to it in the relevant scenario config under `config/scenarios/`:

    ```yaml title="config/scenarios/config.MY_SCENARIO.yaml"
    industry:
      transhyde_scenario: custom
    ```

    Snakemake will then read `TH_Scustom_demand.csv` and
    `TH_Scustom_process_emissions.csv` for that scenario only.

!!! tip
    If you only need to modify demand (not process emissions), still copy
    the emissions file unchanged — both must be present for the rule to run.
