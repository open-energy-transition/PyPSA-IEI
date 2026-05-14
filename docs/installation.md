# Installation

## Requirements

- [Git](https://git-scm.com/downloads) — for cloning the repository
  (**Windows:** [Git for Windows](https://gitforwindows.org/) is recommended, which also includes **Git Bash**)
- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda or Anaconda) — for environment management
- [Gurobi](https://www.gurobi.com) — a commercial solver licence is required to run the model locally.
  If you do not have a Gurobi licence, use the [OETC Cloud Solver](#oetc-cloud-solver-optional-skip-local-solving) instead.

---

## 1. Clone the Repository

```bash
git clone https://github.com/open-energy-transition/PyPSA-IEI.git
cd PyPSA-IEI
```

!!! important "Working directory"
    All Snakemake commands in this guide must be run from inside the `PyPSA-IEI/` directory.
    The `cd PyPSA-IEI` above puts you there after cloning. If you open a new terminal, run:

    ```bash
    cd /path/to/PyPSA-IEI
    ```

---

## 2. Download Input Data

This repository only contains input data explicitly developed for this study.
The following files must be copied from
[PyPSA-Eur v0.10.0 (February 19, 2024)](https://github.com/PyPSA/pypsa-eur/tree/9c08af998906eec076745fae45e849bf2fc54643)
into the `data/` folder of this repository:

```
pypsa-eur/                          ← source repository
└── data/
    ├── GDP_PPP_30arcsec_v3_mapped_default.csv
    ├── switzerland-new_format-all_years.csv
    └── urban_percent.csv
```

Additional data will be automatically retrieved by Snakemake rules during
the first run.

!!! note
    The data used to generate the study results were downloaded on
    **June 27th 2024**.

---

## 3. Set Up the Environment

Create and activate the conda environment using the file matching your operating system:

=== "Windows"

    ```bash
    conda env create -f envs/environment_pypsa_iei.yaml
    conda activate pypsa-iei
    ```

=== "Linux"

    ```bash
    conda env create -f envs/environment_pypsa_iei_linux.yaml
    conda activate pypsa-iei
    ```

For detailed instructions on setting up PyPSA-Eur, refer to the
[official documentation](https://pypsa-eur.readthedocs.io/en/latest/installation.html).

---

## 4. Run a Scenario

Results for the study were generated across four main scenarios and four
sensitivities. Choose the track that matches your situation:

---

### Track 1 — Pipeline Test (Low-End Machine)

This track is designed for running the model on a low-end or Windows machine,
or for anyone who wants to verify the full pipeline works end-to-end before
committing to a full run. The goal is to test the workflow, not to reproduce
study results. Indicative requirements per scenario:

| Configuration | RAM | Time |
|---------------|-----|------|
| `20SEG-T-H-B-I-A` (recommended reduced-resolution test) | >32 GB | ~9 hours |
| `20SEG` (electricity-only fallback, limited downstream compatibility in post-analysis) | > 16 GB | ~3.5 hours |

!!! tip "No local solver?"
    If you do not have a Gurobi licence or prefer to offload solving,
    see the [OETC Cloud Solver](#oetc-cloud-solver-optional-skip-local-solving) section below.

!!! tip "Which config to use for testing?"
    Use `config.SE.yaml` for pipeline testing. It has fewer custom constraints
    and works correctly even when sector suffixes (`T`, `H`, `B`, `I`, `A`) are
    omitted. `config.SN.yaml` enables self-sufficiency constraints that require
    industry sector components (e.g. Fischer-Tropsch links) to be present —
    running it without the `I` suffix will cause an error.

**Step 1 — Reduce the temporal resolution**

Edit `sector_opts` in your scenario config to use fewer time segments while keeping the sector suffixes enabled:

```yaml
# config/scenarios/config.SE.yaml
scenario:
  sector_opts:
  - 20SEG-T-H-B-I-A   # reduced from 2190SEG — much faster, less memory
```

This is the recommended Track 1 setup. It keeps the workflow closer to the
full study configuration and avoids downstream issues in summary generation and
post-analysis scripts that can appear with electricity-only runs.

If you only want the lightest possible smoke test, you can still omit the
sector suffixes entirely:

```yaml
scenario:
    sector_opts:
    - 20SEG
```

However, this electricity-only variant should be treated as a minimal pipeline
check only. Later postprocessing and analysis steps are more likely to **fail with
an electricity-only model**.

!!! warning
        Reduced-segment results are **not comparable** to the study. Electricity-only
        runs are even more limited and are mainly useful for quick smoke tests.

**Step 2 — Dry run (recommended)**

Verify that Snakemake can resolve all rules and inputs before executing anything:

```bash
~/PyPSA-IEI$ snakemake -call all --configfile config/scenarios/config.SE.yaml --dry-run
```

**Step 3 — Run the full workflow**

Use the `all` target so the full pipeline runs and the summary outputs needed
for later analysis are generated. Start with as many cores as your machine can
handle:

```bash
~/PyPSA-IEI$ snakemake -call all --configfile config/scenarios/config.SE.yaml
```

If you are on Windows, you can still start with the `all` target as shown
above. If the workflow later becomes unstable when it reaches
`solve_sector_networks`, see [Troubleshooting](#troubleshooting) and resume the
same target with `--cores 1`.

Once the run completes, see [Verifying Success](#verifying-success) to confirm the output files are in place.
If you run into issues, see the [Troubleshooting](#troubleshooting) section.

---

### Track 2 — Full Study Run

This track reproduces the study results. It requires a machine with sufficient
memory (approximately **250 GB of RAM**) and compute time (approximately
**2.5 days** per scenario).

**Step 1 — Dry run (recommended)**

Before launching the full run, verify that Snakemake can resolve all rules and inputs without executing anything:

```bash
~/PyPSA-IEI$ snakemake -call all --configfile config/scenarios/config.SN.yaml --dry-run
```

This prints the list of jobs that would be executed. If any rule or input file is missing, the error appears here — before committing hours of compute time.

**Step 2 — Run all steps with the full configuration:**

```bash
~/PyPSA-IEI$ snakemake -call all --configfile config/scenarios/config.SN.yaml
```

!!! note
    The study uses **2190 time segments** (`2190SEG`) with all sector suffixes
    (`-T-H-B-I-A`). Do not modify `sector_opts` if you want results comparable
    to the publication.

!!! warning
    On Windows, the workflow may become unstable once it reaches
    `solve_sector_networks`. Start with as many cores as you want, but if the
    solve stage fails, resume with `--cores 1` as described in
    [Troubleshooting](#troubleshooting).

---

### Verifying Success

Snakemake prints the following when all jobs complete without errors:

```
X of X steps (100%) done
```

For each planning horizon (2020–2050), a solved network file should appear under
`results/<run_name>/postnetworks/`. The exact filename depends on your track:

| Track | Example postnetwork file |
|-------|--------------------------|
| Track 1 — `20SEG-T-H-B-I-A` | `elec_s_62_lv99__20SEG-T-H-B-I-A_2020.nc` |
| Track 2 — `2190SEG-T-H-B-I-A` | `elec_s_62_lv99__2190SEG-T-H-B-I-A_2050.nc` |

If any files are missing, check the corresponding log file under `logs/` for the failing rule.

For further details on running PyPSA-Eur-based models, refer to the
[open-source documentation](https://pypsa-eur.readthedocs.io/en/latest/index.html).

If you run into issues, see the [Troubleshooting](#troubleshooting) section.

---

### OETC Cloud Solver (Optional — Skip Local Solving)

If you prefer not to run the solver locally — whether because of hardware
limitations or to save time — the solving step can be offloaded to the
Open Energy Transition Cloud (OETC). This works with both Track 1 and Track 2.
Network preparation always runs locally; only the solve step is offloaded.

**Step 1 — Enable OETC in your scenario config:**

The `oetc` block is already present in `config/config.agora.yaml` with OETC disabled by default.
To enable it, add the following override to your scenario config:

```yaml
# config/scenarios/config.SE.yaml  (or any other scenario file)
solving:
  oetc:
    enabled: true
```

!!! note
    Set `enabled: false` or omit the override entirely to fall back to the local solver.

**Step 2 — Set your OETC credentials as environment variables:**

=== "Linux"

    Add to your `~/.bashrc` (or `~/.bash_profile`) for a persistent setup:

    ```bash
    nano ~/.bashrc   # or: vi ~/.bashrc
    ```

    Append these lines:

    ```bash
    export OETC_EMAIL="your@email.com"
    export OETC_PASSWORD="yourpassword"
    ```

    Then reload and verify:

    ```bash
    source ~/.bashrc
    echo $OETC_EMAIL
    ```

=== "Windows (Git Bash)"

    Add to your `~/.bashrc`:

    ```bash
    nano ~/.bashrc   # or: vi ~/.bashrc
    ```

    Append these lines:

    ```bash
    export OETC_EMAIL="your@email.com"
    export OETC_PASSWORD="yourpassword"
    ```

    Then reload and verify:

    ```bash
    source ~/.bashrc
    echo $OETC_EMAIL
    ```

=== "Windows (PowerShell)"

    For the current session only:

    ```powershell
    $env:OETC_EMAIL = "your@email.com"
    $env:OETC_PASSWORD = "yourpassword"
    ```

    For a persistent setup (user-level):

    ```powershell
    [System.Environment]::SetEnvironmentVariable("OETC_EMAIL", "your@email.com", "User")
    [System.Environment]::SetEnvironmentVariable("OETC_PASSWORD", "yourpassword", "User")
    ```

    Verify (restart the terminal first for persistent variables to take effect):

    ```powershell
    echo $env:OETC_EMAIL
    ```

---

## Troubleshooting

If the steps below do not resolve your issue, please open a report on the
[Support](support.md) page.

??? warning "Out of memory during profile building in `build_renewable_profile`"

    Building renewable profiles with Atlite is memory-intensive. The default
    configuration uses 4 parallel processes (~20 GB RAM total). On machines
    with less than 16 GB, reduce `nprocesses` in `config/config.agora.yaml`:

    ```yaml
    atlite:
      nprocesses: 1  # use 1 on machines with < 16 GB RAM
    ```

??? warning "Limit the number of cores (`--cores`)"

    By default, `-call` (`--cores all`) uses every available CPU core, which
    can exhaust memory and trigger crashes on Linux. Limiting parallelism
    reduces peak memory and CPU pressure:

    If you run into memory pressure, out-of-memory errors, or system
    instability during the workflow, rerun the same command with fewer cores.
    A good first step is to reduce to `--cores 2`, and if needed to `--cores 1`.

    ```bash
    ~/PyPSA-IEI$ snakemake --cores 2 all --configfile config/scenarios/config.SE.yaml
    ```

??? warning "Windows crashes when `solve_sector_networks` starts"

    On Windows, you can still start the workflow with multiple cores to speed up
    preprocessing and postprocessing:

    ```bash
    ~/PyPSA-IEI$ snakemake -call all --configfile config/scenarios/config.SE.yaml
    ```

    If the workflow reaches `solve_sector_networks` and then crashes or becomes
    unstable, rerun the same target with one core:

    ```bash
    ~/PyPSA-IEI$ snakemake --cores 1 all --configfile config/scenarios/config.SE.yaml
    ```

    Snakemake will reuse completed upstream jobs and continue from the remaining
    solve and postprocessing steps.

---

## 5. Run the Evaluations

To use the analysis scripts developed for this study:

1. Copy the following files into `scripts_analysis/shapes/`:

    | File | Source (generated by the pipeline) |
    |------|-------------------------------------|
    | `country_shapes.geojson` | `resources/<run_name>/country_shapes.geojson` |
    | `regions_onshore_elec_s_62.geojson` | `resources/<run_name>/regions_onshore_elec_s_62.geojson` |
    | `regions_offshore_elec_s_62.geojson` | `resources/<run_name>/regions_offshore_elec_s_62.geojson` |

    Replace `<run_name>` with the value of `run.name` from your scenario config file (e.g. `2025-MM-DD-branch-2190SEG-SN`).
    These files are produced by the `build_shapes` and `cluster_network` Snakemake rules and are available after the pipeline has run at least once.

2. Open `scripts_analysis/analysis_main.py` and update the scenario-specific settings so they match the files created by your run:

    ```python
    runs = {
        "SE": "2025-MM-DD-branch-2190SEG-SE",
        "CE": "2025-MM-DD-branch-2190SEG-CE",
        # "scenario_3": "run_name_3",
        # "scenario_4": "run_name_4",
    }

    sector_opts = {
        "SE": "20SEG-T-H-B-I-A",
        "CE": "20SEG-T-H-B-I-A",
        # "scenario_3": "2190SEG-T-H-B-I-A",
        # "scenario_4": "2190SEG-T-H-B-I-A",
    }

    postnetwork_prefixes = {
        scen: f"elec_s_62_lv99__{sector_opt}"
        for scen, sector_opt in sector_opts.items()
    }

    # Reference scenario — used as the baseline in all comparison/residual plots.
    # Must be one of the keys defined in `runs`.
    sel_scen = "SE"

    # No need to edit — overridden automatically by the script during execution.
    scenarios_for_comp = ["SE", "CE"]

    # Every key in `runs` must have an entry here or the script will crash.
    scenario_colors = {
        "SE": "#F58220",
        "CE": "#39C1CD",
        # "scenario_3": "#179C7D",
        # "scenario_4": "#854006",
    }
    ```

    The run name must match the `run.name` value in the corresponding scenario
    config file and the folder name under `results/`.

    Each `sector_opts` entry must match the solved postnetwork filename
    suffix exactly, including the temporal resolution and any enabled
    sector-coupling suffixes. For example:

    - full study run: `2190SEG-T-H-B-I-A`
    - reduced-resolution sector-coupled test: `20SEG-T-H-B-I-A`

    `analysis_main.py` converts these entries into the full postnetwork prefix
    automatically, so users only need to edit `runs` and `sector_opts`.

    Unused scenarios can be commented out.

    !!! warning "At least two entries required in `runs`"
        The cost analysis script generates comparison plots (residual capital
        costs, residual operational costs) that require a reference scenario
        and at least one other scenario to compare against. **Running with
        only one entry in `runs` will cause a crash.**

        If you have only one run, duplicate it under a second key as a
        workaround:

        ```python
        runs = {
            "SE":  "2025-MM-DD-branch-2190SEG-SE",
            "SE2": "2025-MM-DD-branch-2190SEG-SE",  # same run, avoids crash
        }
        sector_opts = {
            "SE":  "20SEG-T-H-B-I-A",
            "SE2": "20SEG-T-H-B-I-A",
        }
        sel_scen = "SE"
        scenario_colors = {
            "SE":  "#39C1CD",
            "SE2": "#39C1CD",
        }
        ```

        The residual/comparison plots will show zero differences, which is
        expected when comparing a scenario against itself.

3. Execute it:

```bash
python scripts_analysis/analysis_main.py
```

This will run all evaluations automatically.

---

## Documentation Environment (Optional)

To build or preview this documentation locally, create the lightweight docs
environment:

```bash
conda env create -f envs/environment_docs.yaml
conda activate pypsa-iei-docs
mkdocs serve
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.
