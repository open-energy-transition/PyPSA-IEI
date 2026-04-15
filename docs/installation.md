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

---

## 2. Download Input Data

This repository only contains input data explicitly developed for this study.
The following files must be copied from
[PyPSA-Eur v0.10.0 (February 19, 2024)](https://github.com/PyPSA/pypsa-eur/tree/9c08af998906eec076745fae45e849bf2fc54643)
into the `data/` folder of this repository:

```
pypsa-eur/                          ← source repository
└── data/
    ├── entsoegridkit/
    ├── existing_infrastructure/
    ├── parameter_corrections.yaml
    ├── links_p_nom.csv
    ├── eia_hydro_annual_generation.csv
    ├── GDP_PPP_30arcsec_v3_mapped_default.csv
    ├── unit_commitment.csv
    ├── geth2015_hydro_capacities.csv
    ├── nuclear_p_max_pu.csv
    ├── district_heat_share.csv
    ├── switzerland-new_format-all_years.csv
    ├── urban_percent.csv
    ├── attributed_ports.json
    └── heat_load_profile_BDEW.csv
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
study results.

**Step 1 — Reduce the temporal resolution**

Edit `sector_opts` in your scenario config to use fewer time segments:

```yaml
# config/scenarios/config.SN.yaml
scenario:
  sector_opts:
  - 256SEG-T-H-B-I-A   # reduced from 2190SEG — much faster, less memory
```

For the fastest possible run (electricity-only, no sector coupling), omit all
sector suffixes entirely:

```yaml
scenario:
  sector_opts:
  - 256SEG   # electricity-only — pipeline test only
```

| Suffix | Sector coupled |
|--------|----------------|
| `T`    | Transport      |
| `H`    | Heat           |
| `B`    | Biomass        |
| `I`    | Industry       |
| `A`    | Agriculture    |

!!! warning
    Reduced-segment and electricity-only results are **not comparable** to the
    study. Use this track only to verify the workflow runs without errors.

**Step 2 — Run the solve step**

Use `solve_sector_networks` as the target (avoids `make_summary`, which fails
when sectors are omitted) and limit to a single core:

```bash
snakemake --cores 1 solve_sector_networks --configfile config/scenarios/config.SN.yaml
```

!!! tip
    If you want to skip local solving entirely, see the
    [OETC Cloud Solver](#oetc-cloud-solver-optional-skip-local-solving) section below.

If you run into issues, see the [Troubleshooting](#troubleshooting) section.

---

### Track 2 — Full Study Run

This track reproduces the study results. It requires a machine with sufficient
memory and compute time (hours to days depending on hardware).

**Run all steps with the full configuration:**

```bash
snakemake -call all --configfile config/scenarios/config.SN.yaml
```

!!! note
    The study uses **2190 time segments** (`2190SEG`) with all sector suffixes
    (`-T-H-B-I-A`). Do not modify `sector_opts` if you want results comparable
    to the publication.

!!! warning
    On Windows, always use `--cores 1` — running with more than one core causes
    crashes during the solving step.

For further details on running PyPSA-Eur-based models, refer to the
[open-source documentation](https://pypsa-eur.readthedocs.io/en/latest/index.html).

If you run into issues, see the [Troubleshooting](#troubleshooting) section.

### OETC Cloud Solver (Optional — Skip Local Solving)

If you prefer not to run the solver locally — whether because of hardware
limitations or to save time — the solving step can be offloaded to the
Open Energy Transition Cloud (OETC). This works with both Track 1 and Track 2.
Network preparation always runs locally; only the solve step is offloaded.

**Step 1 — Add the `oetc:` block to your scenario config:**

```yaml
# config/scenarios/config.SN.yaml  (or any other scenario file)
solving:
  oetc:
    name: "my-oetc-job"
    authentication_server_url: "https://oetc.openenergytransition.org"
    orchestrator_server_url: "https://oetc.openenergytransition.org"
    cpu_cores: 16
    disk_space_gb: 100
```

!!! note
    Remove the `oetc:` block entirely to fall back to the local Gurobi solver
    without any code changes.

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

    ```bash
    snakemake --cores 2 all --configfile config/scenarios/config.SN.yaml
    ```

    On Windows, always use `--cores 1` (see [Track 2](#track-2-full-study-run)).

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

2. Open `scripts_analysis/analysis_main.py` and set the `runs` dictionary to map scenario labels to your run names:

    ```python
    runs = {
        "scenario_1": "2025-MM-DD-branch-2190SEG-SN",
        # "scenario_2": "run_name_2",
        # "scenario_3": "run_name_3",
        # "scenario_4": "run_name_4",
    }
    ```

    The run name must match the `run.name` value in the corresponding scenario
    config file and the folder name under `results/`. Unused scenarios can be
    commented out.

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
