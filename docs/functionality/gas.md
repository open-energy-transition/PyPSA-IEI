# Gas Network

## Overview

Two key modifications are made to the gas network relative to base PyPSA-Eur:

1. **Russian gas imports are removed** in all scenarios by default
2. **TYNDP gas pipeline projects** are processed and added to the model

---

## Russian Import Removal

**Rule:** `build_gas_input_locations`  
**Script:** `scripts/build_gas_input_locations.py`

The base config sets `import_from_russia: false` under `sector:`, so Russian
pipeline entry points are excluded in all scenarios. If re-enabled but
`nordstream` is disabled, only the Nord Stream pipeline is excluded:

```python title="scripts/build_gas_input_locations.py"
if not snakemake.params.import_from_russia:
    entry = entry.loc[~(entry.from_country == "RU")]
elif not snakemake.params.nordstream:
    entry = entry.loc[entry.id != "INET_BP_63"]
```

---

## TYNDP Gas Pipelines

**Rule:** `build_tyndp_gas_pipes`  
**Script:** `scripts/build_tyndp_gas_pipes.py`

TYNDP gas pipeline project data is processed and mapped to model cluster
regions using geographic coordinates:

```python title="scripts/build_tyndp_gas_pipes.py"
# Load TYNDP project list
tyndp_raw_data = pd.read_excel(snakemake.input.tyndp_gas_projects)

# Remove projects with missing critical data
tyndp_raw_data.dropna(subset=[
    'Code', 'Project Name', 'Maturity Status', 'Diameter (mm)',
    'Length (km)', 'PCI 5th List', 'Project Commissioning Year Last',
    'Start', 'End'
], inplace=True)

# Convert DMS coordinates to cluster names
def coordinates_to_cluster(coordinates):
    ...
    point = Point(dd_lon, dd_lat)
    return regions.loc[regions['geometry'].contains(point), 'name'].values[0]
```

Pipe capacity is derived from diameter using the `diameter_to_capacity`
function (from `build_gas_network.py`). Projects entirely within one cluster
are dropped. The output is saved to CSV for use in `prepare_sector_network`.

---

## Scenario-Dependent Project Selection

TYNDP projects are filtered by maturity status via the scenario config:

| Scenario | `allowed_statuses` |
|---|---|
| CE | `FID` only |
| SE | all statuses (no filter) |

```yaml title="config/scenarios/config.CE.yaml"
policy_plans:
  include_tyndp_gas:
    enable: true
    allowed_statuses:
      - FID  # Final Investment Decision
```

---

## How to Modify

To change which TYNDP projects are included, set `allowed_statuses` in the
scenario config file. To allow all maturity levels, omit the key entirely:

```yaml title="config/scenarios/config.CE.yaml"
policy_plans:
  include_tyndp_gas:
    enable: true
    allowed_statuses:
      - FID
      - Advanced
      - Less Advanced
```

To control Russian import handling, override in the scenario config:

```yaml
sector:
  import_from_russia: false  # set to true to allow Russian pipeline gas
  nordstream: false          # set to true to include Nord Stream specifically
```

To add custom gas pipeline projects, extend the TYNDP Excel input file
(`data/gas_network/TYNDP_Gas_Interconnectors.xlsx`) with the required columns
(`Code`, `Diameter (mm)`, `Length (km)`, `Start`, `End`, `Maturity Status`, etc.).
