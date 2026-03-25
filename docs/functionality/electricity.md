# Electricity Network

## Overview

TYNDP electricity transmission projects are enforced on the network in
`prepare_sector_network`. Per-project capacity limits are read from two CSV
files and applied for each planning horizon. Cross-border lines and links can
optionally be made extendable from a given year onwards.

---

## Snakemake Rule

**Rule:** `prepare_sector_network`  
**Script:** `scripts/prepare_sector_network.py` — function `set_capacity_tyndp_elec()`

**Input data:**

- `data/links_2020-2050.csv` — DC link capacity limits per year
- `data/lines_2020-2050.csv` — AC line capacity additions per year and TYNDP status

---

## Scenario Behaviour

| Scenario | TYNDP statuses included | Cross-border extendable from |
|---|---|---|
| CE, CN | `under construction` | All horizons (`optimize_after: true`) |
| SE, SN | `in planning`, `in permitting`, `under construction` | 2040 onwards (`optimize_after: 2040`) |

---

## CSV Data Format

### `data/links_2020-2050.csv`

Columns: `name`, `bus0`, `bus1`, `p_nom`, `2020`, `2025`, …, `2050`

Each year column contains a fraction of `p_nom` or `opt`:

| Value | Effect |
|---|---|
| `0.0` | Link not active in this year |
| `1` (float > 0) | `p_nom_min = p_nom_max = p_nom × value`, link made extendable |
| `opt` | `p_nom_min = p_nom`, link remains extendable without upper bound |

### `data/lines_2020-2050.csv`

Columns: `name`, `bus0`, `bus1`, then one column per `{year}{status}` combination
(e.g., `2025under construction`, `2030in planning`).

Each cell holds the capacity addition [MW] for that year and status, or `opt`
for a soft minimum (extendable without upper bound). Values with an `opt`
suffix set the minimum and leave the line extendable.

---

## Configuration

TYNDP electricity enforcement is disabled by default and enabled per scenario:

```yaml title="config/config.agora.yaml"
policy_plans:
  include_tyndp_elec:
    enable: false           # set to true in scenario configs
    allowed_statuses:
      - under consideration
      - in planning
      - in permitting
      - under construction
    optimize_after: true    # true = all horizons; integer year = from that year
```

```yaml title="config/scenarios/config.CE.yaml"
policy_plans:
  include_tyndp_elec:
    enable: true
    allowed_statuses:
      - under construction
    # optimize_after inherits true from base config
```

```yaml title="config/scenarios/config.SE.yaml"
policy_plans:
  include_tyndp_elec:
    enable: true
    allowed_statuses:
      - in planning
      - in permitting
      - under construction
    optimize_after: 2040
```

---

## How to Change the TYNDP enforcement

### Configure which TYNDP projects are enforced

Edit `policy_plans.include_tyndp_elec.allowed_statuses` in the scenario config.
Only projects whose TYNDP status tag matches an entry in this list are enforced.

### Configure when cross-border links become extendable

Set `policy_plans.include_tyndp_elec.optimize_after` to `true` (all horizons)
or to an integer year (e.g., `2040`) in the scenario config.

### Modify capacity values per horizon

Edit the year columns in `data/links_2020-2050.csv` (DC links) or the
`{year}{status}` columns in `data/lines_2020-2050.csv` (AC lines).
