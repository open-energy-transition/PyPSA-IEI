<!--
SPDX-FileCopyrightText: Open Energy Transition GmbH and contributors
SPDX-License-Identifier: MIT
-->

# Hydrogen Generation

## Overview

Annual H₂ production volumes and full-load hours are extracted from the
optimised networks per technology, bus node, scenario, and planning year.
Results are written to a single Excel file with one sheet per H₂ bus.

**Script:** `scripts_analysis/h2_generation.py`  
**Function:** `analyze_h2_generation()`  
**Output:** `h2_generation/`

---

## Technologies

| Technology | Description |
|---|---|
| `H2 Electrolysis` | Water electrolysis driven by electricity |
| `SMR` | Steam methane reforming (without carbon capture) |
| `SMR CC` | Steam methane reforming with carbon capture |

---

## Output Files

| File | Description |
|---|---|
| `hydrogen_generation.xlsx` | H₂ generation and full-load hours per node, one sheet per H₂ bus |

Each sheet corresponds to one H₂ bus node (suffix ` H2` stripped from the
sheet name). Rows follow this order:

| Row group | Rows |
|---|---|
| H₂ generation [GWh_H2] | `H2 Electrolysis`, `SMR`, `SMR CC`, `Total` |
| Full-load hours [h/a] | `H2 Electrolysis`, `SMR`, `SMR CC` |

Columns form a `MultiIndex(scenario, year)`.

---

## How It Works

`analyze_h2_generation()` calls two internal functions:

### `extract_h2_metrics()`

Uses `n.statistics.energy_balance()` to obtain annually-weighted H₂
generation for each technology at each H₂ bus (supply side only, positive
values):

```python
eb = n.statistics.energy_balance(aggregate_bus=False)
s = eb.loc[pd.IndexSlice[:, carrier, :]]
s = s[s.index.get_level_values(-1).isin(h2_buses)]
s = s[s > 0].groupby(level=-1).sum()
```

Full-load hours per technology are computed as annual generation divided by
optimised H₂ output capacity (taking into account link efficiency):

```python
cap = (links.p_nom_opt * links.efficiency).groupby(links["bus1"]).sum()
flh = (gen / cap.replace(0, float("nan"))).round(1)
```

The result is a DataFrame with `MultiIndex(metric, technology, node)` as the
index and `MultiIndex(scenario, year)` as columns.

### `write_h2_metrics()`

Writes the metrics to Excel, one sheet per H₂ bus node, with rows reindexed
to the canonical display order:

```python
row_order = [H2 generation per technology, Total, FLH per technology]
node_df.to_excel(writer, sheet_name=str(node).removesuffix(" H2"))
```

---

## Configuration

`analyze_h2_generation()` is called from `analysis_main.py`:

```python
analyze_h2_generation(
    networks=networks,
    years=years,
    scenarios=scenarios,
    resultdir=h2_gen_dir,
)
```
