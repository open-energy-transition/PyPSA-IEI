# -*- coding: utf-8 -*-
import os
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")

import configurable_energy_balances as ceb
import geopandas as gpd
import pypsa
from analyze_total_system_cost import analyze_system_cost
from common import import_network, log
from compare_grids import plot_grid_comparisons
from configurable_energy_balances import (
    compute_energy_balance_cache,
    get_standard_balances,
)
from exogenous_demand_analyses import get_transport_demand_plot
from grid_emission_factors import analyze_grid_emission_factors
from h2_generation import analyze_h2_generation
from import_analysis import analyze_imports
from installed_capacity import call_installed_capacity_plot
from line_usage import evaluate_line_usage
from marginal_prices import get_marginal_prices
from matplotlib import pyplot as plt
from plot_balance_map import load_config, plot_balance_map_years
from plot_cases_KPIs import plot_case_study_KPIs
from plot_ch4_network import plot_ch4_map_years
from plot_co2_network import plot_co2_map_years
from plot_dispatch_barchart import plot_dispatch_barchart
from plot_elec_network import plot_map_elec_years
from plot_GWkm import plot_TWkm_all_carriers
from plot_h2_network import plot_h2_map_years
from regional_self_sufficiency_level import evaluate_self_sufficiency
from summary_KPIs import start_KPI_analysis

# Variables needed everywhere:
countries = [
    "AL",
    "AT",
    "BA",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "ME",
    "MK",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "RS",
    "SE",
    "SI",
    "SK",
]

eu27_countries = [
    "AT",
    "BE",
    "BG",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
]  # excluding Malta and Cyprus

th_countries = [
    "AT",
    "BE",
    "BG",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "NL",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
]  # TransHyDE countries


def load_all_network_files(
    runs,
    main_dir,
    postnetwork_prefixes,
    years,
    scenarios,
    off_region_seq=False,
    off_regions=None,
):
    # load all network files from results folder into a nested dictionary
    networks_year = {}
    for year in years:
        curr_networks = {}
        for scen in scenarios:
            log(f"  Loading network: {year} / {scen}")
            run_name = runs[scen]
            postnetwork_prefix = postnetwork_prefixes[scen]
            path_to_networks = Path(f"{main_dir}/results/{run_name}/postnetworks")
            if off_region_seq is False:
                n = pypsa.Network(
                    path_to_networks / f"{postnetwork_prefix}_{year}.nc"
                )  # load the network
            if off_region_seq is True:
                n = import_network(
                    path_to_networks / f"{postnetwork_prefix}_{year}.nc",
                    revert_dac=True,
                    offshore_sequestration=True,
                    offshore_regions=off_regions,
                )
            curr_networks.update({scen: n})

        networks_year.update({year: curr_networks})
    return networks_year


if __name__ == "__main__":
    # User configuration for input data:
    years = ["2030", "2035", "2040", "2045", "2050"]
    all_years = ["2020", "2030", "2035", "2040", "2045", "2050"]
    # insert run names for scenarios here:
    runs = {
        "scenario_1": "run_name_1",
        "scenario_2": "run_name_2",
        "scenario_3": "run_name_3",
        "scenario_4": "run_name_4",
    }
    sector_opts = {
        "scenario_1": "2190SEG-T-H-B-I-A",
        "scenario_2": "2190SEG-T-H-B-I-A",
        "scenario_3": "2190SEG-T-H-B-I-A",
        "scenario_4": "2190SEG-T-H-B-I-A",
    }  # e.g. '2190SEG-T-H-B-I-A', '20SEG-T-H-B-A', or '20SEG'

    postnetwork_prefixes = {
        scen: f"elec_s_62_lv99__{sector_opt}"
        for scen, sector_opt in sector_opts.items()
    }

    # choose scenario for focus analysis
    sel_scen = "scenario_1"
    # choose two scenarios for comparison
    scenarios_for_comp = ["scenario_1", "scenario_2"]

    # Resample PNG time-series to hourly (True = uniform x-axis, slower).
    ceb.RESAMPLE_TIMESERIES_PNG = False

    # User configuration for output data:
    evaluation_name = "analysis_results"
    timestamp = datetime.now().strftime("%Y%m%d")
    full_name = evaluation_name + "_" + timestamp

    # define colors for plotting of the scenarios
    scenario_colors = {
        "scenario_1": "#39C1CD",
        "scenario_2": "#F58220",
        "scenario_3": "#179C7D",
        "scenario_4": "#854006",
    }

    # Dictionary of executed post-analysis scripts
    executed_analysis = {
        "Exogenous demand": True,
        "Marginal prices": True,
        "H2 generation & full-load hours": True,
        "Grid emission factors": True,
        "Energy balances": True,
        "Network plots": True,
        "KPIs": True,
        "Self-sufficiency": True,
        "System costs": True,
        "Utilization": True,
        "Import": True,
        "Balance maps": True,
    }

    scenarios = list(runs.keys())
    scenarios_compare = []
    for scen in scenarios:
        if scen != sel_scen:
            scenarios_compare.append(scen)

    scenario_colors_comp = {key: scenario_colors[key] for key in scenarios_for_comp}
    # Directories
    main_dir = Path(os.getcwd()).parent
    resultdir = (
        Path(main_dir) / full_name
    )  # folder where Excel files and graphs are stored
    if not os.path.exists(resultdir):
        os.makedirs(resultdir)

    scenarios = list(runs.keys())
    networks = load_all_network_files(
        runs,
        main_dir,
        postnetwork_prefixes,
        years,
        scenarios,
    )
    add_years = [item for item in all_years if item not in years]
    networks_all = load_all_network_files(
        runs,
        main_dir,
        postnetwork_prefixes,
        add_years,
        scenarios,
    )
    networks_all.update(networks)

    ## DEMAND DATA
    # Pre-compute energy_balance() for all networks once — reused by all
    # get_standard_balances calls (avoids 2 × years × scenarios calls per carrier)
    log("Pre-computing energy balance cache...")
    en_balance_cache = compute_energy_balance_cache(networks, years, scenarios)

    # EXOGENOUS DEMAND
    if executed_analysis["Exogenous demand"]:
        # Make demand data plots (one scenario but all available years) and store
        # them in demand_resultdir:
        demand_resultdir = (
            resultdir / "ExogenousDemand"
        )  # folder where Excel files and graphs are stored
        if not os.path.exists(demand_resultdir):
            os.makedirs(demand_resultdir)

        # Transport
        get_transport_demand_plot(
            networks,
            years,
            sel_scen,
            demand_resultdir,
        )

    ## MARGINAL PRICES
    if executed_analysis["Marginal prices"]:
        prices_dir = resultdir / "marginal_prices"
        if not os.path.exists(prices_dir):
            os.mkdir(prices_dir)
        get_marginal_prices(
            networks,
            years,
            scenarios,
            scenario_colors,
            prices_dir,
        )

    ## H2 GENERATION & FULL-LOAD HOURS
    if executed_analysis["H2 generation & full-load hours"]:
        h2_gen_dir = resultdir / "h2_generation"
        if not os.path.exists(h2_gen_dir):
            os.mkdir(h2_gen_dir)
        analyze_h2_generation(
            networks,
            years,
            scenarios,
            h2_gen_dir,
        )

    ## GRID EMISSION FACTORS
    if executed_analysis["Grid emission factors"]:
        emission_factors_dir = resultdir / "grid_emission_factors"
        if not os.path.exists(emission_factors_dir):
            os.mkdir(emission_factors_dir)
        analyze_grid_emission_factors(
            networks,
            years,
            scenarios,
            emission_factors_dir,
        )

    ## ENERGY BALANCES
    # extract balance for (groups of) clusters/countries
    country_to_plot = "DE"
    compare_scenarios = [True, False]

    # ENERGY BALANCES
    if executed_analysis["Energy balances"]:
        balance_resultdir = (
            resultdir / "Balances"
        )  # folder where Excel files and graphs are stored
        if not os.path.exists(balance_resultdir):
            os.makedirs(balance_resultdir)

        # ENERGY BALANCES (ELECTRICITY)
        carrier_for_balance = "electricity"
        get_standard_balances(
            networks,
            carrier_for_balance,
            years,
            scenarios,
            balance_resultdir,
            country_to_plot,
            compare_scenarios,
            en_balance_cache=en_balance_cache,
        )

        # ENERGY BALANCES (GAS)
        carrier_for_balance = "gas"
        get_standard_balances(
            networks,
            carrier_for_balance,
            years,
            scenarios,
            balance_resultdir,
            country_to_plot,
            compare_scenarios,
            en_balance_cache=en_balance_cache,
        )

        # ENERGY BALANCES (LOW VOLTAGE)
        carrier_for_balance = "low voltage"
        get_standard_balances(
            networks,
            carrier_for_balance,
            years,
            scenarios,
            balance_resultdir,
            country_to_plot,
            compare_scenarios,
            en_balance_cache=en_balance_cache,
        )

        # ENERGY BALANCES (H2)
        carrier_for_balance = "H2"
        get_standard_balances(
            networks,
            carrier_for_balance,
            years,
            scenarios,
            balance_resultdir,
            country_to_plot,
            compare_scenarios,
            en_balance_cache=en_balance_cache,
        )

        # ENERGY BALANCES (HEAT)
        carrier_for_balance = "heat"
        get_standard_balances(
            networks,
            carrier_for_balance,
            years,
            scenarios,
            balance_resultdir,
            country_to_plot,
            compare_scenarios,
            en_balance_cache=en_balance_cache,
        )

        # ENERGY BALANCES (URBAN CENTRAL HEAT)
        carrier_for_balance = "urban central heat"
        get_standard_balances(
            networks,
            carrier_for_balance,
            years,
            scenarios,
            balance_resultdir,
            country_to_plot,
            compare_scenarios=[True],
            en_balance_cache=en_balance_cache,
        )

    # NETWORK PLOTS
    country_to_plot_networks = "EU27"
    if executed_analysis["Network plots"]:
        network_plot_dir = resultdir / "network_plots"
        if not os.path.exists(network_plot_dir):
            os.mkdir(network_plot_dir)

        # ELECTRICITY NETWORK PLOTS
        plot_map_elec_years(
            networks,
            network_plot_dir,
            scenarios,
            years,
            main_dir,
            postnetwork_prefixes,
            runs,
            country_to_plot_networks,
        )

        # H2 NETWORK PLOTS
        plot_h2_map_years(
            networks,
            main_dir,
            network_plot_dir,
            years,
            scenarios,
            runs,
            country_to_plot_networks,
        )

        # CO2 NETWORK PLOTS
        plot_co2_map_years(
            networks,
            network_plot_dir,
            years,
            scenarios,
            country_to_plot_networks,
        )

        # CH4 NETWORK PLOTS
        plot_ch4_map_years(
            networks,
            network_plot_dir,
            years,
            scenarios,
            country_to_plot_networks,
        )

        # GRID COMPARISONS
        for scen_comp in scenarios_compare:
            scenarios_for_comp = [sel_scen, scen_comp]
            scenario_colors_comp = {
                key: scenario_colors[key] for key in scenarios_for_comp
            }
            plot_grid_comparisons(
                networks,
                years,
                network_plot_dir,
                scenario_colors_comp,
                country_to_plot_networks,
            )

    ## KPIs
    if executed_analysis["KPIs"]:
        KPI_dir = resultdir / "KPIs"
        if not os.path.exists(KPI_dir):
            os.mkdir(KPI_dir)
        plot_backup_capas = True
        call_installed_capacity_plot(
            networks,
            years,
            scenarios,
            KPI_dir,
            plot_backup_capas,
        )

        # INFRASTRUCTURE VOLUME
        plot_TWkm_all_carriers(
            networks,
            scenario_colors,
            scenarios,
            years,
            KPI_dir,
        )

        # SUMMARY KPIs
        start_KPI_analysis(
            networks,
            years,
            scenarios,
            main_dir,
            KPI_dir,
        )

        plot_case_study_KPIs(
            networks,
            years,
            runs,
            main_dir,
            KPI_dir,
        )

        plot_dispatch_barchart(
            KPI_dir,
            networks,
            runs,
            years,
            "flexibility",
        )

    ## SELF-SUFFICIENCY
    if executed_analysis["Self-sufficiency"]:
        self_sufficiency_dir = resultdir / "self-sufficiency"
        if not os.path.exists(self_sufficiency_dir):
            os.mkdir(self_sufficiency_dir)
        for scen_comp in scenarios_compare:
            scenarios_for_comp = [sel_scen, scen_comp]
            evaluate_self_sufficiency(
                networks,
                scenarios,
                scenario_colors,
                scenarios_for_comp,
                main_dir,
                self_sufficiency_dir,
                runs,
                years,
            )

    ## SYSTEM COSTS
    if executed_analysis["System costs"]:
        costs_dir = resultdir / "costs"
        if not os.path.exists(costs_dir):
            os.mkdir(costs_dir)
        backup_capas = True
        analyze_system_cost(
            main_dir,
            runs,
            costs_dir,
            sel_scen,
            scenario_colors,
            years,
            backup_capas,
        )
        plt.close("all")

    ## LINE USAGE
    if executed_analysis["Utilization"]:
        util_dir = resultdir / "utilization"
        if not os.path.exists(util_dir):
            os.mkdir(util_dir)
        evaluate_line_usage(
            networks,
            years,
            scenarios,
            util_dir,
        )
        plt.close("all")

    # IMPORT
    if executed_analysis["Import"]:
        import_resultdir = (
            resultdir / "Import"
        )  # folder where Excel files and graphs are stored
        if not os.path.exists(import_resultdir):
            os.makedirs(import_resultdir)
        analyze_imports(
            networks,
            years,
            import_resultdir,
        )
        plt.close("all")

    ## BALANCE MAPS
    if executed_analysis["Balance maps"]:
        off_regions_path = (
            main_dir
            / "scripts_analysis"
            / "shapes"
            / "regions_offshore_elec_s_62.geojson"
        )
        off_regions = gpd.read_file(off_regions_path).set_index("name")
        networks_off = load_all_network_files(
            runs,
            main_dir,
            postnetwork_prefixes,
            years,
            scenarios,
            True,
            off_regions,
        )

        balance_maps_dir = resultdir / "balance_maps"
        if not os.path.exists(balance_maps_dir):
            os.mkdir(balance_maps_dir)

        config = load_config(main_dir / "config" / "config.plotting.yaml")
        plot_balance_map_years(
            networks_off,
            balance_maps_dir,
            years,
            scenarios,
            config,
            off_regions,
            country_to_plot_networks,
            sel_scen,
        )

    print("Done")
