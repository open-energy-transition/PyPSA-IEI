# Expansion Limits

## Overview

Minimum and maximum capacity constraints are enforced for selected renewable
and other carriers across European countries for each planning year.
The constraints target **total cumulative installed capacity** per
country and carrier. Existing (non-extendable) capacity is subtracted before
the bound is applied to the extendable `p_nom` decision variable.

---

## Snakemake Rule

**Script:** `scripts/solve_network.py` — function
`add_country_carrier_limit_constraints`, called from `extra_functionality`  
**Rule:** `solve_sector_network_myopic`  
**Data files:** selected via `policy_plans.agg_p_nom_limits` in the scenario config

| Scenario | Data file | Min/max band |
|---|---|---|
| CE, SE, and variants | `data/agg_p_nom_minmax_european.csv` | ±20 % |
| CN, SN | `data/agg_p_nom_minmax_national.csv` | ±15 % |

---

## Carriers and Components

| Carrier | Component | Geographic scope | Years with data |
|---|---|---|---|
| `solar` | Generator | All modelled countries | 2030, 2050 |
| `onwind` | Generator | All modelled countries | 2030, 2050 |
| `offwind` | Generator | All modelled countries | 2030, 2050 |
| `H2 Electrolysis` | Link | European-wide (`Eur`) + Romania | 2030 |
| `gas for electricity` | Link | Poland (2020–2030), Romania (2020–2050) | varies |
| `co2 sequestered` | Store | Romania | 2030–2050 |

`gas for electricity` is a **grouped carrier**: OCGT, CCGT, urban central gas
CHP (and CHP CC), micro gas CHP variants, and `allam` are all counted together
against this limit. For Links, the constraint is applied to output capacity
(`p_nom × efficiency`), not input capacity.

---

## CSV Format

Both files share the same long format: one row per (country, carrier, year)
combination. Empty `min` or `max` cells mean no constraint for that direction.

| Column | Description |
|---|---|
| `country` | ISO2 country code, or `Eur` for European-wide aggregate |
| `carrier` | Carrier name as it appears in the constraint (see grouping above) |
| `year` | Planning year (integer) |
| `min` | Minimum total installed capacity [MW or t for CO₂] — blank = unconstrained |
| `max` | Maximum total installed capacity [MW or t for CO₂] — blank = unconstrained |
| `unit` | Unit string (e.g. `MW`, `MW_H2`, `t`) |
| `Source` | Source reference |
| `component` | PyPSA component type in **lowercase** (`generator`, `link`, `store`) |

Example rows:

```csv
country,carrier,year,min,max,unit,Source,component
DE,solar,2030,172000.0,258000.0,MW,Ember,generator
DE,solar,2050,9600.0,175423.9,MW,Atlite,generator
PL,gas for electricity,2025,,5500.0,MW,Forum Energii 2025/03/07,link
Eur,H2 Electrolysis,2030,46978.8,111532.4,MW_H2,IEA hydrogen map,link
RO,co2 sequestered,2030,,10000000.0,t,NZIA communicated by EPG,store
```

---

## Config

The active file is set via `policy_plans.agg_p_nom_limits`. The base config
uses the European file; scenario configs override it:

```yaml title="config/config.agora.yaml"
policy_plans:
  agg_p_nom_limits: data/agg_p_nom_minmax_european.csv  # default
```

```yaml title="config/scenarios/config.CN.yaml  |  config.SN.yaml"
policy_plans:
  agg_p_nom_limits: data/agg_p_nom_minmax_national.csv
```

!!! note
    The two files differ only in the ±% band applied to the 2030 Ember/NECP
    targets: ±20 % in the European file and ±15 % in the national file.
    The 2050 upper bounds (Atlite technical potentials) and all non-renewable
    entries are identical.

You have two options for customising the limits.

**Option 1: Edit a shared file (applies to all runs that use it)**

Edit `data/agg_p_nom_minmax_european.csv` or `data/agg_p_nom_minmax_national.csv`
directly. All scenarios that reference the file will pick up the change.

**Option 2: Create a scenario-specific file (applies to selected runs only)**

1. Copy the relevant base file and give it a descriptive name:

    ```
    cp data/agg_p_nom_minmax_european.csv data/agg_p_nom_minmax_custom.csv
    ```

2. Edit the copy with the scenario-specific capacity limits.

3. Point to it in the relevant scenario config under `config/scenarios/`:

    ```yaml title="config/scenarios/config.MY_SCENARIO.yaml"
    policy_plans:
      agg_p_nom_limits: data/agg_p_nom_minmax_custom.csv
    ```

    This overrides only `agg_p_nom_limits` for that scenario; all
    other config values remain inherited from `config.agora.yaml`.

!!! tip
    This is useful when comparing scenarios with different renewable
    expansion ambition levels — e.g. a moderate baseline and a high-ambition
    sensitivity — without modifying the shared files.

---

## How to Modify the Expansion Limits

### Change a capacity limit for a country

Edit the relevant CSV directly. Each row is a single (country, carrier, year)
entry. For example, to raise the solar minimum in Spain for 2030:

```csv
ES,solar,2030,130000.0,195000.0,MW,Custom,generator
```

### Add a constraint to new country or carrier

Add a new row with `country`, `carrier`, `year`, `min`/`max`, and `component`.
Make sure `carrier` matches the grouped name (e.g. use `offwind`, not
`offwind-ac`) and `component` is lowercase.

### Add a European-wide constraint

Use `Eur` as the `country` value. The code automatically duplicates every
component into an `Eur` group and adds both country-level and European-level
`p_nom` to the left-hand side of the constraint.
