# Parameters & Configuration

The table below shows at a glance where each type of assumption is adjusted.

| Parameter | Change location |
|---|---|
| Investment costs | `config/config.agora.yaml` or scenario override under `costs.investment` |
| Transmission efficiency / losses | `config/config.agora.yaml` under `sector.transmission_efficiency` |
| Powerplant lifetimes | `data/powerplant_lifetime.csv` (data file) |
| Time segmentation | scenario config — `sector_opts` wildcard (e.g. `2190SEG-T-H-B-I-A`) |

---

## Finding the right technology name for cost overrides

Technology names must exactly match the `technology` column in:

```
data/costs_<planning_horizon>.csv   # e.g. data/costs_2030.csv
```

This file is derived from
[technology-data v0.9.0](https://github.com/PyPSA/technology-data/blob/v0.9.0/outputs/).
Browse it to find the exact string to use as a key under
`costs.investment.<year>` in the config.
