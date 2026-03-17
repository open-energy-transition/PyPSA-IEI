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

---

## Country Scopes

Three country lists are defined in `analysis_main.py`:

| Variable | Count | Countries | Used for |
|---|---|---|---|
| `countries` | 33 | EU + NO, GB, CH, Western Balkans | Full model scope |
| `eu27_countries` | 25 | EU27 excl. Malta, Cyprus | Network maps |
| `th_countries` | 26 | TransHyDE project countries | Import analysis |
