# Installation

## Requirements

- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda or Anaconda)
- [Snakemake](https://snakemake.readthedocs.io) (included in the environment)
- A supported solver: [Gurobi](https://www.gurobi.com) (recommended) or HiGHS

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
sensitivities. To reproduce a scenario, run Snakemake with the desired
configuration file:

```bash
snakemake -call all --configfile config/scenarios/<scenario_file>.yaml
```

For example, to run the **SN** (**S**ectoral, **N**ational) scenario:

```bash
snakemake -call all --configfile config/scenarios/config.SN.yaml
```

### Reducing Temporal Resolution

The study uses **2190 time segments** (`2190SEG`), which requires significant
compute time and memory. To run on a laptop, or for fast testing and
development, reduce the number of segments by editing `sector_opts` in the
scenario config file:

```yaml
# config/scenarios/config.SN.yaml
scenario:
  sector_opts:
  - 256SEG-T-H-B-I-A   # reduced from 2190SEG
```

!!! note
    Reducing segments changes optimisation results. Use full `2190SEG` for
    results comparable to the study.

For further details on running PyPSA-Eur-based models, refer to the
[open-source documentation](https://pypsa-eur.readthedocs.io/en/latest/index.html).

### OETC Cloud Solver (Optional)

Network preparation runs locally. The solving step can be offloaded to the
Open Energy Transition Cloud (OETC) instead of running on your machine.
To enable this, add an `oetc:` block to the `solving:` section of your
scenario config file and set your credentials as environment variables.

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
    Remove the `oetc:` block entirely to fall back to the local solver
    (`gurobi` or HiGHS) without any code changes.

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

??? warning "Out of memory during profile building"

    Building renewable profiles with Atlite is memory-intensive. The default
    configuration uses 4 parallel processes (~20 GB RAM total). On machines
    with less than 16 GB, reduce `nprocesses` in `config/config.agora.yaml`:

    ```yaml
    atlite:
      nprocesses: 1  # use 1 on machines with < 16 GB RAM
    ```

??? warning "Run is slow or crashing on a laptop"

    By default, Snakemake uses all available CPU cores (`-call` = `--cores all`).
    On a laptop, limiting parallelism reduces peak memory and CPU pressure:

    ```bash
    snakemake --cores 2 all --configfile config/scenarios/config.SN.yaml
    ```

    For a quick test run, also reduce the number of time segments (see
    [Reducing Temporal Resolution](#reducing-temporal-resolution))

---

## 5. Run the Evaluations

To use the analysis scripts developed for this study:

1. Copy the following files into `scripts_analysis/shapes/`:
    - `country_shapes.geojson`
    - `regions_offshore_elec_s_62.geojson`
    - `regions_onshore_elec_s_62.geojson`

2. Open `scripts_analysis/analysis_main.py` and enter your specifications
   for the results you want to analyze.

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
