# Post-Analysis Overview

The post-analysis scripts are located in `scripts_analysis/` and are run
**after** the PyPSA optimization is complete. The master script
`analysis_main.py` orchestrates all analyses and produces plots and Excel
files organized into timestamped output folders.

---

## How to Run

```bash
cd scripts_analysis
python analysis_main.py
```

The script must be run from inside `scripts_analysis/` — `main_dir` is
resolved automatically as the parent of the current working directory.

---

## Output Structure

```
analysis_results_YYYYMMDD/
  ExogenousDemand/      ← transport demand plots
  Balances/             ← energy balance charts per carrier
  network_plots/        ← transmission network maps
  KPIs/                 ← installed capacity, GWkm, dispatch, summary KPIs
  self-sufficiency/     ← regional energy self-sufficiency
  costs/                ← total system cost breakdown
  utilization/          ← transmission line utilization
  Import/               ← energy import volumes and costs
  balance_maps/         ← spatial energy balance maps
  marginal_prices/      ← nodal marginal prices per carrier
  h2_generation/        ← H₂ production volumes and full-load hours
  grid_emission_factors/ ← hourly CO₂ emission factors per AC node
```

---

## Toggling Analyses On/Off

Near the top of `analysis_main.py` there is a dictionary called `executed_analysis`.
Each key corresponds to one analysis group, and its boolean value controls whether
that group runs. Set a value to `False` to skip it entirely — useful when you only
want to regenerate a subset of outputs or when iterating quickly on a single module.

```python
executed_analysis = {
    "Exogenous demand":             True,   # transport demand plots
    "Marginal prices":              True,   # nodal marginal price charts
    "H2 generation & full-load hours": True, # H₂ production & FLH
    "Grid emission factors":        True,   # hourly CO₂ emission factors
    "Energy balances":              True,   # energy balance charts
    "Network plots":                True,   # transmission network maps
    "KPIs":                         True,   # capacity, GWkm, dispatch, summary KPIs
    "Self-sufficiency":             True,   # regional self-sufficiency
    "System costs":                 True,   # total system cost breakdown
    "Utilization":                  True,   # line utilization
    "Import":                       True,   # import volumes & costs
    "Balance maps":                 True,   # spatial energy balance maps
}
```

---

## Analysis Modules

| Output folder | Script | Function |
|---|---|---|
| `ExogenousDemand/` | `exogenous_demand_analyses.py` | `get_transport_demand_plot()` |
| `Balances/` | `configurable_energy_balances.py` | `get_standard_balances()` |
| `network_plots/` | `plot_elec_network.py` | `plot_map_elec_years()` |
| `network_plots/` | `plot_h2_network.py` | `plot_h2_map_years()` |
| `network_plots/` | `plot_co2_network.py` | `plot_co2_map_years()` |
| `network_plots/` | `plot_ch4_network.py` | `plot_ch4_map_years()` |
| `network_plots/` | `compare_grids.py` | `plot_grid_comparisons()` |
| `KPIs/` | `installed_capacity.py` | `call_installed_capacity_plot()` |
| `KPIs/` | `plot_GWkm.py` | `plot_TWkm_all_carriers()` |
| `KPIs/` | `summary_KPIs.py` | `start_KPI_analysis()` |
| `KPIs/` | `plot_cases_KPIs.py` | `plot_case_study_KPIs()` |
| `KPIs/` | `plot_dispatch_barchart.py` | `plot_dispatch_barchart()` |
| `self-sufficiency/` | `regional_self_sufficiency_level.py` | `evaluate_self_sufficiency()` |
| `costs/` | `analyze_total_system_cost.py` | `analyze_system_cost()` |
| `utilization/` | `line_usage.py` | `evaluate_line_usage()` |
| `Import/` | `import_analysis.py` | `analyze_imports()` |
| `balance_maps/` | `plot_balance_map.py` | `plot_balance_map_years()` |
| `marginal_prices/` | `marginal_prices.py` | `get_marginal_prices()` |
| `h2_generation/` | `h2_generation.py` | `analyze_h2_generation()` |
| `grid_emission_factors/` | `grid_emission_factors.py` | `analyze_grid_emission_factors()` |

---

## Country Scopes

Three country lists are defined in `analysis_main.py`:

| Variable | Count | Countries | Used for |
|---|---|---|---|
| `countries` | 33 | EU + NO, GB, CH, Western Balkans | Full model scope |
| `eu27_countries` | 25 | EU27 excl. Malta, Cyprus | Network maps |
| `th_countries` | 26 | TransHyDE project countries | Import analysis |
