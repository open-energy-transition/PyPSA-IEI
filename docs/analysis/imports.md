# Import Analysis

## Overview

Energy import volumes (TWh) per import technology across planning years and
scenarios.

**Script:** `scripts_analysis/import_analysis.py`  
**Function:** `analyze_imports()`  
**Output:** `Import/`  

---

## Import Sets

Three sets of import carriers are evaluated independently:

| Set | Carriers |
|---|---|
| `H2_import` | H₂ pipeline, H₂ shipping |
| `H2_derivate_import` | H₂ pipeline, H₂ shipping, syngas pipeline, syngas shipping, synfuel |
| `energy_import` | All of the above + coal, oil, uranium, LNG gas, pipeline gas |

---

## Output Files

For each import set the following files are saved to `Import/`:

| File | Description |
|---|---|
| `plot_{scenario}_{set}.png` | Stacked bar chart per scenario across years |
| `plot_all_{set}.png` | Side-by-side comparison of all scenarios |
| `imports_{scenario}_TWh.xlsx` | Detailed time-series data per scenario |
