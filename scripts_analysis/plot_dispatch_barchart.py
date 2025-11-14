import os
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa



def plot_dispatch_barchart(resultdir, networks_year, runs, years, KPI):
    """
    Creates barchart to compare the dispatch of a technology group
    (flexibilities) to compare scenarios by years.

    Parameters
    ----------
    resultdir : str or Path
        path of resultdirectory
    networks_year : dict
        dict with postnetworks data
    runs : dict
        dict of scenarios with associated folders
    years : list
        list of considered years
    KPI : str
        string of KPI ('flexibility')

    Returns
    -------
    None
    """

    # Stylesheet for plot + colors
    plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")

    if KPI == "flexibility":
        dict_data = calculate_flexibilty_dispatch(networks_year, runs, years)
        scalar = 1e-6
    else:
        return
    ## Transform dict
    dict_data = {key: df * scalar for key, df in dict_data.items()}

    fig, ax = plt.subplots(figsize=(6.2, 4))

    # Position of bars for dict_df[first_scenario] on x axis
    scenarios = dict_data.keys()
    scenarios_use = list(scenarios) * len(years)
    first_scenario, first_value = next(iter(dict_data.items()))
    r = {}
    x_ticks = []
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # Plot
    barWidth = 0.8 / len(dict_data)
    r0 = np.arange(len(years))
    i = 0
    for scenario, df in dict_data.items():
        r[scenario] = [x + i * barWidth + 0.3 for x in r0]
        i = i + 1

    for scenario in dict_data.keys():
        for j in range(0, len(r[scenario])):
            r[scenario][j] = np.round(r[scenario][j], 1)
        keys = dict_data[scenario].index

        # Barplot for one scenario with bottoms
        diff = 0.0115
        bottoms = np.zeros(len(years))
        for i in range(0, len(keys)):
            arr = np.array(dict_data[scenario].loc[keys[i]])
            if i > 0:
                if scenario == first_scenario:
                    ax.bar(
                        r[scenario],
                        arr,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=colors[i],
                        label=keys[i],
                    )
                else:
                    ax.bar(
                        r[scenario],
                        arr,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=colors[i],
                    )
                bottoms = np.add(bottoms, arr)
            else:
                if scenario == first_scenario:
                    ax.bar(
                        r[scenario],
                        arr,
                        width=barWidth - diff,
                        color=colors[i],
                        label=keys[i],
                    )
                else:
                    ax.bar(
                        r[scenario],
                        arr,
                        width=barWidth - diff,
                        color=colors[i],
                    )
                bottoms = np.add(bottoms, arr)

        for j in range(0, len(r[scenario])):
            if r[scenario][j] not in x_ticks:
                x_ticks.append(r[scenario][j])

        if KPI == "flexibility":
            ax.set_ylabel(
                "Electricity supply (TWh)"
            )
        else:
            return
        handles, labels = (
            ax.get_legend_handles_labels()
        )
        ax.legend(reversed(handles), reversed(labels), bbox_to_anchor=(1, 0.5))
    # Final settings
    x_lab = [
        r[scenario][i] - (len(dict_data) - 1) * (barWidth - diff) / 2
        for i in range(0, len(r[scenario]))
    ]
    ax.set_xticks(x_lab, years)
    ax.xaxis.set_ticks_position("top")
    # Second x-axis
    x_ticks.sort()
    secax = ax.secondary_xaxis("bottom")
    secax.set_xticks(
        x_ticks,
        scenarios_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    secax.tick_params(labelsize=10)

    plt.tight_layout()
    if KPI == "flexibility":
        plt.savefig(resultdir / f"{KPI}_dispatch.png")
    plt.close()




def calculate_flexibilty_dispatch(networks_year, runs, years):
    """
    Calculates the annual dispatch of technologies providing
    flexibility to the energy system.

    Parameters
    ----------
    networks_year : dict
        dict with postnetworks data
    runs : dict
        dict of scenarios with associated folders
    years : list
        list of considered years

    Returns
    -------
    dict
        dict with dfs of offshore capacity for every scenario
    """
    flex_carriers = {
        "V2G": "Vehicle-to-grid",
        "battery discharger": "Transmission grid\nbattery storage",
        "home battery discharger": "Home battery storage",
        "OCGT": "Gas turbine\n(OCGT, CCGT, allam cycle)",
        "CCGT": "Gas turbine\n(OCGT, CCGT, allam cycle)",
        "allam": "Gas turbine\n(OCGT, CCGT, allam cycle)",
        "H2 turbine": "H$_{2}$ turbine",
        "H2 Fuel Cell": "H$_{2}$ fuel cell",
        "services urban decentral micro gas CHP": "CHP (gas, biomass)",
        "urban central gas CHP": "CHP (gas, biomass)",
        "urban central gas CHP CC": "CHP (gas, biomass)",
        "urban central solid biomass CHP": "CHP (gas, biomass)",
        "urban central solid biomass CHP CC": "CHP (gas, biomass)",
        "residential rural micro gas CHP": "CHP (gas, biomass)",
        "residential urban decentral micro gas CHP": "CHP (gas, biomass)",
        "services rural micro gas CHP": "CHP (gas, biomass)",
    }
    dict_scen = dict()

    for scenario in runs.keys():
        df_flex_scen = pd.DataFrame()

        for year in years:
            network_flex = networks_year[year][scenario].copy()
            network_flex.links.carrier.replace(flex_carriers, inplace=True)
            # Extract relevant components and calculate their annual dispatch
            flex_idx = network_flex.links.query(
                f"carrier.isin({list(flex_carriers.values())})"
            ).index
            grouper = network_flex.links.query(
                f"carrier.isin({list(flex_carriers.values())})"
            ).carrier
            nodal_dispatch = (
                network_flex.links_t.p1.loc[:, flex_idx]
                .mul(network_flex.snapshot_weightings.generators, axis=0)
                .sum()
            )
            df_flex_scen[year] = -nodal_dispatch.groupby(grouper).sum()
        dict_scen[scenario] = df_flex_scen

    return dict_scen


if __name__ == "__main__":
    # User configuration for input data
    years = ["2030", "2035", "2040", "2045", "2050"]
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    runs = {
        "scenario_1": "run_name_1",
        "scenario_2": "run_name_2",
        "scenario_3": "run_name_3",
        "scenario_4": "run_name_4",
    }

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

    KPI_dir = resultdir / "KPIs"
    if not os.path.exists(KPI_dir):
        os.mkdir(KPI_dir)
    # Possible: ['flexibility']
    plot_dispatch_barchart(KPI_dir, networks_year, runs, years, "flexibility")
