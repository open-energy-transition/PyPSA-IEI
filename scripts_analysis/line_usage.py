import os
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from matplotlib.colors import LinearSegmentedColormap

from networks_regional_dictionary import boundary_network_plots



def evaluate_line_usage(networks_year, years, scenarios, resultdir):
    """
    Creates maps showing the CH4-pipeline utilization by calling plot functions as a color scale.

    Parameters
    ----------
    networks_year : dict
        dict with networks per year and scenario
        ({year: {scen: network}})
    years : list
        list of relevant years
    scenarios : list
        list of relevant scenarios
    resultdir : pathlib.Path
        path of resultdirectory

    Returns
    -------
    None
    """

    for year in years:
        updated_networks = {}
        for scen in scenarios:
            # Get network and calculate data
            this_network = networks_year[year][scen]
            this_network = calculate_utilization(this_network)

            # Plot calls
            filename = f"{resultdir}/ch4_utilization_map_{scen}_{year}.png"
            plot_ch4_utilization_map(this_network, filename)
            updated_networks[scen] = this_network


def plot_ch4_utilization_map(network, filename):
    """
    Creates map with the CH4 pipeline capacity as linewidth and the
    utilization as color of the line.

    Parameters
    ----------
    network : pypsa.Network
        network of one year and scenario
    filename : str
        string of path + filename

    Returns
    -------
    None
    """
    # Get data + assign location
    n_ch4_util = network.copy()
    assign_location(n_ch4_util)

    # Setting bounds
    linewidth_factor = 1e4
    # MW below which not drawn
    line_lower_threshold = 1e2

    # Drop non-electric buses so they don't clutter the plot
    n_ch4_util.buses.drop(
        n_ch4_util.buses.index[n_ch4_util.buses.carrier != "AC"], inplace=True
    )

    # Drop all links which are not gas pipelines
    to_remove = n_ch4_util.links.index[
        ~n_ch4_util.links.carrier.str.contains("gas pipeline")
    ]
    n_ch4_util.links.drop(to_remove, inplace=True)

    gas_pipes = group_pipes_CH4(n_ch4_util.links, drop_direction=True)
    n_ch4_util.links = gas_pipes
    # Calculate linewidth
    link_widths = gas_pipes.p_nom_opt / linewidth_factor
    link_widths[gas_pipes.p_nom_opt < line_lower_threshold] = 0.0

    gas_pipes.bus0 = gas_pipes.bus0.str.replace(" gas", "")
    gas_pipes.bus1 = gas_pipes.bus1.str.replace(" gas", "")

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(
        figsize=(3.15, 4.13), subplot_kw={"projection": ccrs.EqualEarth()}
    )
    # Set plot options + plot map
    map_opts = {
        "boundaries": boundary_network_plots("EU27"),
        "color_geomap": {"ocean": "white", "land": "white"},
    }

    # Define hex codes for your three desired colors
    colors = ["#8B0000", "#FFD700", "#008000"]  # Red, Green, Blue
    # Build a LinearSegmentedColormap from these colors
    custom_cmap = LinearSegmentedColormap.from_list("myRdYlGn", colors)
    # Plot
    map = n_ch4_util.plot(
        bus_sizes=0,
        link_colors=gas_pipes.mean_util * 100,
        link_widths=link_widths,
        branch_components=["Link"],
        link_cmap=custom_cmap,
        ax=ax,
        **map_opts,
    )

    ## Legend
    # Add colorbar
    plt.colorbar(
        map[1],
        orientation="horizontal",
        fraction=0.04,
        pad=0.004,
        label="Average utilisation (%)",
    )
    # Add legend for linewidth
    # Set legend options (labels + sizes
    sizes = [50, 10]
    labels = [f"{s} GW" for s in sizes]
    scale = 1e3 / linewidth_factor
    sizes = [s * scale for s in sizes]
    legend_kw = dict(
        loc="upper left",
        bbox_to_anchor=(0.0, 1.15),
        labelspacing=0.3,
        handletextpad=1.0,
        title="gas pipeline",
        frameon=True,
        facecolor="white",
        framealpha=1.0,
    )
    add_legend_lines(
        ax,
        sizes,
        labels,
        patch_kw=dict(color="grey"),
        legend_kw=legend_kw,
    )

    # Saving plot
    plt.tight_layout()
    fig.savefig(filename, bbox_inches="tight")
    plt.close(fig)




def add_legend_lines(ax, sizes, labels, patch_kw={}, legend_kw={}):
    """
    Add a legend for lines and links.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        matplotlib ax
    sizes : list of float
        list (float) with size of the line reference
    labels : list of str
        list (str) with label of the line reference
    patch_kw : dict, optional
        Keyword arguments passed to plt.Line2D, by default {}
    legend_kw : dict, optional
        Keyword arguments passed to ax.legend, by default {}

    Returns
    -------
    None
    """
    # Set labels + handels + sizes of lines
    sizes = np.atleast_1d(sizes)
    labels = np.atleast_1d(labels)
    assert len(sizes) == len(
        labels
    ), "Sizes and labels must have the same length."
    handles = [plt.Line2D([0], [0], linewidth=s, **patch_kw) for s in sizes]

    # Add legend
    legend = ax.legend(handles, labels, **legend_kw)
    ax.get_figure().add_artist(legend)
    # Set frame to white
    legend.get_frame().set_facecolor("white")
    legend.get_frame().set_alpha(1)


def assign_location(n):
    """
    Assigns values of network.

    Parameters
    ----------
    n : pypsa.Network
        network of one year and scenario

    Returns
    -------
    None
    """
    for c in n.iterate_components(n.one_port_components | n.branch_components):
        ifind = pd.Series(c.df.index.str.find(" ", start=4), c.df.index)
        for i in ifind.value_counts().index:
            # these have already been assigned defaults
            if i == -1:
                continue
            names = ifind.index[ifind == i]
            c.df.loc[names, "location"] = names.str[:i]


def calculate_utilization(network):
    """
    Calculates mean utilization of links.

    Parameters
    ----------
    network : pypsa.Network
        network of one year and scenario

    Returns
    -------
    pypsa.Network
        network with mean utilization of lines and links
    """
    # Get network
    n_calc_util = network.copy()
    snapshot_weightings = n_calc_util.snapshot_weightings.generators
    # Calculation for links
    links = n_calc_util.links.query("(p_nom_opt>1)")
    links_t = n_calc_util.links_t
    links_t.p0 = links_t.p0.loc[:, links.index]

    hourly_p = abs(links_t.p0.loc[:, links.index])
    mean_p = (
        hourly_p.T.groupby(links.index.str.replace("-reversed", "")).sum()
    ).mul(snapshot_weightings, axis=1).sum(axis=1) / snapshot_weightings.sum()
    mean_utilization_links = mean_p / (
        links.query("~reversed").p_nom_opt * links.query("~reversed").p_max_pu
    )

    n_calc_util.links["mean_util"] = mean_utilization_links.replace(
        {np.inf: np.nan, -np.inf: np.nan}
    )

    return n_calc_util


def group_pipes_CH4(df, drop_direction=False):
    """
    Group pipes which connect same buses and return overall capacity.

    Parameters
    ----------
    df : pd.DataFrame
        df of filtered network (index contains 'gas pipeline')
    drop_direction : bool, optional
        boolean (drops flow direction), by default False

    Returns
    -------
    pd.DataFrame
        df with overall capacity
    """
    # Group reversed pipelines
    df.index = df.index.str.replace("-reversed", "")
    df.mean_util.fillna(0, inplace=True)
    df = df.groupby(level=0).agg(
        {
            "p_nom_opt": "first",
            "bus0": "first",
            "bus1": "first",
            "mean_util": "mean",
        }
    )
    # Drop flow direction
    if drop_direction:
        positive_order = df.bus0 < df.bus1
        df_p = df[positive_order]
        swap_buses = {"bus0": "bus1", "bus1": "bus0"}
        df_n = df[~positive_order].rename(columns=swap_buses)
        df = pd.concat([df_p, df_n])

    # There are pipes for each investment period rename to
    # AC buses name for plotting
    df.index = df.apply(
        lambda x: (
            f"gas pipeline {x.bus0.replace(' gas', '')} -> "
            f"{x.bus1.replace(' gas', '')}"
        ),
        axis=1,
    )
    df.mean_util = df.mean_util * df.p_nom_opt
    grouped_df = df.groupby(level=0).agg(
        {"p_nom_opt": sum, "bus0": "first", "bus1": "first", "mean_util": sum}
    )
    grouped_df.mean_util = grouped_df.mean_util / grouped_df.p_nom_opt
    return grouped_df


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    years = ["2025", "2030", "2035", "2040", "2045", "2050"]
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

    scenario_colors = {
        "scenario_1": "#39C1CD",
        "scenario_2": "#F58220",
        "scenario_3": "#179C7D",
        "scenario_4": "#854006",
    }
    util_dir = resultdir / "utilization"
    if not os.path.exists(util_dir):
        os.mkdir(util_dir)
    evaluate_line_usage(networks_year, years, scenarios, util_dir)
