# Powerplant Lifetimes

## Overview

Standard powerplantmatching data does not always reflect country-specific
or plant-specific decommissioning decisions. This model updates powerplant
lifetimes based on a custom CSV, incorporating data from:

- [Beyond Fossil Fuels](https://beyondfossilfuels.org)
- Reuters
- [Forum Energii](https://forum-energii.eu) (2024)

---

## Snakemake Rule

**Rule:** `build_powerplants`  
**Script:** `scripts/build_powerplants.py`  
**Data file:** `data/powerplant_lifetime.csv`

---

## How It Works

The `build_powerplants` rule retrieves the standard powerplant database from
[powerplantmatching](https://github.com/FRESNA/powerplantmatching) and then
calls `manipulate_lifetimes()` to apply corrections from the custom CSV:

```python title="scripts/build_powerplants.py"
ppl = manipulate_lifetimes(ppl, snakemake.input.new_ppl_lifetimes)
```

The function handles four cases based on the `Name` and `status` columns:

```python title="scripts/build_powerplants.py"
def manipulate_lifetimes(ppl_lifetime, path_lifetimes):
    lifetime_data = pd.read_csv(path_lifetimes)

    # Four adjustment categories:
    ppl_specific_lifetimes_limit  = lifetime_data.query("(Name!='all') & (status=='limit')")
    country_level_lifetimes_limit = lifetime_data.query("(Name=='all') & (status=='limit')")
    ppl_specific_lifetimes_ext    = lifetime_data.query("(Name!='all') & (status=='extend')")
    country_level_lifetimes_ext   = lifetime_data.query("(Name=='all') & (status=='extend')")

    # For 'limit': replace DateOut only if the new date is *earlier* than the existing one
    # For 'extend': replace DateOut only if the new date is *later* than the existing one
    # Applied first at country level, then at individual plant level
```

Adjustments are applied at two levels:

- **Country-level** (`Name == 'all'`): All plants of a given fuel type in a
  country get their `DateOut` updated (e.g. coal phase-out in Germany by 2030)
- **Plant-level** (`Name != 'all'`): Individual plants receive specific
  retirement years based on confirmed announcements

The logic is conservative: a `limit` entry only takes effect if the plant
would have lived *longer* than specified; an `extend` entry only takes effect
if the plant would have retired *earlier* than specified.

---

## Data Format

`data/powerplant_lifetime.csv` columns (in order):

| Column | Description |
|---|---|
| `Country` | ISO2 country code |
| `Fueltype` | e.g. `Lignite`, `Hard Coal`, `Nuclear` |
| `DateOut` | Target retirement year |
| `Name` | Plant name for plant-level rules; `all` for country-level rules |
| `status` | `limit` (force earlier retirement) or `extend` (force later retirement) |
| `Reference` | Data source citation |

---

## Current Data in `powerplant_lifetime.csv`

### Coal / Lignite Phase-outs (country-level `limit`)

All entries use `Name = all` and `status = limit`, sourced from
[Beyond Fossil Fuels](https://beyondfossilfuels.org/europes-coal-exit/)
except Poland which uses Forum Energii (25.11.2024):

| Country | Fueltype | DateOut |
|---|---|---|
| PL | Lignite + Hard Coal | 2044 |
| DE | Lignite + Hard Coal | 2038 |
| BG | Lignite + Hard Coal | 2038 |
| HR, CZ, SI | Lignite + Hard Coal | 2033 |
| ME | Lignite + Hard Coal | 2035 |
| RO | Lignite + Hard Coal | 2032 |
| MK | Lignite + Hard Coal | 2030 |
| NL, FI | Lignite + Hard Coal | 2029 |
| DK | Lignite + Hard Coal | 2028 |
| FR, HU, IT | Lignite + Hard Coal | 2027 |
| GR | Lignite + Hard Coal | 2026 |
| ES, IE | Lignite + Hard Coal | 2025 |
| SK | Lignite + Hard Coal | 2024 |
| GB | Lignite + Hard Coal | 2024 |
| PT | Lignite + Hard Coal | 2021 |
| AT, SE | Lignite + Hard Coal | 2020 |
| BE | Lignite + Hard Coal | 2016 |

### Nuclear Lifetime Extensions (plant-level `extend`)

French plants extended per Macron's 2022 announcement (Reuters), Belgian
reactors extended per the 2023 Engie agreement (Reuters):

| Country | Plant | DateOut |
|---|---|---|
| FR | Civaux | 2057 |
| FR | Nogent, Belleville | 2047 |
| FR | Golfech, Penly | 2050 |
| FR | St Alban, Flamanville | 2045 |
| FR | Cruas | 2043 |
| FR | Paluel | 2044 |
| FR | Cattenom | 2038 |
| FR | Blayais, Gravelines, Dampierre | 2040–2041 |
| FR | Chooz | 2027 |
| FR | Bugey | 2032 |
| FR | Chinon | 2023 |
| BE | Doel, Tihange | 2035 |

---

## How to Modify

### Limit a country-wide fuel type (phase-out)

Set `Name` to `all` and `status` to `limit`. All plants of that fuel type
in that country will retire no later than `DateOut`:

```csv
Country,Fueltype,DateOut,Name,status,Reference
DE,Lignite,2030,all,limit,custom
PL,Hard Coal,2040,all,limit,custom
```

### Extend a country-wide fuel type (lifetime extension)

```csv
Country,Fueltype,DateOut,Name,status,Reference
CZ,Nuclear,2050,all,extend,custom
```

### Override a specific plant

Use the exact plant name as it appears in the powerplantmatching database:

```csv
Country,Fueltype,DateOut,Name,status,Reference
PL,Lignite,2036,Bełchatów,limit,custom
CZ,Nuclear,2050,Dukovany,extend,custom
```

### Disable lifetime corrections entirely

Leave the `new_ppl_lifetimes` input empty in the Snakemake config (the
function returns the original dataframe unchanged if no path is provided).
