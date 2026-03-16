import os
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pypsa

# Stylesheet for plot
plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")


def get_transport_demand_plot(networks, years, sel_scen, demand_resultdir):
    """
    Creates Plot and Excel with transport-demand of fossil energy
    sources and EV for each year and the selected scenario.

    Parameters
    ----------
    networks : dict
        dict with postnetworks data
    years : list of str
        list of considererd years
    sel_scen : str
        string of selected scenario
    demand_resultdir : str or Path
        path of resultdirectory

    Returns
    -------
    None
    """

    # Transport fossil energy sources and energy
    transport_loads = [
        ["aviation", "kerosene"],
        ["shipping", "oil"],
        ["shipping", "methanol"],
        ["land transport", "oil"],
        ["land transport", "EV"],
        ["land transport", "fuel cell"],
    ]
    transport_load_name = [
        "kerosene for aviation",
        "shipping oil",
        "shipping methanol",
        "land transport oil",
        "land transport EV",
        "land transport fuel cell",
    ]
    legend_names = [
        "Kerosene/SAF",
        "Shipping oil",
        "Shipping methanol",
        "Land transp. oil",
        "Land transp. EV",
        "Land transp. fuel cell",
    ]

    # Initial dataframe
    df_index = pd.MultiIndex.from_tuples(
        transport_loads, names=["Mode", "carrier"]
    )
    df = pd.DataFrame(index=df_index, columns=years)

    # Calculation per year
    for year in years:
        # Connect to network and get snapshots
        network_transport = networks[year][sel_scen]
        snapshots = network_transport.snapshot_weightings.generators
        snapshot_hours = network_transport.snapshot_weightings.generators.sum()

        # Calculation for multiindex
        my_i = 0
        for item in transport_loads:
            # Calculate transport demand
            curr_val_1 = (
                network_transport.loads.p_set[
                    network_transport.loads.p_set.index.str.contains(
                        transport_load_name[my_i]
                    )
                ]
                .sum()
                .sum()
                * 1e-6
                * snapshot_hours
            )
            curr_val_2 = (
                network_transport.loads_t.p_set.mul(snapshots, axis=0)
                .sum()[
                    network_transport.loads_t.p_set.sum().index.str.contains(
                        transport_load_name[my_i]
                    )
                ]
                .sum()
                * 1e-6
            )
            my_i = my_i + 1
            if curr_val_1 > 0:
                df.loc[(item[0], item[1]), year] = curr_val_1
            else:
                df.loc[(item[0], item[1]), year] = curr_val_2
            # set both values to 0 to avoid having accidentally a larger value
            # from the previous loop
            del curr_val_2, curr_val_1

        # Plot with settings
        ax = df.T.plot(kind="bar", figsize=(4.72, 4.33), stacked=True)
        plt.xticks(rotation=0)
        ax.legend(legend_names, bbox_to_anchor=(0.5, 1), ncol=2)
        ax.set_ylabel("Energy demand (TWh/a)")
        plt.tight_layout()

        # Save plot and excel
        plt.savefig(f"{demand_resultdir}/Transport_demand_exogenous.png")
        df.to_excel(f"{demand_resultdir}/Transport_demand_exogenous.xlsx")


if __name__ == "__main__":
    # User configuration for input data
    years = ["2030", "2035", "2040", "2045", "2050"]
    sel_scen = "scenario_1"
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
                path_to_networks
                / f"elec_s_62_lv99__2190SEG-T-H-B-I-A_{year}.nc"
            )
            curr_networks.update({scen: n})

        networks_year.update({year: curr_networks})

    get_transport_demand_plot(networks_year, years, sel_scen, resultdir)
