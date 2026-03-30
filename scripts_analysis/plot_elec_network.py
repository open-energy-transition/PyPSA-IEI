import os
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import pypsa
from pypsa.plot import add_legend_patches

from common import log
from networks_regional_dictionary import boundary_network_plots



def plot_map_elec_years(
    networks_year,
    resultdir,
    scenarios,
    years,
    main_dir,
    sector_opts,
    run_names,
    country_to_plot,
):
    """
    Creates 3 different maps of electricity grids per year and scenario
    by calling plot functions:
        - Net expansion of electricity grid (post + pre)
        - Net expansion of electricity grid (difference)
        - Existing electricity grid for scen 'CE' in '2020'


    Parameters
    ----------
    networks_year : dict
        dict with networks per scenario and year
        ({year: {scen: network}})
    resultdir : str or Path
        path of resultdirectory
    scenarios : list
        list of scenarios
    years : list
        list of relevant years
    main_dir : str or Path
        path of maindirectory
    sector_opts : dict
        string of filename (e.g. for prenetwork)
    run_names : dict
        dict with network storage folder ({scen: folder})
    country_to_plot : str
        string of relevant country/region

    Returns
    -------
    None
    """
    log("Starting: plot_map_elec_years")

    for year in years:
        for scen in scenarios:
            this_network = networks_year[year][scen]

            # Load prenetwork for year '2020'
            pre_network_year = "2020"
            path_to_prenetworks = Path(
                f"{main_dir}/results/{run_names[scen]}/prenetworks"
            )
            n_pre = pypsa.Network(
                path_to_prenetworks
                / f"{sector_opts[scen]}_{pre_network_year}.nc"
            )

            # Plot electricity network expansion
            filename = f"{resultdir}/elec_netexpansion_{scen}_{year}.png"
            plot_map_elec(this_network, n_pre, filename, country_to_plot)
            filename = f"{resultdir}/pre_elec_netexpansion_{scen}_{year}.png"
            plot_map_elec(
                this_network, n_pre, filename, country_to_plot, type="diff"
            )

            # Plot existing electricity grid for scen 'CE' in '2020'
            if (scen == "CE") & (year == "2020"):
                path_to_prenetworks = Path(
                    f"{main_dir}/results/{run_names[scen]}/prenetworks"
                )
                n_pre = pypsa.Network(
                    path_to_prenetworks / f"{sector_opts[scen]}_{year}.nc"
                )  # load the network
                filename = f"{resultdir}/elec_network_existing.png"
                plot_map_elec_existing(n_pre, filename, country_to_plot)

    log("Done: plot_map_elec_years")


def plot_map_elec(network, pre_network, FN, country_to_plot, type="both"):
    """
    Creates map with Net expansion of electricity grid
    (post + pre if type = 'both'; difference if type = 'diff').

    Parameters
    ----------
    network : pypsa.Network
        postnetwork of one year and scenario
    pre_network : pypsa.Network
        prenetwork of one year and scenario
    FN : str
        string of filename
    country_to_plot : str
        string of region to be plotted
    type : str, optional
        string of plot type (described above), by default "both"

    Returns
    -------
    None
    """
    n_post = network.copy()
    n_pre = pre_network.copy()
    assign_location(n_post)

    ## Calculation of lines and links
    # PDF has minimum width, so set these to zero
    line_lower_threshold = 200.0
    line_upper_threshold = 1e4
    linewidth_factor = 3e3

    # Drop non-electric buses so they don't clutter the plot
    n_post.buses.drop(
        n_post.buses.index[n_post.buses.carrier != "AC"], inplace=True
    )
    n_pre.buses.drop(
        n_pre.buses.index[n_pre.buses.carrier != "AC"], inplace=True
    )

    # Post links + lines
    to_drop = n_post.links.index[
        (n_post.links.carrier != "DC") & (n_post.links.carrier != "B2B")
    ]
    n_post.links.drop(to_drop, inplace=True)
    line_widths = n_post.lines.s_nom_opt
    link_widths = n_post.links.p_nom_opt
    line_widths = line_widths.clip(line_lower_threshold, line_upper_threshold)
    link_widths = link_widths.clip(line_lower_threshold, line_upper_threshold)
    line_widths = line_widths.replace(line_lower_threshold, 0)
    link_widths = link_widths.replace(line_lower_threshold, 0)

    # Pre links + lines
    to_drop = n_pre.links.index[
        (n_pre.links.carrier != "DC") & (n_pre.links.carrier != "B2B")
    ]
    n_pre.links.drop(to_drop, inplace=True)
    line_widths_pre = n_pre.lines.s_nom_min
    link_widths_pre = n_pre.links.p_nom_min
    line_widths_pre = line_widths_pre.clip(
        line_lower_threshold, line_upper_threshold
    )
    link_widths_pre = link_widths_pre.clip(
        line_lower_threshold, line_upper_threshold
    )
    line_widths_pre = line_widths_pre.replace(line_lower_threshold, 0)
    link_widths_pre = link_widths_pre.replace(line_lower_threshold, 0)
    if type == "diff":
        line_widths_pre = line_widths - line_widths_pre
        link_widths_pre = link_widths - link_widths_pre

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})
    # Set plot options
    map_opts = {
        "boundaries": boundary_network_plots(
            country_to_plot
        ),  # [-11, 30, 34, 71],
        "color_geomap": {"ocean": "white", "land": "white"},
    }
    ac_color_pre = "#d95f02"
    dc_color_pre = "#1b9e77"
    ac_color_post = "#fdcdac"
    dc_color_post = "#b3e2cd"
    # Plot map (differenciate between 'both' and 'diff')
    if type == "both":
        n_post.plot(
            bus_colors="k",
            line_colors=ac_color_post,
            link_colors=dc_color_post,
            line_widths=line_widths / linewidth_factor,
            link_widths=link_widths / linewidth_factor,
            ax=ax,
            **map_opts,
        )
    n_post.plot(
        bus_colors="k",
        line_colors=ac_color_pre,
        link_colors=dc_color_pre,
        line_widths=line_widths_pre / linewidth_factor,
        link_widths=link_widths_pre / linewidth_factor,
        ax=ax,
        **map_opts,
    )

    # Set handels + labels for legend
    handles = []
    labels = []
    for s in (10, 5):
        handles.append(
            plt.Line2D(
                [0],
                [0],
                color="lightgrey",
                linewidth=s * 1e3 / linewidth_factor,
            )
        )
        labels.append(f"{s} GW")

    # Add legend for linewidth
    l1_1 = ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0.05, 1.01),
        frameon=True,
        facecolor="white",
        framealpha=1.0,
        labelspacing=0.5,
        handletextpad=1.0,
    )
    ax.add_artist(l1_1)

    # Add legend for colormapping (difference between 'both' and 'diff')
    legend_kw = dict(
        bbox_to_anchor=(0.5, 1), ncol=2, frameon=True, facecolor="white"
    )
    if type == "both":
        add_legend_patches(
            ax,
            [ac_color_post, dc_color_post, ac_color_pre, dc_color_pre],
            ["AC Post", "DC Post", "AC Pre", "DC Pre"],
            legend_kw=legend_kw,
        )
    if type == "diff":
        add_legend_patches(
            ax,
            [ac_color_pre, dc_color_pre],
            ["AC net expansion", "DC net expansion"],
            legend_kw=legend_kw,
        )

    plt.tight_layout()
    fig.savefig(FN, bbox_inches="tight")




def plot_map_elec_existing(network, FN, country_to_plot):
    """
    Creates map of country_to_plot with the existing electricity
    network (related to '2020').

    Parameters
    ----------
    network : pypsa.Network
        prenetwork of 'CE' and '2020'
    FN : str
        string of filename
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    n_elec_pre = network.copy()
    assign_location(n_elec_pre)

    ## Calculation of lines and links
    # PDF has minimum width, so set these to zero
    line_lower_threshold = 200.0
    line_upper_threshold = 1e4
    linewidth_factor = 3e3

    # Drop non-electric buses so they don't clutter the plot
    n_elec_pre.buses.drop(
        n_elec_pre.buses.index[n_elec_pre.buses.carrier != "AC"], inplace=True
    )

    to_drop = n_elec_pre.links.index[
        (n_elec_pre.links.carrier != "DC")
        & (n_elec_pre.links.carrier != "B2B")
    ]
    n_elec_pre.links.drop(to_drop, inplace=True)
    line_widths = n_elec_pre.lines.s_nom_min
    link_widths = n_elec_pre.links.p_nom_min
    line_widths = line_widths.clip(line_lower_threshold, line_upper_threshold)
    link_widths = link_widths.clip(line_lower_threshold, line_upper_threshold)
    line_widths = line_widths.replace(line_lower_threshold, 0)
    link_widths = link_widths.replace(line_lower_threshold, 0)

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})
    # Set plot options
    map_opts = {
        "boundaries": boundary_network_plots(
            country_to_plot
        ),  # [-11, 30, 34, 71],
        "color_geomap": {"ocean": "white", "land": "white"},
    }
    ac_color = "#d95f02"
    dc_color = "#1b9e77"
    # Plot map
    n_elec_pre.plot(
        bus_colors="k",
        line_colors=ac_color,
        link_colors=dc_color,
        line_widths=line_widths / linewidth_factor,
        link_widths=link_widths / linewidth_factor,
        ax=ax,
        **map_opts,
    )

    # Set handels + labels for legend
    handles = []
    labels = []
    for s in (10, 5):
        handles.append(
            plt.Line2D(
                [0],
                [0],
                color="lightgrey",
                linewidth=s * 1e3 / linewidth_factor,
            )
        )
        labels.append(f"{s} GW")

    # Add legend for linewidth
    l1_1 = ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0.05, 1.01),
        frameon=True,
        facecolor="white",
        framealpha=1.0,
        labelspacing=0.5,
        handletextpad=1.0,
    )
    ax.add_artist(l1_1)

    # Add legend for colormapping
    legend_kw = dict(
        bbox_to_anchor=(0.5, 1), ncol=2, frameon=True, facecolor="white"
    )
    add_legend_patches(
        ax, [ac_color, dc_color], ["AC", "DC"], legend_kw=legend_kw
    )

    plt.tight_layout()
    fig.savefig(FN, bbox_inches="tight")




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


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    years = ["2020", "2030", "2035", "2040", "2045", "2050"]
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
    run_name = {}
    # load all network files from results folder into a nested dictionary
    networks_year = {}
    for year in years:
        curr_networks = {}
        for scen in scenarios:
            run_name[scen] = runs[scen]
            path_to_networks = Path(
                f"{main_dir}/results/{run_name[scen]}/postnetworks"
            )
            n = pypsa.Network(
                path_to_networks / f"{sector_opts}_{year}.nc"
            )
            curr_networks.update({scen: n})

        networks_year.update({year: curr_networks})

    # Specify for which country network plots are generated
    country_to_plot = "EU27"

    plot_map_elec_years(
        networks_year,
        resultdir,
        scenarios,
        years,
        main_dir,
        sector_opts,
        run_name,
        country_to_plot,
    )
