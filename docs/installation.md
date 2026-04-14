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
data/entsoegridkit/
data/existing_infrastructure/
data/parameter_corrections.yaml
data/links_p_nom.csv
data/eia_hydro_annual_generation.csv
data/GDP_PPP_30arcsec_v3_mapped_default.csv
data/unit_commitment.csv
data/geth2015_hydro_capacities.csv
data/nuclear_p_max_pu.csv
data/district_heat_share.csv
data/switzerland-new_format-all_years.csv
data/urban_percent.csv
data/attributed_ports.json
data/heat_load_profile_BDEW.csv
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

For example, to run the base scenario:

```bash
snakemake -call all --configfile config/scenarios/config.base.yaml
```

For further details on running PyPSA-Eur-based models, refer to the
[open-source documentation](https://pypsa-eur.readthedocs.io/en/latest/index.html).

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
