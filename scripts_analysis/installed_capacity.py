import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
from matplotlib import pyplot as plt

# Stylesheet for colors
plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
COLORS = plt.rcParams["axes.prop_cycle"].by_key()["color"]


def call_installed_capacity_plot(
    networks_year, years, scenarios, resultdir, backup_capas=False
):
    """
    Creates plots that include installed electricity capacities of
    selected generation technologies (aggregation).
        - Plot to compare scenarios per year
        - Plot of each scenario

    Parameters
    ----------
    networks_year : dict
        dict of years with calculated data per scenario
    years : list
        list of relevant years
    scenarios : list
        list of scenarios
    resultdir : pathlib.Path
        path of resultdirectory
    backup_capas : bool, optional
        boolean, by default False

    Returns
    -------
    None
    """
    # EU-countries aside from Cyprus and Malta
    EU27_countries = [
        "DK",
        "LV",
        "NL",
        "IT",
        "PL",
        "DE",
        "FI",
        "BE",
        "AT",
        "CZ",
        "HU",
        "RO",
        "EE",
        "PT",
        "BG",
        "GR",
        "LT",
        "ES",
        "SE",
        "FR",
        "LU",
        "SK",
        "IE",
        "SI",
        "HR",
    ]

    # Load additional backup gas data
    national = ["CN", "SN"]
    filter_regions = ["EU27", "All"]
    for filter in filter_regions:
        backup_capas_path = (
            resultdir.parent
            / "Balances"
            / "gas_turbine_backup_capacities.xlsx"
        )
        # check if input file exists to be plotted
        if not os.path.exists(backup_capas_path):
            backup_capas = False
        if backup_capas:
            backup_capacities = (
                pd.read_excel(
                    backup_capas_path, sheet_name=filter, index_col=0
                )
                * 1e-06
            )

        # Calculate data
        generation_capacities = {}
        storage_capacities = {}
        heat_capacities = {}
        for scen in scenarios:
            generation_capacities.update({scen: pd.DataFrame()})
            storage_capacities.update({scen: pd.DataFrame()})
            heat_capacities.update({scen: pd.DataFrame()})
        for year in years:
            for scen in scenarios:
                this_network = networks_year[year][scen]
                generation_result = calculate_installed_generation_capacity(
                    EU27_countries, this_network, filter
                )
                if backup_capas & (scen in national):
                    generation_result.loc["Backup capacities$^{1}$"] = (
                        backup_capacities.loc[scen, year]
                    )
                generation_capacities[scen][year] = generation_result
                storage_result = calculate_installed_storage_capacity(
                    EU27_countries, this_network, filter
                )
                storage_capacities[scen][year] = storage_result
                heat_result = calculate_installed_heat_capacity(
                    EU27_countries, this_network, filter
                )
                heat_capacities[scen][year] = heat_result

        plot_installed_capacities(
            filter, generation_capacities, resultdir, "generation"
        )
        plot_installed_capacities(filter, heat_capacities, resultdir, "heat")
        plot_installed_capacities(
            filter, storage_capacities, resultdir, "storage"
        )


def plot_installed_capacities(filter, per_scenario, resultdir, type):
    """
    Creates stacked bar charts with the aggregated capacity in a
    category given by 'type' (electricity, heat,...). One plot contains
    all years of each scenario, the other plot shows a scenario
    comparison.

    Parameters
    ----------
    filter : str
        string for identifier
    per_scenario : dict
        dictionary of capacity data for all scenarios and years
        {scneario: pd.DataFrame}
    resultdir : pathlib.Path
        Path of the directory for saving results
    type : str
        category to summarize the capcities plotted (e.g. electricity)

    Returns
    -------
    None
    """
    scenarios = list(per_scenario.keys())
    years = per_scenario[scenarios[0]].columns

    ## 1. Plot installed_{type}_capacities_{filter}.png
    # Updated stylesheet for installed capacity scenario
    plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
    # Initial plot settings and variables
    fig, ax1 = plt.subplots()
    scenarios_use = scenarios * len(years)
    first_scenario = next(iter(scenarios))
    r = {}
    x_ticks = []
    if type == "storage":
        unit = "TWh"
    else:
        unit = "TW"
    # Bar width
    barWidth = 0.8 / len(scenarios)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars on x axis
    for scenario in scenarios:
        r[scenario] = [x + i * barWidth + 0.3 for x in r0]
        i = i + 1
    threshold = 0.005
    categories_old = []
    # Create the stacked bar chart
    for scenario in scenarios:
        for j in range(0, len(r[scenario])):
            r[scenario][j] = np.round(r[scenario][j], 1)

        # Calculation
        result = aggregate_and_filter_negligible_carriers(
            per_scenario[scenario], threshold, type, "compare"
        )
        categories = result.index.tolist()
        # Ensure order matches previous scenarios
        ordered_categories = [x for x in categories if x in categories_old]
        [
            ordered_categories.append(x)
            for x in categories
            if x not in ordered_categories
        ]

        # Plot
        diff = 0.0115
        bottoms = np.zeros(len(years))
        for kpi in ordered_categories:
            index = ordered_categories.index(kpi)
            y_values = result.loc[kpi]

            if i > 0:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=ordered_categories[index],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=ordered_categories[index],
                    )
                bottoms = np.add(bottoms, y_values)
            else:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=ordered_categories[index],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=ordered_categories[index],
                    )
                bottoms = np.add(bottoms, y_values)

        for j in range(0, len(r[scenario])):
            if r[scenario][j] not in x_ticks:
                x_ticks.append(r[scenario][j])
        categories_old = ordered_categories
        # Plot settings
        ax1.set_ylabel(f"Installed capacity ({unit})")
        handles, labels = (
            ax1.get_legend_handles_labels()
        ) 
        handles_unique = []
        [handles_unique.append(x) for x in handles if x not in handles_unique]
        labels_unique = []
        [labels_unique.append(x) for x in labels if x not in labels_unique]
        ax1.legend(
            reversed(handles_unique),
            reversed(labels_unique),
            bbox_to_anchor=(1, 0.5),
        )
    x_lab = [
        r[scenario][i] - (len(scenarios) - 1) * (barWidth - diff) / 2
        for i in range(0, len(r[scenario]))
    ]
    ax1.set_xticks(x_lab, years)
    ax1.xaxis.set_ticks_position("top")
    # Second x-axis
    x_ticks.sort()
    secax = ax1.secondary_xaxis("bottom")
    secax.set_xticks(
        x_ticks,
        scenarios_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    y_min, y_max = plt.ylim()
    plt.ylim(y_min, y_max * 1.05)

    if "Backup capacities$^{1}$" in ordered_categories:
        x_min, x_max = plt.xlim()
        plt.text(
            x_max * 1.04,
            0,
            f"$^{1}$Post-optimisation estimate",
            fontsize=7,
            verticalalignment="bottom",
            horizontalalignment="left",
        )
    plt.tight_layout()
    plt.savefig(f"{resultdir}/installed_{type}_capacities_{filter}.png")
    plt.close()

    ## 2. Plot installed_{type}_capacities_{filter}_{scen}.png
    # Updated stylesheet for installed capacity scenario
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    for scen in scenarios:
        # Get data
        current_df = aggregate_and_filter_negligible_carriers(
            per_scenario[scen], threshold, type
        )
        # Create Barplot
        current_df.T.plot(kind="bar", stacked=True)

        # Plot settings
        plt.ylabel("Installed capacity (TW)")
        plt.xticks(rotation=0)
        handles, labels = (
            plt.gca().get_legend_handles_labels()
        )  
        plt.legend(
            reversed(handles),
            reversed(labels),
            bbox_to_anchor=(0.5, 1),
            ncol=2,
        ) 

        if "Backup capacities$^{1}$" in ordered_categories:
            y_min, y_max = plt.ylim()
            plt.text(
                -0.5,
                -0.2 * y_max,
                f"$^{1}$Post-optimisation estimate",
                fontsize=7,
                verticalalignment="bottom",
                horizontalalignment="left",
            )
        plt.tight_layout()
        plt.savefig(
            f"{resultdir}/installed_{type}_capacities_{filter}_{scen}.png"
        )


def calculate_installed_heat_capacity(EU27_countries, network, filter):
    """
    Calculates p_nom_opt for all carriers supplying heat and groups
    them into categories defined below. Either for all countries
    (filter = 'All') or for EU27 countries.

    Parameters
    ----------
    EU27_countries : list
        list of relevant countries
    network : pypsa.Network
        network of selected year and scenario
    filter : str
        string for identifier

    Returns
    -------
    pd.Series
        df with p_nom_opt values
    """
    # Map old carrier names to new ones for consistency
    carrier_map = {
        "services urban decentral air heat pump": "Heat Pump",
        "services urban decentral biomass boiler": "Biomass Boiler",
        "services urban decentral gas boiler": "Gas Boiler",
        "services urban decentral micro gas CHP": "CHP",
        "services urban decentral oil boiler": "Oil Boiler",
        "services urban decentral resistive heater": "Resistive Heater",
        "services urban decentral solar thermal": "Solar Thermal",
        "Fischer-Tropsch": "Residual Heat",
        "H2 Electrolysis": "Residual Heat",
        "H2 Fuel Cell": "Residual Heat",
        "Sabatier": "Residual Heat",
        "urban central air heat pump": "Heat Pump",
        "urban central gas CHP": "CHP",
        "urban central gas CHP CC": "CHP",
        "urban central gas boiler": "Gas Boiler",
        "urban central resistive heater": "Resistive Heater",
        "urban central solid biomass CHP": "CHP",
        "urban central solid biomass CHP CC": "CHP",
        "urban central solar thermal": "Solar Thermal",
        "residential rural air heat pump": "Heat Pump",
        "residential rural biomass boiler": "Biomass Boiler",
        "residential rural gas boiler": "Gas Boiler",
        "residential rural ground heat pump": "Heat Pump",
        "residential rural micro gas CHP": "CHP",
        "residential rural oil boiler": "Oil Boiler",
        "residential rural resistive heater": "Resistive Heater",
        "residential rural solar thermal": "Solar Thermal",
        "residential urban decentral air heat pump": "Heat Pump",
        "residential urban decentral biomass boiler": "Biomass Boiler",
        "residential urban decentral gas boiler": "Gas Boiler",
        "residential urban decentral micro gas CHP": "CHP",
        "residential urban decentral oil boiler": "Oil Boiler",
        "residential urban decentral resistive heater": "Resistive Heater",
        "residential urban decentral solar thermal": "Solar Thermal",
        "services rural air heat pump": "Heat Pump",
        "services rural biomass boiler": "Biomass Boiler",
        "services rural gas boiler": "Gas Boiler",
        "services rural ground heat pump": "Heat Pump",
        "services rural micro gas CHP": "CHP",
        "services rural oil boiler": "Oil Boiler",
        "services rural resistive heater": "Resistive Heater",
        "services rural solar thermal": "Solar Thermal",
    }
    network_heat = network.copy()
    network_heat.links.carrier.replace(carrier_map, inplace=True)

    # p_nom_opt for links
    interesting_carriers_links = list(carrier_map.values())
    heat_links = network_heat.links.query(
        "carrier.isin(@interesting_carriers_links)"
    )
    efficiency = heat_links.efficiency
    idx_chp = heat_links.query('bus2.str.contains("heat")').index
    efficiency.loc[idx_chp] = heat_links.loc[idx_chp, "efficiency2"]
    idx_residual_heat = heat_links.query('bus3.str.contains("heat")').index
    efficiency.loc[idx_residual_heat] = heat_links.loc[
        idx_residual_heat, "efficiency3"
    ]
    heat_links.p_nom_opt = heat_links.p_nom_opt * efficiency
    p_nom_all = heat_links.groupby(
        [heat_links.carrier, heat_links.bus1.str[:2]]
    ).p_nom_opt.sum()

    # p_nom_opt for Eur
    p_nom_opt_Eur = p_nom_all.groupby(level=0).sum()

    # p_nom_opt for links EU27
    heat_links_EU27 = heat_links[heat_links.bus1.str[:2].isin(EU27_countries)]
    heat_links_EU27.bus1 = "EU27"
    p_nom_opt_links_EU27 = heat_links_EU27.groupby(
        [heat_links_EU27.carrier, heat_links_EU27.bus1]
    ).p_nom_opt.sum()

    # Return associated p_nom_opt
    if filter == "All":
        return p_nom_opt_Eur / 1e6
    else:
        p_nom_opt_all = pd.concat([p_nom_all, p_nom_opt_links_EU27])
        p_nom_opt_selected = p_nom_opt_all.loc[
            p_nom_opt_all.index.get_level_values(1) == filter
        ].droplevel(1)
        return p_nom_opt_selected / 1e6


def calculate_installed_generation_capacity(EU27_countries, network, filter):
    """
    Calculates p_nom_opt for all carriers supplying electricity and
    groups them into categories defined below. Either for all countries
    (filter = 'All') or for EU27 countries.

    Parameters
    ----------
    EU27_countries : list
        list of relevant countries
    network : pypsa.Network
        network of selected year and scenario
    filter : str
        string for identifier

    Returns
    -------
    pd.Series
        df with p_nom_opt values
    """
    # Map old carrier names to new ones for consistency
    carrier_map = {
        "solar": "Solar",
        "onwind": "Onshore wind",
        "solar rooftop": "Solar",
        "offwind-ac": "Offshore wind",
        "offwind-dc": "Offshore wind",
        "CCGT": "Gas",
        "ror": "Hydro",
        "PHS": "Hydro",
        "lignite": "Lignite",
        "coal": "Coal",
        "nuclear": "Nuclear",
        "hydro": "Hydro",
        "OCGT": "Gas",
        "H2 Fuel Cell": "H2 fuel cell",
        "urban central gas CHP": "Gas",
        "urban central gas CHP CC": "Gas",
        "urban central solid biomass CHP": "Biomass",
        "urban central solid biomass CHP CC": "Biomass",
        "H2 turbine": "H2 turbine",
        "residential rural micro gas CHP": "Gas",
        "services rural micro gas CHP": "Gas",
        "residential urban decentral micro gas CHP": "Gas",
        "services urban decentral micro gas CHP": "Gas",
    }
    network_gen = network.copy()
    network_gen.generators.carrier.replace(carrier_map, inplace=True)

    # p_nom_opt for gen
    interesting_carriers_gen = [
        "Solar",
        "Onshore wind",
        "Offshore wind",
        "Hydro",
    ]
    elec_gen = network_gen.generators.query(
        "carrier.isin(@interesting_carriers_gen)"
    )
    elec_gen_EU27 = elec_gen[elec_gen.bus.str[:2].isin(EU27_countries)]
    elec_gen_EU27.bus = "EU27"
    p_nom_opt_gen = elec_gen.groupby(
        [elec_gen.carrier, elec_gen.bus.str[:2]]
    ).p_nom_opt.sum()

    # p_nom_opt for links
    network_gen.links.carrier.replace(carrier_map, inplace=True)
    interesting_carriers_links = list(
        set([item for key, item in carrier_map.items()])
    )
    elec_links = network_gen.links.query(
        "carrier.isin(@interesting_carriers_links)"
    )
    elec_links.p_nom_opt = elec_links.p_nom_opt * elec_links.efficiency
    p_nom_opt_links = elec_links.groupby(
        [elec_links.carrier, elec_links.bus1.str[:2]]
    ).p_nom_opt.sum()

    # p_nom_opt for Eur
    p_nom_all = pd.concat([p_nom_opt_gen, p_nom_opt_links])
    p_nom_opt_Eur = p_nom_all.groupby(level=0).sum()

    # p_nom_opt for gen EU27
    elec_gen_EU27 = elec_gen[elec_gen.bus.str[:2].isin(EU27_countries)]
    elec_gen_EU27.bus = "EU27"
    p_nom_opt_gen_EU27 = elec_gen_EU27.groupby(
        [elec_gen_EU27.carrier, elec_gen_EU27.bus]
    ).p_nom_opt.sum()

    # p_nom_opt for links EU27
    elec_links_EU27 = elec_links[elec_links.bus1.str[:2].isin(EU27_countries)]
    elec_links_EU27.bus1 = "EU27"
    p_nom_opt_links_EU27 = elec_links_EU27.groupby(
        [elec_links_EU27.carrier, elec_links_EU27.bus1]
    ).p_nom_opt.sum()

    # Return associated p_nom_opt
    if filter == "All":
        return p_nom_opt_Eur / 1e6
    else:
        p_nom_opt_all = pd.concat(
            [p_nom_all, p_nom_opt_gen_EU27, p_nom_opt_links_EU27]
        )
        p_nom_opt_selected = p_nom_opt_all.loc[
            p_nom_opt_all.index.get_level_values(1) == filter
        ].droplevel(1)
        return p_nom_opt_selected / 1e6


def calculate_installed_storage_capacity(EU27_countries, network, filter):
    """
    Calculates p_nom_opt for selected storage technologies specified
    in interesting_carriers_store (stores) below. Either for all
    countries (filter = 'All') or for EU27 countries.

    Parameters
    ----------
    EU27_countries : list
        list of relevant countries
    network : pypsa.Network
        network of selected year and scenario
    filter : str
        string for identifier

    Returns
    -------
    pd.Series
        df with p_nom_opt values
    """
    # Map old carrier names to new ones for consistency
    carrier_map = {
        "H2": "Hydrogen Storage",
        "battery": "Transmission Grid\nBattery Storage",
        "Li ion": "Distribution Grid\nBattery Storage",
        "residential rural water tanks": "Water Tanks",
        "services rural water tanks": "Water Tanks",
        "residential urban decentral water tanks": "Water Tanks",
        "services urban decentral water tanks": "Water Tanks",
        "urban central water tanks": "Water Tanks",
        "home battery": "Distribution Grid\nBattery Storage",
        "hydro": "Hydro",
        "PHS": "Pumped Hydro Storage",
        "gas": "Gas",
    }
    network_store = network.copy()
    network_store.stores.carrier.replace(carrier_map, inplace=True)
    network_store.storage_units.carrier.replace(carrier_map, inplace=True)

    # e_nom_opt for stores
    interesting_carriers_stores = [
        "Hydrogen Storage",
        "Transmission Grid\nBattery Storage",
        "Distribution Grid\nBattery Storage",
        "Water Tanks",
    ]
    stores = network_store.stores.query(
        "carrier.isin(@interesting_carriers_stores)"
    )
    stores_EU27 = stores[stores.bus.str[:2].isin(EU27_countries)]
    stores_EU27.bus = "EU27"
    e_nom_opt_stores = stores.groupby(
        [stores.carrier, stores.bus.str[:2]]
    ).e_nom_opt.sum()
    e_nom_opt_stores_EU27 = stores_EU27.groupby(
        [stores_EU27.carrier, stores_EU27.bus]
    ).e_nom_opt.sum()
    # e_nom_opt for storage units
    interesting_carriers_su = []
    storage_units = network_store.storage_units.query(
        "carrier.isin(@interesting_carriers_su)"
    )
    storage_units["e_nom_opt"] = storage_units["p_nom_opt"].mul(
        storage_units["max_hours"]
    )
    e_nom_opt_su = storage_units.groupby(
        [storage_units.carrier, storage_units.bus.str[:2]]
    ).e_nom_opt.sum()
    # e_nom_opt for storage units EU27
    storage_units_EU27 = storage_units[
        storage_units.bus.str[:2].isin(EU27_countries)
    ]
    storage_units_EU27.bus = "EU27"
    e_nom_opt_su_EU27 = storage_units_EU27.groupby(
        [storage_units_EU27.carrier, storage_units_EU27.bus]
    ).e_nom_opt.sum()

    # e_nom_opt for Eur
    e_nom_all = pd.concat([e_nom_opt_su, e_nom_opt_stores])
    e_nom_opt_Eur = e_nom_all.groupby(level=0).sum()

    # Return associated p_nom_opt
    if filter == "All":
        return e_nom_opt_Eur / 1e6
    else:
        e_nom_opt_all = pd.concat(
            [e_nom_all, e_nom_opt_stores_EU27, e_nom_opt_su_EU27]
        )
        e_nom_opt_selected = e_nom_opt_all.loc[
            e_nom_opt_all.index.get_level_values(1) == filter
        ].droplevel(1)
        return e_nom_opt_selected / 1e6


def aggregate_and_filter_negligible_carriers(
    df, threshold, type, mode="single"
):
    """
    Aggregates rows of df and filters by threshold.

    Parameters
    ----------
    df : pd.DataFrame
        df with data from calculate_installed_capacity
    threshold : float
        float for threshold
    type : str
        string of technology type
    mode : str, optional
        string to determine if one ('single') or multiple scenarios
        ('compare') are plotted, by default "single"

    Returns
    -------
    pd.DataFrame
        df aggregated and filtered
    """
    # Aggregate index
    if type == "generation":
        aggregate_name_to_carriers = {
            "Gas": "Fossils",
            "Lignite": "Fossils",
            "Coal": "Fossils",
        }
    else:
        aggregate_name_to_carriers = {}

    data_columns = [
        col
        for col in df.columns
        if "carrier" not in col and not col.strip() == ""
    ]
    df["aggregate_carrier"] = df.index.map(
        lambda x: aggregate_name_to_carriers.get(x, x)
    )

    # Filter df
    max_sum_over_year = df[data_columns].sum(axis=0).max()
    for column in data_columns:
        df[column] = df[column].apply(
            lambda x: x if x / max_sum_over_year >= threshold else 0
        )
    df = df.loc[~(df[data_columns] == 0).all(axis=1)]

    df_grouped = df.groupby(by="aggregate_carrier", dropna=False).sum()
    # Ensure backup capacities are on top of graph
    if ("Backup capacities$^{1}$" in df.index) & (mode == "single"):
        idx_backup = df_grouped.index.get_loc("Backup capacities$^{1}$")
        backup_capas = df_grouped.loc["Backup capacities$^{1}$", :]
        df_grouped = pd.concat(
            [
                df_grouped.iloc[:idx_backup, :],
                df_grouped.iloc[idx_backup + 1 :, :],
            ]
        )
        df_grouped.loc["Backup capacities$^{1}$", :] = backup_capas

    return df_grouped


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG" # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    years = ["2030", "2035", "2040", "2045", "2050"]
    all_years = ["2020", "2025", "2030", "2035", "2040", "2045", "2050"]
    # insert run names for scenarios here:
    runs = {
        "scenario_1": "run_name_1", 
        "scenario_2": "run_name_2", 
        "scenario_3": "run_name_3", 
        "scenario_4": "run_name_4",
    } # analysis on back up capacities are only available for the scenario names of national scenarios "CN" and "SN"

    # User configuration for output data:
    evaluation_name = "analysis_results"
    timestamp = datetime.now().strftime("%Y%m%d")
    full_name = evaluation_name + "_" + timestamp

    # Directories
    main_dir = Path(os.getcwd()).parent
    resultdir = (
        Path(main_dir) / full_name
    )  # folder where Excel files and graphs are stored
    if not os.path.exists(resultdir):
        os.makedirs(resultdir)

    KPI_dir = resultdir / "KPIs"
    if not os.path.exists(KPI_dir):
        os.mkdir(KPI_dir)
    scenarios = list(runs.keys())

    # load all network files from results folder into a nested dictionary
    networks_year = {}
    for year in years:
        curr_networks = {}
        for scen in scenarios:
            run_name = runs[scen]
            path_to_networks = Path(
                f"{main_dir}/results/{run_name}/postnetworks"
            )
            n = pypsa.Network(
                path_to_networks / f"{sector_opts}_{year}.nc"
            )
            curr_networks.update({scen: n})

        networks_year.update({year: curr_networks})
    backup_capas = True
    call_installed_capacity_plot(
        networks_year, years, scenarios, KPI_dir, backup_capas
    )
