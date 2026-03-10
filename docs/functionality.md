# Extra Model Functionality

This page summarizes the key extensions and modifications made to the
[PyPSA-Eur](https://github.com/PyPSA/pypsa-eur) base model for the
PyPSA-IEI study.

---

## Costs

The model uses mainly the cost assumptions from
[technology-data v0.9.0](https://github.com/PyPSA/technology-data).
However, some technology costs are taken from `config/config.agora.yaml`.

The following investment costs are read from configuration files and updated
in cost files by the `update_costs_csv` rule for **all scenarios**:

- HVDC overhead
- HVDC submarine
- HVAC overhead
- Electrolysis
- CO₂ pipeline
- CO₂ submarine pipeline

For the **CE flexibility scenario**, the following additional investment costs
are also updated from the config:

- Central and decentral air-sourced heat pumps
- Central and decentral ground-sourced heat pumps
- Central solid biomass CHP
- Central gas CHP
- Micro CHP
- Biomass CHP capture
- Central and decentral water tank storage
- Central and decentral resistive heater

---

## Lifetimes

Powerplant lifetimes are updated based on `data/powerplant_lifetime.csv`
within the `build_powerplants` rule. Lifetimes are adjusted at both
**country-level** and **powerplant-level**, based on data from:

- Beyond Fossil Fuels
- Reuters
- Forum Energii (2024)

---

## Gas

- **Russian gas imports** are removed in all scenarios in the
  `build_gas_input_locations` rule.
- **TYNDP gas pipeline** project data is processed and mapped to cluster
  regions in the custom rule `build_tyndp_gas_pipes`.
- TYNDP-based gas pipelines are attached to the model in
  `prepare_sector_network` for all scenarios:

| Scenario type | TYNDP projects included |
|---|---|
| Cross-sectoral | Final Investment Decision (FID) only |
| Sectoral | FID, advanced, and less-advanced |

---

## Hydrogen

The hydrogen network is modelled in the **SN** and **SE** scenarios using
the `build_wasserstoff_kernnetz` and `cluster_wasserstoff_kernnetz` rules
(adapted from [PyPSA-Ariadne](https://github.com/PyPSA/pypsa-ariadne)).

**Data sources:**

- Germany-specific hydrogen network: [FNB-Gas](https://www.fnb-gas.de)
- European hydrogen infrastructure map: [ENTSO-G](https://www.entsog.eu)

Both datasets are merged to obtain the full hydrogen network, with duplicate
entries removed to prevent double counting.

**Key features:**

- Hydrogen retrofitting from the gas network is enabled
- New hydrogen pipeline construction is allowed
- Hydrogen pipeline data is integrated in the `modify_prenetwork` rule
- Gas pipeline capacity and H₂ retrofitting potential are reduced by the
  added hydrogen pipeline capacity to account for retrofitting

---

## Industrial Energy Demand

Industry demand data is updated based on
[TransHyDe](https://www.transhyde.eu) data within the
`build_industrial_energy_demand_per_node` rule:

- Demands are scaled and missing data are filled using TransHyDe data
- **All scenarios** use TransHyDe Scenario 1.5, except
  `config.CE_TranshydeS2.yaml` which uses Scenario 2
- Functionality to adjust industrial energy demands for **ammonia and
  methanol imports** is included (no imports are considered in the current
  study)

**Hydrogen demand distribution** is derived from high-temperature industrial
processes (smelting and furnaces). Their energy consumption is assigned to
hydrogen as the carrier (instead of electricity or methane) in
`build_industry_sector_ratios`, reflecting an assumption of high industrial
decarbonization. These ratios determine the **spatial distribution** of
demand across nodes within a country, while absolute country-level totals
are overwritten in `build_industrial_energy_demand_per_node` with actual
TransHyDE data.

---

## Imports

Energy imports are added as **extendable generators** (and supporting
buses/links where needed) in the `prepare_sector_network` rule, covering
5 import technologies read from a CSV file:

| Technology | Type |
|---|---|
| Hydrogen | Pipeline |
| Hydrogen | Shipping |
| Syngas | Pipeline |
| Syngas | Shipping |
| Synfuel | Shipping |

Each import is extendable with maximum capacity provided by the CSV.
Syngas/synfuel links assign **negative efficiency on the CO₂ atmosphere bus**
to cancel out emissions when the synthetic fuel is eventually consumed.

!!! note
    The majority of import data is taken from the TransHyDe report.

---

## Losses

Transmission losses are set for the following components in
`prepare_sector_network`:

- DC links
- H₂ pipelines
- Gas pipelines
- Low voltage electricity distribution grid

---

## Electricity Network

TYNDP electricity infrastructure policy is enforced on the already-built
network in `prepare_sector_network`. Capacity limits for TYNDP-based lines
and links are enforced based on:

- `data/lines_2020-2050.csv`
- `data/links_2020-2050.csv`

for each planning horizon.

| Scenario type | TYNDP projects | Cross-border extendability |
|---|---|---|
| Cross-sectoral | Under construction only | All horizons |
| Sectoral | Planning, permitting & under construction | After 2040 |

---

## Myopic Optimization

The `add_brownfield` rule handles capacity accounting between planning
horizons:

- **Gas pipelines**: Current capacities are reduced by already-retrofitted
  capacity from the previous horizon (when H₂ retrofit is enabled)
- **Non-European gas import pipelines**: Gas pipeline capacity and H₂
  retrofit potential are reduced by already-retrofitted amounts
- **LNG import terminals**: Same retrofitting logic applied for terminals
  being converted to H₂ shipping terminals
- **New powerplants**: A base powerplant network is loaded and newly
  commissioned assets (`Generator` and `Link` types) coming online between
  the previous and current planning year are added

---

## Expansion Limits

Minimum and maximum capacity constraints (in MW) for renewable energy and
other carriers are set across European countries for multiple planning years
(2020–2050):

| Carrier | Component | Scope |
|---|---|---|
| `solar` | Generator | All European countries separately |
| `onwind` | Generator | All European countries separately |
| `offwind` | Generator | All European countries separately |
| `H2 Electrolysis` | Link | European-wide (`Eur`) + Romania separately |
| `gas for electricity` | Link | Poland, Romania |
| `co2 sequestered` | Store | Romania only |

**Constraint characteristics by planning year:**

| Period | Constraints |
|---|---|
| 2020/2025 | Only `max` set — interpolated from existing capacities toward 2030 targets |
| 2030 | Both `min` and `max` — based on NECPs, Agora, Ember, Forum Energii |
| 2035–2045 | Interpolated between 2030 and 2050 values |
| 2050 | Based on technical potentials from Atlite or national studies |

---

## Allam Cycle Gas Turbines

The Allam cycle gas turbine is a technology with **100% CO₂ capture
potential**, modelled with the following techno-economic assumptions:

| Parameter | Value |
|---|---|
| Investment cost | 1,500 EUR/kW |
| Efficiency | 60% |
| Lifetime | 30 years |
| Marginal cost | 2.0 EUR/MWh_th (3.33 EUR/MWh_el) |
| Fuel (gas) cost | ~24.5 EUR/MWh_th |
| CO₂ intensity of gas | 0.198 tCO₂/MWh_th |

**Energy flow:**

- **Input**: Natural gas
- **Output**: Electricity
- **CO₂**: Fully captured and stored
