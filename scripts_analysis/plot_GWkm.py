import os
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

from line_usage import calculate_utilization



def plot_TWkm_all_carriers(
    networks_year, scenario_colors, scenarios, years, resultdir
):
    """
    Creates TWkm (Installed capacity x Length) Plots for the carriers
    'Electricity', 'H2', 'CO2' and 'Gas'.
    Relevant clusters are defined below.

    Parameters
    ----------
    networks_year : dict
        dict with postnetworks data
    scenario_colors : dict
        list of colors for scenarios
    scenarios : list of str
        list of scenarios
    years : list of int
        list of considered years
    resultdir : str or Path
        path of resultdirectory

    Results
    -------
    None
    """
    europe_list = {
        "europe": [
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
    }
    eu27_list = {
        "eu27": [
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
        ]
    }
    benelux_list = {
        "benelux": [
            "BE1 0",
            "NL1 0",
            "NL1 1",
            "DE1 1",
            "DE1 2",
            "DE1 3",
            "DK1 0",
            "LU1 0",
        ]
    }
    balticum_list = {
        "balticum": [
            "EE6 0",
            "LT6 0",
            "LV6 0",
            "PL1 2",
            "PL1 0",
            "PL1 1",
            "PL1 2",
            "PL1 3",
            "PL1 4",
        ]
    }

    plot_calc_TWkm(
        networks_year,
        scenario_colors,
        scenarios,
        years,
        resultdir,
        europe_list,
    )
    plot_calc_TWkm(
        networks_year, scenario_colors, scenarios, years, resultdir, eu27_list
    )
    plot_calc_TWkm(
        networks_year,
        scenario_colors,
        scenarios,
        years,
        resultdir,
        benelux_list,
    )
    plot_calc_TWkm(
        networks_year,
        scenario_colors,
        scenarios,
        years,
        resultdir,
        balticum_list,
    )


def plot_calc_TWkm(
    networks_year, scenario_colors, scenarios, years, resultdir, countries_list
):
    """
    Calls calculation and plot functions.

    Parameters
    ----------
    networks_year : dict
        dict with postnetworks data
    scenario_colors : list
        list of colors for scenarios
    scenarios : list
        list of scenarios
    years : list
        list of considered years
    resultdir : pathlib.Path
        path of resultdirectory
    countries_list : dict
        dict of cluster ({clustername: [list]})

    Returns
    -------
    None
    """
    # Init dict
    df_TWkm_elec = {}
    df_TWkm_H2 = {}
    df_TWkm_CO2 = {}
    df_TWkm_gas = {}

    # Extract key and list
    key = list(countries_list.keys())
    countries_list = countries_list[key[0]]

    # Calculate TWkm for carriers ('elec', 'H2', 'CO2', 'Gas').
    # Stacked ('Gas') is for stacked barchart
    stacked = True
    for scen in scenarios:
        df_TWkm_elec[scen] = calculate_TWkm_elec_all_years(
            networks_year, scen, years, countries_list
        )
        df_TWkm_H2[scen] = calculate_TWkm_H2_all_years(
            networks_year, scen, years, countries_list
        )
        df_TWkm_CO2[scen] = calculate_TWkm_CO2_all_years(
            networks_year, scen, years, countries_list
        )
        df_TWkm_gas[scen] = calculate_TWkm_gas_all_years(
            networks_year, scen, years, countries_list, stacked
        )

    # Filenames
    save_name_TWkm = resultdir / (f"TWkm_elec_{key[0]}.png")
    save_name_TWkm_H2 = resultdir / (f"TWkm_H2_{key[0]}.png")
    save_name_TWkm_CO2 = resultdir / (f"TWkm_CO2_{key[0]}.png")
    save_name_TWkm_gas = resultdir / (f"TWkm_gas_{key[0]}.png")

    # Final plot
    plot_TWkm(
        df_TWkm_elec, save_name_TWkm, "Electricity", scenario_colors, years
    )
    plot_TWkm(df_TWkm_H2, save_name_TWkm_H2, "H2", scenario_colors, years)
    plot_TWkm(df_TWkm_CO2, save_name_TWkm_CO2, "CO2", scenario_colors, years)

    if stacked == False:
        plot_TWkm(
            df_TWkm_gas, save_name_TWkm_gas, "Gas", scenario_colors, years
        )
    else:
        plot_TWkm_stacked(df_TWkm_gas, save_name_TWkm_gas, scenarios, years)




def plot_TWkm(dict_df, save_file, carrier, color_scheme, years):
    """
    Plots TWkm for each scenario each year next to each other.

    Parameters
    ----------
    dict_df : dict
        dict with data per scenario
    save_file : pathlib.Path
        path/name of stored file
    carrier : str
        string of carrier ('Electricity', 'H2', 'CO2')
    color_scheme : dict
        list of scenario colors
    years : list
        list of considered years

    Returns
    -------
    None
    """
    # Stylesheet for plot_TWkm
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    # Initial plot settings and variables
    fig, ax = plt.subplots()
    r = {}
    # Position of bars for dict_df[first_scenario] on x axis
    first_scenario, first_value = next(iter(dict_df.items()))
    num_scenario = len(dict_df)
    # Bar width
    barWidth = 0.8 / num_scenario
    r0 = np.arange(len(dict_df[first_scenario].columns))
    x_ticks_cap = []
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in dict_df.items():
        r[scenario] = [x + i * barWidth for x in r0]
        i = i + 1
        x_ticks_cap = x_ticks_cap + r[scenario]

    # Create barplot
    if carrier == "Electricity":
        for scenario, df in dict_df.items():
            ax.bar(
                r[scenario],
                df.loc["AC"] + df.loc["DC"],
                color=color_scheme[scenario],
                width=barWidth,
                label=scenario,
            )
    else:
        for scenario, df in dict_df.items():
            ax.bar(
                r[scenario],
                df.loc[carrier],
                color=color_scheme[scenario],
                width=barWidth,
                label=scenario,
            )

    # Plot settings
    ax.set_ylabel("Installed Capacity x Length (TWkm)")
    ax.set_xticks(
        [
            r + (num_scenario - 1) / 2 * barWidth
            for r in range(len(dict_df[first_scenario].columns))
        ],
        dict_df[first_scenario].columns,
    )
    scenario_use = [scen for scen in dict_df.keys() for _ in range(len(years))]
    ax.xaxis.set_ticks_position("top")
    # Second x-axis
    sec_ax = ax.secondary_xaxis("bottom")
    sec_ax.set_xticks(
        x_ticks_cap,
        scenario_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    y_min, y_max = plt.ylim()
    plt.ylim(y_min, y_max * 1.05)
    plt.tight_layout()
    fig.savefig(save_file)
    plt.close()


def plot_TWkm_stacked(dict_df, save_file, scenarios, years):
    """
    Creates same plot as plot_TWkm but with stacked barchart.

    Parameters
    ----------
    dict_df : dict
        dict with data per scenario
    save_file : pathlib.Path
        path/name of stored file
    scenarios : list
        list of scenarios
    years : list
        list of relevant years

    Returns
    ------
    None
    """
    # Updated stylesheet for installed capacity scenario
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    COLORS = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # Initial plot settings and variables
    fig, ax1 = plt.subplots()
    scenarios_use = scenarios * len(years)
    first_scenario = next(iter(scenarios))
    r = {}
    x_ticks = []
    # Bar width
    barWidth = 0.8 / len(scenarios)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars on x axis
    for scenario in scenarios:
        r[scenario] = [x + i * barWidth + 0.3 for x in r0]
        i = i + 1

    # Create the stacked bar chart
    for scenario in scenarios:
        for j in range(0, len(r[scenario])):
            r[scenario][j] = np.round(r[scenario][j], 1)

        # Plot
        diff = 0.0115
        bottoms = np.zeros(len(years))
        pipelines = dict_df[scenario].index.tolist()
        for pipe in pipelines:
            # Set index and get data
            index = pipelines.index(pipe)
            y_values = dict_df[scenario].loc[pipe]

            if i > 0:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=pipelines[index],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[index],
                    )
                bottoms = np.add(bottoms, y_values)
            else:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=pipelines[index],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        width=barWidth - diff,
                        color=COLORS[index],
                    )
                bottoms = np.add(bottoms, y_values)

        for j in range(0, len(r[scenario])):
            if r[scenario][j] not in x_ticks:
                x_ticks.append(r[scenario][j])

        # Plot settings
        ax1.set_ylabel("Installed Capacity x Length (TWkm)")
        handles, labels = (
            ax1.get_legend_handles_labels()
        )
        ax1.legend(
            reversed(handles), reversed(labels), bbox_to_anchor=(0.5, 1.1)
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
    plt.tight_layout()
    plt.savefig(save_file)
    plt.close()




def filter_substrings(df, list):
    """
    Filters network.links bus0 and bus1 by contained listnames.

    Parameters
    ----------
    df : pandas.DataFrame
        df network.links
    list : list of str
        list of cluster names

    Returns
    -------
    pandas.DataFrame
        df filtered
    """
    # Filter bus by country names in list
    mask_bus0 = df["bus0"].str.contains("|".join(list), case=False, na=False)
    mask_bus1 = df["bus1"].str.contains("|".join(list), case=False, na=False)
    mask = mask_bus0 | mask_bus1
    df = df[mask]
    return df


def calculate_TWkm(net, list):
    """
    Help-function for electricity. Calculates ac and dc.

    Parameters
    ----------
    net : pypsa.Network
        network of one year and scenario
    list : list of str
        list of cluster names

    Returns
    -------
    float
        total AC capacity multiplied by line length in TWkm
    float
        total DC capacity multiplied by link length in TWkm
    """
    # Connect to network
    links = net.links.query('carrier=="DC" & ~reversed')
    links = filter_substrings(links, list)
    # Calculate data
    dc_TWkm = (links.length * links.p_nom_opt).sum()
    lines = net.lines
    lines = filter_substrings(lines, list)
    ac_TWkm = (lines.length * lines.s_nom_opt).sum()
    return ac_TWkm, dc_TWkm


def calculate_TWkm_H2_all_years(networks, scenario, years, countries_list):
    """
    Calculates TWkm for H2 for one scenario and all years.

    Parameters
    ----------
    networks : dict
        dict with postnetworks data
    scenario : str
        string of current scenario
    years : list of str
        list of considered years
    countries_list : list of str
        list of clusters

    Returns
    -------
    pd.DataFrame
        df with TWkm
    """
    H2_TWkm = []
    for year in years:
        this_network = networks[year][scenario]
        # Transform dataframe
        links_H2_pipes = this_network.links.query(
            'carrier.str.contains("H2 pipeline") & ~reversed'
        )
        links_H2_pipes = filter_substrings(links_H2_pipes, countries_list)
        MWkm_H2 = (links_H2_pipes.p_nom_opt * links_H2_pipes.length).sum()
        H2_TWkm = H2_TWkm + [MWkm_H2 / 1e6]
    df_TWkm = pd.DataFrame([H2_TWkm], columns=years, index=["H2"])
    return df_TWkm


def calculate_TWkm_CO2_all_years(networks, scenario, years, countries_list):
    """
    Calculates TWkm for CO2 for one scenario and all years.

    Parameters
    ----------
    networks : dict
        dict with postnetworks data
    scenario : str
        string of current scenario
    years : list of str
        list of considered years
    countries_list : list of str
        list of clusters

    Returns
    -------
    pd.DataFrame
        df with TWkm
    """
    CO2_TWkm = []
    for year in years:
        this_network = networks[year][scenario]
        links_CO2_pipes = this_network.links.query(
            'carrier.str.contains("CO2 pipeline") & ~reversed'
        )
        links_CO2_pipes = filter_substrings(links_CO2_pipes, countries_list)
        MWkm_CO2 = (links_CO2_pipes.p_nom_opt * links_CO2_pipes.length).sum()
        CO2_TWkm = CO2_TWkm + [MWkm_CO2 / 1e6]
    df_TWkm = pd.DataFrame([CO2_TWkm], columns=years, index=["CO2"])
    return df_TWkm


def calculate_TWkm_gas_all_years(
    networks, scenario, years, countries_list, stacked, threshold=-1.0
):
    """
    Calculates TWkm for gas pipelines for one scenario and all years.

    Parameters
    ----------
    networks : dict
        dict with postnetworks data
    scenario : str
        string of current scenario
    years : list of str
        list of considered years
    countries_list : list of str
        list of clusters
    stacked : bool
        whether to return data grouped by carrier type
    threshold : float, optional
        float that gives the minimum utilization rate that should be
        used, by default -1.0

    Returns
    -------
    pd.DataFrame
        df with TWkm
    """
    gas_TWkm = pd.DataFrame()
    for year in years:
        this_network = networks[year][scenario]
        this_network = calculate_utilization(this_network)
        links_gas_pipes = this_network.links.query(
            'carrier.str.contains("gas pipeline") & ~reversed'
        )
        links_gas_pipes = links_gas_pipes.query("mean_util>@threshold")
        links_gas_pipes = filter_substrings(links_gas_pipes, countries_list)

        # use potential threshold for carrier mapping:
        if threshold > 0:
            threshold_string = f"\nabove {threshold*100}% average utilisation"
        else:
            threshold_string = ""
        carrier_map = {
            "gas pipeline": (
                f"Existing/endogenous gas pipelines{threshold_string}"
            ),
            "gas pipeline new": (
                f"Existing/endogenous gas pipelines{threshold_string}"
            ),
            "gas pipeline tyndp": (
                f"TYNDP gas pipeline projects{threshold_string}"
            ),
        }
        # Calculate MWkm
        MWkm = links_gas_pipes.p_nom_opt * links_gas_pipes.length
        if stacked == False:
            MWkm_gas = MWkm.sum()
            gas_TWkm[year] = [MWkm_gas / 1e6]
            gas_TWkm.index = ["Gas"]
        else:
            links_gas_pipes.replace(carrier_map, inplace=True)
            links_gas_pipes["MWkm"] = MWkm
            carrier_MWkm = links_gas_pipes[["carrier", "MWkm"]]
            carrier_MWkm.loc[
                carrier_MWkm["carrier"] == "gas pipeline new", "carrier"
            ] = "gas pipeline"
            MWkm_gas = carrier_MWkm.groupby("carrier").sum()
            gas_TWkm[year] = MWkm_gas / 1e6
    return gas_TWkm


def calculate_TWkm_elec_all_years(networks, scenario, years, countries_list):
    """
    Calculates TWkm for Electricity for one scenario and all years.

    Parameters
    ----------
    networks : dict
        dict with postnetworks data
    scenario : str
        string of current scenario
    years : list of str
        list of considered years
    countries_list : list of str
        list of clusters

    Returns
    -------
     pd.DataFrame
        df with TWkm
    """
    ac_TWkm = []
    dc_TWkm = []
    for year in years:
        this_network = networks[year][scenario]
        ac_MWkm, dc_MWkm = calculate_TWkm(this_network, countries_list)
        ac_TWkm = ac_TWkm + [ac_MWkm / 1e6]
        dc_TWkm = dc_TWkm + [dc_MWkm / 1e6]
    df_TWkm = pd.DataFrame(
        [ac_TWkm, dc_TWkm], columns=years, index=["AC", "DC"]
    )
    return df_TWkm


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    years = ["2030", "2035", "2040", "2045", "2050"]
    runs = {
        "scenario_1": "run_name_1",
        "scenario_2": "run_name_2",
        "scenario_3": "run_name_3",
        "scenario_4": "run_name_4",
    }

    scenario_colors = {
        "scenario_1": "#39C1CD",
        "scenario_2": "#F58220",
        "scenario_3": "#179C7D",
        "scenario_4": "#854006",
    }
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

    plot_TWkm_all_carriers(
        networks_year, scenario_colors, scenarios, years, resultdir
    )
