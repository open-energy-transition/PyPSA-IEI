# Costs

## Overview

The model uses cost assumptions from
[technology-data v0.9.0](https://github.com/PyPSA/technology-data) as a
baseline (stored in `data/costs_{planning_horizon}.csv`). Selected investment
costs are **overridden per planning horizon** using values defined in
`config/config.agora.yaml`.

---

## Snakemake Rule

**Rule:** `update_costs_csv`  
**Script:** `scripts/update_costs_csv.py`

This rule reads the baseline costs CSV and updates specific technology
investment costs before the network is built.

---

## How It Works

```python title="scripts/update_costs_csv.py"
def insert_new_costs(costs_file, invest_update, filename):
    costs = pd.read_csv(costs_file).set_index('technology')
    for key, investment in invest_update.items():
        mask = (costs.parameter == "investment") & (costs.index == key)
        costs.loc[mask, 'value'] = investment
    costs.to_csv(filename)

# Called with per-horizon values from config:
investment_update = snakemake.params.invest_update[int(snakemake.wildcards.planning_horizons)]
insert_new_costs(snakemake.input.costs, investment_update, snakemake.output.costs)
```

---

## Technologies Updated in All Scenarios

These investment costs are overridden for **every scenario** and every
planning year:

| Technology | Config key |
|---|---|
| HVDC overhead line | `HVDC overhead` |
| HVDC submarine cable | `HVDC submarine` |
| HVAC overhead line | `HVAC overhead` |
| H₂ electrolysis | `electrolysis` |
| CO₂ pipeline | `CO2 pipeline` |
| CO₂ submarine pipeline | `CO2 submarine pipeline` |

---

## Additional Technologies (CE Flexibility Scenario Only)

In the CE flexibility scenario (`config.CE_flexibility.yaml`), investment
costs for the following heat-sector technologies are set to **20% above the
technology-data v0.9.0 baseline** for every planning year:

| Technology (config key) |
|---|
| `central air-sourced heat pump` |
| `central ground-sourced heat pump` |
| `decentral air-sourced heat pump` |
| `decentral ground-sourced heat pump` |
| `central solid biomass CHP` |
| `central gas CHP` |
| `micro CHP` |
| `biomass CHP capture` |
| `central water tank storage` |
| `decentral water tank storage` |
| `central resistive heater` |
| `decentral resistive heater` |

Example for 2030:

| Technology | Unit | Baseline (tech-data) | CE Flexibility (+20%) |
|---|---|---|---|
| `central air-sourced heat pump` | EUR/kW_th | 906.1 | 1087.3 |
| `decentral air-sourced heat pump` | EUR/kW_th | 899.5 | 1079.4 |
| `central gas CHP` | EUR/kW | 592.6 | 711.1 |
| `micro CHP` | EUR/kW_th | 7841.7 | 9410.1 |
| `central water tank storage` | EUR/kWh | 0.576 | 0.691 |

---

## How to Modify the Cost Parameters

### Step 1: Find the correct technology name

Technology names must exactly match the `technology` column in
`data/costs_<year>.csv`, which in turn comes from
[technology-data v0.9.0](https://github.com/PyPSA/technology-data/blob/v0.9.0/outputs/).

### Step 2: Edit the scenario config file

Add or update the technology under `costs.investment` in
`config/config.agora.yaml` (base config, applies to all scenarios) or in a
scenario-specific file to override only for that scenario. Units depend on
the technology — check the `unit` column in the costs CSV first.

```yaml title="config/config.agora.yaml or config/scenarios/config.*.yaml"
costs:
  investment:
    2020:
      HVDC overhead: 2000.0        # EUR/MW/km — IEA 2023
      HVDC submarine: 2000.0       # EUR/MW/km
      HVAC overhead: 500.0         # EUR/MW/km
      electrolysis: 1260.0         # EUR/kW_e — IEA Global Hydrogen Review 2023
      CO2 pipeline: 13000.0        # EUR/(tCO2/h)/km — Danish Energy Agency
      CO2 submarine pipeline: 33000.0  # EUR/(tCO2/h)/km — Danish Energy Agency
    2025:
      HVDC overhead: 2000.0
      ...
```
