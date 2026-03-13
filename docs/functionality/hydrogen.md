# Hydrogen Network

## Overview

The hydrogen network is modelled in the **SN** and **SE** scenarios. It
combines the German *Wasserstoffkernnetz* ([FNB-Gas](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Wasserstoff/Kernnetz/start.html))
with the European [hydrogen infrastructure map](https://www.h2inframap.eu/), enabling both
retrofitting of existing gas pipelines and construction of new H₂ pipelines.

The scripts are adapted from [PyPSA-Ariadne](https://github.com/PyPSA/pypsa-ariadne).

---

## Snakemake Rules

| Rule | Script | Purpose |
|---|---|---|
| `build_wasserstoff_kernnetz` | `scripts/build_wasserstoff_kernnetz.py` | Process and merge FNB-Gas + ENTSO-G data |
| `cluster_wasserstoff_kernnetz` | `scripts/cluster_wasserstoff_kernnetz.py` | Map H₂ network to model clusters |
| `modify_prenetwork` | `scripts/modify_prenetwork.py` | Integrate H₂ pipelines into the network |

---

## Data Sources

| Source | File | Geographic scope |
|---|---|---|
| [FNB-Gas](https://fnb-gas.de/) | `Anlage2_Leitungsmeldungen_...xlsx` — pipeline submissions from potential operators | Germany |
| [FNB-Gas](https://fnb-gas.de/) | `Anlage3_FNB_Massnahmenliste_...xlsx` — FNB measure list (retrofit + new build) | Germany |
| ENTSO-G | `data/wasserstoff_kernnetz/h2_inframap_entsog.geojson` | Europe |

The two FNB-Gas files are downloaded automatically by Snakemake at runtime from
[fnb-gas.de](https://fnb-gas.de/wp-content/uploads/2023/11/). Both datasets are
merged in `cluster_wasserstoff_kernnetz`. Duplicate entries between the two
sources are removed to prevent double-counting of pipeline capacities.

---

## Pipe Capacity Calculation

H₂ pipe capacity is estimated from pipe diameter using piecewise linear
interpolation across three reference points:

```python title="scripts/build_wasserstoff_kernnetz.py"
def diameter_to_capacity_h2(pipe_diameter_mm):
    """
    20 inch (500 mm)  50 bar ->  1.2 GW H2 (LHV)
    36 inch (900 mm)  50 bar ->  4.7 GW H2 (LHV)
    48 inch (1200 mm) 80 bar -> 16.9 GW H2 (LHV)
    """
    m0 = (1200 - 0) / (500 - 0)
    m1 = (4700 - 1200) / (900 - 500)
    m2 = (16900 - 4700) / (1200 - 900)

    if pipe_diameter_mm < 500:
        return m0 * pipe_diameter_mm
    elif pipe_diameter_mm < 900:
        return m1 * pipe_diameter_mm + (1200 - m1 * 500)
    else:
        return m2 * pipe_diameter_mm + (4700 - m2 * 900)
```

For retrofitted pipes, the displaced gas capacity is also tracked using
`diameter_to_capacity` (from `build_gas_network.py`) to reduce the gas
network capacity accordingly.

---

## Integration into the Network

H₂ pipeline data is integrated into the network in the `modify_prenetwork`
rule via `add_wasserstoff_kernnetz()`. Only pipelines with `build_year` within
the current investment period are added. The function also:

- **Reduces gas pipeline capacity** (`p_nom`) on routes where kernnetz
  pipelines have been retrofitted from gas
- **Reduces H₂ retrofitting potential** (`p_nom_max` on H₂ pipeline
  retrofitted links) for all kernnetz pipelines built to date

```python title="scripts/modify_prenetwork.py"
# Reduce gas pipeline p_nom for retrofitted kernnetz pipes
gas_pipes = n.links.query("carrier == 'gas pipeline'")
res_gas_pipes = reduce_capacity(gas_pipes, add_reversed_pipes(wkn_to_date), carrier="gas")
n.links.loc[n.links.carrier == "gas pipeline", "p_nom"] = res_gas_pipes["p_nom"]

# Reduce H2 retrofitting potential for all kernnetz pipes built to date
res_h2_pipes_retrofitted = reduce_capacity(
    h2_pipes_retrofitted,
    add_reversed_pipes(wkn),
    carrier="H2",
    target_attr="p_nom_max",
    conversion_rate=snakemake.config["sector"]["H2_retrofit_capacity_per_CH4"],
)
```

---

## How to Modify the Hydrogen Network

### The Wasserstoffkernnetz 
The Wasserstoffkernnetz integration is controlled under `policy_plans` in the scenario config:

```yaml title="config/scenarios/config.SE.yaml"
policy_plans:
  wasserstoff_kernnetz:
    enable: true
    optimize_after: 2040  # pipelines are non-extendable until this year
```
### Gas-to-H₂
Pipeline retrofitting is controlled separately under `sector:`:

```yaml title="config/config.agora.yaml"
sector:
  H2_retrofit: true
  H2_retrofit_capacity_per_CH4: 0.6  # capacity ratio H2/CH4
```
