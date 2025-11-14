import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pypsa
from matplotlib import pyplot as plt

from agora_import_calculator import AgoraImportCalculator

# Stylesheet for colors
plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
COLORS = plt.rcParams["axes.prop_cycle"].by_key()["color"]




def analyze_imports(
    networks_year_dict: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    import_resultdir: Path,
):
    """
    Creates plots and excel files of imported energy to europe for
    every year. Relevant sets are 'H2_derivate_import', 'H2_import'
    and 'energy_import'. Files include:
        - import per scenario
        - import for comparison of scenarios
        - excel files per scenario

    Parameters
    ----------
    networks_year_dict : Dict[str, Dict[str, pypsa.Network]]
        dict with postnetworks data
    years : List[str]
        list of considererd years
    import_resultdir : Path
        path of resultdirectory

    Returns
    -------
    None
    """

    # Import analysis sets
    sets = {
        "H2_derivate_import": [
            "import pipeline-H2",
            "import shipping-H2",
            "import pipeline-syngas",
            "import shipping-syngas",
            "synfuel",
        ],
        "H2_import": ["import pipeline-H2", "import shipping-H2"],
        "energy_import": [
            "import pipeline-H2",
            "import shipping-H2",
            "import pipeline-syngas",
            "import shipping-syngas",
            "synfuel",
            "coal",
            "oil",
            "uranium",
            "import lng gas",
            "import pipeline gas",
        ],
    }
    # Run routine
    for chosen_set in sets:
        plot_excel_imports(
            networks_year_dict,
            chosen_set,
            sets[chosen_set],
            years,
            import_resultdir,
        )


def plot_excel_imports(
    networks_year_dict: Dict[str, Dict[str, pypsa.Network]],
    chosen_set_name: str,
    chosen_set: List[str],
    years: List[str],
    import_resultdir: Path,
):
    """
    Calculates data with AgoraImportCalculator and calls plot- and
    excel-functions.

    Parameters
    ----------
    networks_year_dict : Dict[str, Dict[str, pypsa.Network]]
        dict with postnetworks data
    chosen_set_name : str
        string name of chosen set (like 'energy_import')
    chosen_set : List[str]
        list of chosen sets
    years : List[str]
        list of considered years
    import_resultdir : Path
        path of resultdirectory

    Returns
    -------
    None
    """

    # Calculate data with AgoraImportCalculator
    network_dict = {}
    for year in networks_year_dict:
        for scenario in networks_year_dict[year]:
            if scenario not in network_dict:
                network_dict[scenario] = {}
            network = networks_year_dict[year][scenario]
            agora_import_analyzer = AgoraImportCalculator(
                network, chosen_set, year, scenario
            )
            network_dict[scenario][year] = agora_import_analyzer

    # Save scenario- and all-plots
    for scenario in network_dict:
        subsets_plotter(
            scenario,
            network_dict[scenario],
            chosen_set_name,
            chosen_set,
            years,
            import_resultdir,
        )
    all_in_one_plotter(
        network_dict, chosen_set_name, chosen_set, years, import_resultdir
    )

    # Save excel
    save_as_excel(network_dict, import_resultdir)




def subsets_plotter(
    scenario_name: str,
    network_dict: Dict[str, AgoraImportCalculator],
    chosen_set_name: str,
    chosen_set: List[str],
    years: List[str],
    output_dir: Path,
):
    """
    Plot for import per scenario.

    Parameters
    ----------
    scenario_name : str
        string of current scenario (like 'CE')
    network_dict : Dict[str, AgoraImportCalculator]
        dict of scenarios with calculated data per year
    chosen_set_name : str
        string name of chosen set (like 'energy_import')
    chosen_set : List[str]
        list of chosen sets
    years : List[str]
        list of considererd years
    output_dir : Path
        path of resultdirectory

    Returns
    -------
    None
    """

    # Updated stylesheet for operational costs
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    # Initial plot settings
    fig = plt.figure()
    bar_width = 0.5
    index = np.arange(len(network_dict))
    plt.xticks(index, years)

    # Set color map
    colors = COLORS.copy()
    color_mapping = {}
    for current_set in chosen_set:
        color = colors.pop(0)
        color_mapping[current_set] = color

    # Plot
    bottom_values = len(index) * [0]
    for current_set in chosen_set:
        # Get data
        y_values = []
        for year in network_dict:
            y_values.append(network_dict[year].get_total([current_set]))
        # Create Barchart
        plt.bar(
            index,
            y_values,
            width=bar_width,
            bottom=bottom_values,
            label=current_set,
            color=color_mapping[current_set],
        )
        bottom_values = [y1 + y2 for y1, y2 in zip(bottom_values, y_values)]

    # Plot settings
    plt.xlabel("")
    plt.ylabel("Imported energy (TWh)")
    handles, labels = plt.gca().get_legend_handles_labels()
    plt.legend(
        reversed(handles), reversed(labels), bbox_to_anchor=(0.5, 1), ncol=2
    )
    y_min, y_max = plt.ylim()
    plt.ylim(y_min, y_max * 1.05)
    plt.tight_layout()
    fig.savefig(f"{output_dir}/plot_{scenario_name}_{chosen_set_name}.png")
    plt.close()


def all_in_one_plotter(
    network_dict: Dict[str, Dict[str, AgoraImportCalculator]],
    chosen_set_name: str,
    chosen_set: List[str],
    years: List[int],
    output_dir: Path,
):
    """
    Plot to compare imports of scenarios.

    Parameters
    ----------
    network_dict : Dict[str, Dict[str, AgoraImportCalculator]]
        dict of scenarios with calculated data per year
    chosen_set_name : str
        string name of chosen set (like 'energy_import')
    chosen_set : List[str]
        list of chosen sets
    years : List[int]
        list of considererd years
    output_dir : Path
        path of resultdirectory

    Returns
    -------
    None
    """

    # Updated stylesheet for all in one
    plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")

    # Initial plot settings and variables
    fig, ax1 = plt.subplots()
    scenarios = network_dict.keys()
    scenarios_use = list(scenarios) * len(years)
    first_scenario, first_value = next(iter(network_dict.items()))
    r = {}
    x_ticks = []
    # Bar width
    barWidth = 0.8 / len(network_dict)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars on x axis
    for scenario in network_dict.keys():
        r[scenario] = [x + i * barWidth + 0.3 for x in r0]
        i = i + 1

    # Create the stacked bar chart
    for scenario in network_dict.keys():
        for j in range(0, len(r[scenario])):
            r[scenario][j] = np.round(r[scenario][j], 1)
        keys = chosen_set
        network_dict_scenario = network_dict[scenario]
        diff = 0.0115
        bottoms = np.zeros(len(years))

        for current_set in chosen_set:
            # Set index and get data
            index = chosen_set.index(current_set)
            y_values = []
            for year in network_dict_scenario:
                y_values.append(
                    network_dict_scenario[year].get_total([current_set])
                )

            if i > 0:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        y_values,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[index],
                        label=keys[index],
                    )  # , edgecolor='black',index_mapping[scenario]
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
                        label=keys[index],
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
        ax1.set_ylabel("Imported energy (TWh)")
        handles, labels = (
            ax1.get_legend_handles_labels()
        )
        ax1.legend(
            reversed(handles), reversed(labels), bbox_to_anchor=(1, 0.5)
        )
    x_lab = [
        r[scenario][i] - (len(network_dict) - 1) * (barWidth - diff) / 2
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
    fig.savefig(f"{output_dir}/plot_all_{chosen_set_name}.png")
    plt.close()


def save_as_excel(
    network_dict: Dict[str, Dict[str, AgoraImportCalculator]], output_dir
):
    """
    Save excel files.

    Parameters
    ----------
    network_dict : Dict[str, Dict[str, AgoraImportCalculator]]
        dict of scenarios with calculated data per year
    output_dir : _type_
        path of resultdirectory

    Returns
    -------
    None
    """

    # Get data and write excel
    for scenario in network_dict:
        writer = pd.ExcelWriter(
            f"{output_dir}/imports_{scenario}_TWh.xlsx", engine="openpyxl"
        )
        for year in network_dict[scenario]:
            df = network_dict[scenario][year].import_gens_series_TWh
            df.to_excel(writer, sheet_name=year)
        writer.close()


if __name__ == "__main__":
    # User configuration for input data:
    years = ["2030", "2035", "2040", "2045", "2050"]
    # insert run names for scenarios here:
    runs = {
        "scenario_1": "run_name_1",
        "scenario_2": "run_name_2",
        "scenario_3": "run_name_3",
        "scenario_4": "run_name_4",
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
    networks = {}
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

        networks.update({year: curr_networks})

    import_resultdir = (
        resultdir / "Import"
    )  # folder where Excel files and graphs are stored
    if not os.path.exists(import_resultdir):
        os.makedirs(import_resultdir)

    # Save plots and excel
    analyze_imports(networks, years, import_resultdir)
