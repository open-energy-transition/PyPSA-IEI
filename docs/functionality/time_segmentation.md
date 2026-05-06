# Flexible Time Segmentation

## Overview

Full-year hourly time series (8760 snapshots) make sector-coupled optimisation
extremely slow. To keep solve times tractable, the model aggregates snapshots
into a smaller number of **representative segments** using the
[tsam](https://github.com/FZJ-IEK3-VSA/tsam) library.
The number of segments is controlled via the `sector_opts` wildcard (e.g.
`2190SEG`, `256SEG`) and can be changed freely for each run without touching
any script.

Two simpler alternatives also exist:

| Method | `sector_opts` example | Effect |
|---|---|---|
| Temporal segmentation (tsam) | `2190SEG` | Aggregate 8760 h → N representative segments |
| Hourly resampling | `4h` | Average every 4 hours → 2190 snapshots |
| No aggregation | _(no suffix)_ | Keep all hourly snapshots |

---

## Snakemake Rules

**Rule:** `time_aggregation` (in `rules/build_sector.smk`)  
**Script:** `scripts/time_aggregation.py`

This rule runs **before** `prepare_sector_network` and writes a CSV of snapshot
weightings. The sector-coupled network then reads that CSV and applies the aggregation.

**Rule:** `prepare_sector_network`  
**Script:** `scripts/prepare_sector_network.py` — function
`set_temporal_aggregation()`

---

## How It Works

### Step 1 — Compute snapshot weightings (`time_aggregation.py`)

All time-varying data is collected (generator profiles, load, heat demand,
solar thermal) and normalised to the unit interval. `tsam` then partitions the
8760-hour year into N contiguous segments, each described by a representative
hour and a duration weight:

```python title="scripts/time_aggregation.py"
agg = tsam.TimeSeriesAggregation(
    df,
    hoursPerPeriod=len(df),   # treat the whole year as one period
    noTypicalPeriods=1,
    noSegments=segments,       # e.g. 2190 or 256
    segmentation=True,
    solver=snakemake.params.solver_name,
)
agg = agg.createTypicalPeriods()

weightings = agg.index.get_level_values("Segment Duration")
offsets = np.insert(np.cumsum(weightings[:-1]), 0, 0)
snapshot_weightings = n.snapshot_weightings.loc[n.snapshots[offsets]].mul(
    weightings, axis=0
)
snapshot_weightings.to_csv(snakemake.output.snapshot_weightings)
```

The result is a CSV with one row per segment, indexed by the representative
timestamp and holding the duration of that segment in hours.

### Step 2 — Apply to the sector-coupled network (`prepare_sector_network.py`)

`set_temporal_aggregation()` reads the CSV and reindexes all time-dependent
network data (profiles, loads, snapshot weightings) to the reduced set of
snapshots:

```python title="scripts/prepare_sector_network.py"
snapshot_weightings = pd.read_csv(
    snakemake.input.snapshot_weightings, index_col=0, parse_dates=True
)
set_temporal_aggregation(n, snapshot_weightings)
```

---

## Configuration

### Via the `sector_opts` wildcard

The number of segments is set in `sector_opts` in the scenario config file.
The `SEG` suffix is parsed at runtime — no code change is needed:

```yaml title="config/scenarios/config.SE.yaml"
scenario:
  sector_opts:
  - 2190SEG-T-H-B-I-A   # full study resolution
```

| `sector_opts` value | Segments | Intended use |
|---|---|---|
| `2190SEG-T-H-B-I-A` | 2190 | Full study (publication results) |
| `256SEG-T-H-B-I-A` | 256 | Pipeline test with sector coupling |
| `256SEG` | 256 | Electricity-only pipeline test |

### Via the static config (alternative)

`snapshots.segmentation` in `config/config.agora.yaml` can also trigger
segmentation. It is `false` by default — all scenarios use the wildcard
approach instead:

```yaml title="config/config.agora.yaml"
snapshots:
  start: "2013-01-01"
  end: "2014-01-01"
  inclusive: 'left'
  resolution: false      # hourly resampling, e.g. "4h" — disabled by default
  segmentation: false    # static segment count — disabled by default
```

The wildcard always takes precedence over the static config value.

---

## How to Change the Number of Segments

Edit `sector_opts` in the relevant scenario config:

```yaml title="config/scenarios/config.SE.yaml"
scenario:
  sector_opts:
  - 128SEG-T-H-B-I-A   # fewer segments → faster, less accurate
```

!!! warning
    Results produced with different segment counts are **not directly
    comparable**. The study uses `2190SEG` for all published results.
    Use reduced counts (e.g. `256SEG`) only for pipeline testing.
