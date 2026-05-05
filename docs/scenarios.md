# Scenario Framework

This page describes the four main scenarios analyzed in the PyPSA-IEI study. Each scenario represents a distinct policy pathway for European energy infrastructure development, defined by two key dimensions:

1. **Infrastructure planning approach**: Cross-sectoral vs. Sectoral silos
2. **Policy perspective**: European view vs. National view

---

## Policy Dimensions

### Dimension 1: Cross-Sectoral vs. Sectoral View

Infrastructure planning can be approached either through **integrated cross-sectoral planning** or through planning in **sectoral silos**.

#### Cross-Sectoral View

Infrastructure planning considers the interaction between sectors (electricity, natural gas, hydrogen) in a consistent, harmonised way. This enables:

- Integrated, cost-optimal grid expansion across all energy carriers
- Efficient sector-coupling approaches
- Minimization of system-wide costs
- Avoidance of grid bottlenecks and overcapacities

??? details "Implementation Details"

    The existing grid and already advanced TYNDP projects (i.e., with status "in construction" for electricity, "FID" for gas) form the lower boundary for endogenous transmission capacity expansions. The optimization model can freely expand transmission capacities for electricity, gas, hydrogen, and CO₂ networks beyond these baseline projects.

    For detailed project lists, see Annex 2 in the [published report](https://www.ieg.fraunhofer.de/content/dam/ieg/englisch/documents/20251008_Report_IEI_AgoraEnergiewende_Fraunhofer_dfine_final_updates_November2025.pdf).

#### Sectoral View (Silos)

Infrastructure planning treats energy networks largely independently, with electricity, natural gas, and hydrogen networks planned separately. This reflects current practices like the TYNDP process, but involves risks:

- Unnecessarily high energy system costs
- Potential grid bottlenecks
- Overcapacities in technologies and infrastructure
- Lack of coordination between energy carriers

??? details "Implementation Details"

    The existing grid and all sectoral infrastructure projects (TYNDP, H2 Infrastructure Map, and German Hydrogen Core Network) are the only capacity expansions permitted in the system **until 2040**. This reflects network capacity expansion as envisioned by grid planners. After 2040, the optimization model can freely expand transmission capacities.

    For electricity networks, this includes less advanced TYNDP projects with maturity status "in permitting" and "under consideration". For complete project listings, see Annex 2 in the [published report](https://www.ieg.fraunhofer.de/content/dam/ieg/englisch/documents/20251008_Report_IEI_AgoraEnergiewende_Fraunhofer_dfine_final_updates_November2025.pdf).

---

### Dimension 2: European vs. National View

The second dimension reflects the tension between European internal market integration and national protectionist tendencies.

#### European View

The European internal market paradigm supports free trade and optimal resource allocation across borders. The model:

- Can freely optimize the share of imported versus domestically generated electricity and hydrogen
- Maximizes system-wide efficiency
- Leverages regional comparative advantages
- No self-sufficiency constraints are activated

??? details "Implementation Details"

    Self-sufficiency constraints are **not activated**. The system freely optimizes imports and exports on both hourly and annual basis to minimize total system costs.

#### National View

National perspectives prioritize minimizing energy import dependencies (even from within the EU) by expanding domestic generation and storage capacities. Motivations include:

- Energy security concerns
- Keeping domestic electricity prices low
- Avoiding political dependencies
- National self-determination

This approach can lead to:

- Unnecessarily high system costs
- Excess regional capacities despite sub-optimal generation conditions
- Underutilization of low-cost generation potentials in other countries

??? details "Implementation Details"

    Self-sufficiency constraints are **activated** to require high shares of domestic generation for each country. These constraints operate on an **annual basis** (hourly imports/exports remain unrestricted).

    For detailed constraint formulation, see [Self-Sufficiency Constraints](functionality/self_sufficiency.md) or Annex 1 in the [published report](https://www.ieg.fraunhofer.de/content/dam/ieg/englisch/documents/20251008_Report_IEI_AgoraEnergiewende_Fraunhofer_dfine_final_updates_November2025.pdf).

    **Parameterization:**

    | Year | Electricity Min. National Generation | Hydrogen Min. National Generation | Export Capacity Buffer |
    |------|-------------------------------------|----------------------------------|----------------------|
    | 2030 | 80% | 70% | +10% of demand |
    | 2050 | 100% | 70% | +10% of demand |

    - Electricity self-sufficiency increases linearly from 80% (2030) to 100% (2050)
    - Hydrogen self-sufficiency remains constant at 70%
    - Countries must build sufficient capacity to export 10% of their electricity/hydrogen demand

---

## The Four Main Scenarios

<table>
<thead>
<tr>
<th></th>
<th><strong>European View</strong><br/>(no self-sufficiency constraints)</th>
<th><strong>National View</strong><br/>(with self-sufficiency constraints)</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>Cross-Sectoral</strong><br/>(free grid expansion)</td>
<td>
<strong>CE</strong><br/>
<em>Cross-sectoral, European</em><br/>
Cost-optimal integrated planning
</td>
<td>
<strong>CN</strong><br/>
<em>Cross-sectoral, National</em><br/>
Integrated planning with self-sufficiency
</td>
</tr>
<tr>
<td><strong>Sectoral</strong><br/>(fixed grid expansion until 2040)</td>
<td>
<strong>SE</strong><br/>
<em>Sectoral, European</em><br/>
Sectoral planning with free trade
</td>
<td>
<strong>SN</strong><br/>
<em>Sectoral, National</em><br/>
Sectoral planning with self-sufficiency
</td>
</tr>
</tbody>
</table>

---

## Detailed Scenario Descriptions

### CE Scenario (Cross-sectoral, European view)

**Configuration file:** `config/scenarios/config.CE.yaml`

The **CE scenario** represents fully integrated, cost-optimal European energy infrastructure planning. This scenario serves as the **cost-optimal benchmark** against which other scenarios are compared.

??? details "View Characteristics"

    - ✅ **Free transmission expansion** for all sectors (electricity, gas, hydrogen, CO₂)
    - ✅ **No self-sufficiency constraints**
    - ✅ Existing grid + advanced TYNDP projects form the lower bound
    - ✅ Free optimization of import vs. domestic generation shares

??? details "View Expected Outcomes"

    - Cost-optimal generation, storage, and sectorally-integrated grid expansion
    - Maximum utilization of regional comparative advantages
    - Lowest system-wide costs
    - High cross-border energy flows where economically efficient
    - Achievement of climate neutrality by 2050 at minimal cost

---

### CN Scenario (Cross-sectoral, National view)

**Configuration file:** `config/scenarios/config.CN.yaml`

The **CN scenario** combines integrated infrastructure planning with national self-sufficiency objectives. This scenario explores the **cost of energy sovereignty** within an otherwise optimally integrated system.

??? details "View Characteristics"

    - ✅ **Free transmission expansion** for all sectors (electricity, gas, hydrogen, CO₂)
    - ⚠️ **Self-sufficiency constraints activated**
    - ✅ Existing grid + advanced TYNDP projects form the lower bound
    - ⚠️ High share of domestic generation required (80-100% electricity, 70% hydrogen)

??? details "View Expected Outcomes"

    - Sectorally-integrated grid expansion within national constraints
    - High level of national energy supply
    - Low import dependence (including intra-European)
    - Higher domestic generation and storage capacities
    - Increased system costs compared to CE due to sub-optimal resource allocation
    - Underutilization of cross-border transmission despite available capacity

---

### SE Scenario (Sectoral, European view)

**Configuration file:** `config/scenarios/config.SE.yaml`

The **SE scenario** reflects current infrastructure planning practices (e.g., TYNDP) with European market integration. This scenario evaluates the **cost of sectoral planning** under current institutional frameworks.

??? details "View Characteristics"

    - ⚠️ **Fixed transmission expansion until 2040** based on:
        - TYNDP electricity projects (including "in permitting" and "under consideration")
        - TYNDP gas projects
        - H2 Infrastructure Map
        - German Hydrogen Core Network
    - ✅ **No self-sufficiency constraints**
    - ✅ Free optimization of import vs. domestic generation shares
    - ✅ Free transmission expansion after 2040

??? details "View Expected Outcomes"

    - Good EU-wide coordination on trade and generation
    - Sub-optimal infrastructure due to sectoral planning silos
    - Networks may be insufficient or misaligned for integrated sector-coupling
    - Potential grid bottlenecks or stranded assets
    - Higher costs than CE due to lack of integrated infrastructure optimization
    - Increased reliance on generation and storage to compensate for grid constraints

---

### SN Scenario (Sectoral, National view)

**Configuration file:** `config/scenarios/config.SN.yaml`

The **SN scenario** represents the most constrained policy pathway, combining sectoral planning with national protectionism. This scenario represents the **worst-case policy pathway** where both infrastructure planning and trade policies work against system optimization.

??? details "View Characteristics"

    - ⚠️ **Fixed transmission expansion until 2040** (same as SE)
    - ⚠️ **Self-sufficiency constraints activated**
    - ⚠️ High share of domestic generation required (80-100% electricity, 70% hydrogen)
    - ⚠️ Limited cross-border coordination
    - ✅ Free transmission expansion after 2040

??? details "View Expected Outcomes"

    - Uncoordinated expansion of generation and grid infrastructure
    - Highest system costs among all scenarios
    - Significant overcapacities in some regions, bottlenecks in others
    - Sub-optimal use of renewable resources
    - Stranded assets due to fixed, uncoordinated network planning
    - Low cross-border energy flows despite physical interconnection

---

## Sensitivity Scenarios

In addition to the four main scenarios, several **sensitivity analyses** were conducted based on the CE scenario to test robustness:

| Scenario | Configuration File | Description |
|----------|-------------------|-------------|
| **CE (base)** | `config.CE.yaml` | Reference scenario |
| **CE - No Gas/Oil** | `config.CE_no_gas_no_oil.yaml` | Fossil gas and oil phase-out |
| **CE - Flexibility** | `config.CE_flexibility.yaml` | Limited flexibility options |
| **CE - Expensive Compensation** | `config.CE_expensive_compensation.yaml` | Higher balancing costs |
| **CE - TransHyDE S2** | `config.CE_TranshydeS2.yaml` | Alternative industrial demand profile |

---

## Running Scenarios

To execute a specific scenario, use Snakemake with the corresponding configuration file:

```bash
snakemake -call all --configfile config/scenarios/config.CE.yaml
```

Replace `config.CE.yaml` with the desired scenario configuration file.

For detailed execution instructions, see the [Installation](installation.md) page.

---

## Key Differences Summary

| Feature | CE | CN | SE | SN |
|---------|----|----|----|----|
| Grid expansion (until 2040) | Free | Free | Fixed (TYNDP) | Fixed (TYNDP) |
| Grid expansion (after 2040) | Free | Free | Free | Free |
| Self-sufficiency constraints | ❌ No | ✅ Yes | ❌ No | ✅ Yes |
| Cross-border optimization | Full | Limited | Full | Limited |
| Expected system cost | Lowest | Medium-low | Medium-high | Highest |
| Infrastructure planning | Integrated | Integrated | Sectoral silos | Sectoral silos |
| Trade policy | European market | National focus | European market | National focus |

---

## Related Documentation

- [Self-Sufficiency Constraints](functionality/self_sufficiency.md) — Technical implementation details
- [TYNDP Electricity Projects](functionality/electricity.md) — Fixed electricity network projects
- [Gas Networks](functionality/gas.md) — TYNDP gas pipeline implementation
- [Hydrogen Networks](functionality/hydrogen.md) — H2 Infrastructure Map and Core Network
- [Expansion Limits](functionality/expansion.md) — Constraints on capacity expansion

---

## References

For comprehensive methodology and results analysis, please refer to:

> *"Integrated Infrastructure Planning and 2050 Climate Neutrality: Deriving Future-Proof European Energy Infrastructures"*
> Fraunhofer IEG, Fraunhofer ISI, and d-fine (November 2025)
> [Download report (PDF)](https://www.ieg.fraunhofer.de/content/dam/ieg/englisch/documents/20251008_Report_IEI_AgoraEnergiewende_Fraunhofer_dfine_final_updates_November2025.pdf)
