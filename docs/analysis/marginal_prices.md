# Marginal Prices

## Overview

Nodal marginal prices are extracted from the optimised networks for selected
bus carriers across all scenarios and planning years. Results are written to
Excel files, one per carrier.

**Script:** `scripts_analysis/marginal_prices.py`  
**Function:** `get_marginal_prices()`  
**Output:** `marginal_prices/`

---

## Carriers

| Carrier | Bus type | Output label |
|---|---|---|
| `AC` | High-voltage electricity buses | `electricity` |
| `H2` | Hydrogen buses | `hydrogen` |

The default carrier list is `["AC", "H2"]`. It can be changed by passing a
custom `carriers` argument to `get_marginal_prices()`.

---

## Output Files

| File | Description |
|---|---|
| `marginal_prices_electricity.xlsx` | Nodal electricity marginal prices, one sheet per bus |
| `marginal_prices_hydrogen.xlsx` | Nodal hydrogen marginal prices, one sheet per bus |

Each Excel file contains one sheet per bus node. Within each sheet, rows are
time steps and columns form a `MultiIndex(scenario, year)`.

---

## How It Works

`get_marginal_prices()` calls two internal functions:

### `extract_marginal_prices()`

Reads `network.buses_t.marginal_price` for each `(scenario, year)` pair and
accumulates one narrow DataFrame per bus. Missing buses in a given network
become `NaN` rather than raising an error.

```python
mp = n.buses_t.marginal_price.reindex(columns=buses)
```

The result is a nested dict `{carrier: {bus: DataFrame}}` where each
DataFrame has `MultiIndex(scenario, year)` columns and time steps as the
index.

### `write_marginal_prices()`

Writes the per-bus DataFrames to Excel, with each bus as a separate sheet:

```python
for bus, df in prices[carrier].items():
    df.to_excel(writer, sheet_name=str(bus))
```

---

## Configuration

`get_marginal_prices()` is called from `analysis_main.py`. The carriers and
result directory are controlled there:

```python
get_marginal_prices(
    networks_year=networks,
    years=years,
    scenarios=scenarios,
    scenario_colors=scenario_colors,
    resultdir=marginal_prices_dir,
    carriers=["AC", "H2"],  # default
)
```
