import os
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import pypsa

from networks_regional_dictionary import boundary_network_plots
from common import log


def plot_grid_comparisons(
    networks_year, years, resultdir, scenario_colors_comp, country_to_plot
):
    """
    Creates 2 maps (for electricity and H2) that compare the installed
    grid capacity between 2 scenarios by calling plot functions. The
    plotted lines show the difference, i.e. which scenario
    predominates.
        - Electricity grid
        - H2 grid

    Parameters
    ----------
    networks_year : dict
        dictionary with networks per scenario and year
        ({year: {scen: network}})
    years : list
        list of relevant years
    resultdir : str or pathlib.Path
        path of the result directory
    scenario_colors_comp : dict
        dictionary with scenario names and colors that are compared
        ({scen: color})
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    log(f"Starting: plot_grid_comparisons — {scenario_colors_comp.keys()}")

    # Get scenario names to compare
    scenarios_for_comp = [scen for scen, color in scenario_colors_comp.items()]
    scenario1 = scenarios_for_comp[0]
    scenario2 = scenarios_for_comp[1]
    # Get associated colors
    color1 = scenario_colors_comp[scenario1]
    color2 = scenario_colors_comp[scenario2]

    for year in years:
        # Get network of each scenario for one year
        network1 = networks_year[year][scenario1]
        network2 = networks_year[year][scenario2]
        # Get links from networks
        links1 = network1.links.rename(columns={"p_nom_opt": "p_nom_opt1"})
        links2 = network2.links.rename(columns={"p_nom_opt": "p_nom_opt2"})
        # Initialize data for comparison
        merged_links = pd.merge(
            links1, links2, left_index=True, right_index=True, how="outer"
        ).fillna(0)
        merged_links["p_nom_opt"] = (
            merged_links["p_nom_opt2"] - merged_links["p_nom_opt1"]
        )
        merged_links.rename(
            columns={
                "bus0_x": "bus0",
                "bus1_x": "bus1",
                "carrier_x": "carrier",
                "reversed_x": "reversed",
            },
            inplace=True,
        )
        merged_links.loc[merged_links["bus0"] == 0, ["reversed"]] = (
            merged_links["reversed_y"]
        )
        merged_links.loc[merged_links["bus0"] == 0, ["bus0"]] = merged_links[
            "bus0_y"
        ]
        merged_links.loc[merged_links["bus1"] == 0, ["bus1"]] = merged_links[
            "bus1_y"
        ]
        merged_links.loc[merged_links["carrier"] == 0, ["carrier"]] = (
            merged_links["carrier_y"]
        )
        merged_links.reversed = merged_links.reversed.astype(bool)
        n_comp = network2.copy()
        n_comp.links = merged_links
        n_comp.lines.s_nom_opt = network2.lines.s_nom_opt.add(
            -network1.lines.s_nom_opt, fill_value=0
        )

        # Plot electricity map
        filename = resultdir / f"diff_elec_{scenario1}_{scenario2}_{year}.png"
        plot_map_elec_comp(
            n_comp,
            filename,
            color1,
            color2,
            scenario1,
            scenario2,
            country_to_plot,
        )

        # Plot H2 map
        FN = resultdir / f"diff_H2_{scenario1}_{scenario2}_{year}.png"
        plot_h2_map_comp(
            n_comp, FN, color1, color2, scenario1, scenario2, country_to_plot
        )

    log(f"Done: plot_grid_comparisons — {scenario_colors_comp.keys()}")


def plot_map_elec_comp(
    network, FN, color_neg, color_pos, scenario1, scenario2, country_to_plot
):
    """
    Creates map for electricity grid as described in
    plot_grid_comparisons.

    Parameters
    ----------
    network : pypsa.Network
        network of one year for comparison
    FN : str or pathlib.Path
        string of path + filename to save the plot
    color_neg : str
        color corresponding to scenario1
    color_pos : str
        color corresponding to scenario2
    scenario1 : str
        name of scenario1
    scenario2 : str
        name of scenario2
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    # Get network + assign location
    n_elec_comp = network.copy()
    assign_location(n_elec_comp)

    ## Calculation
    # PDF has minimum width, so set these to zero
    line_lower_threshold = 0
    line_upper_threshold = 1e20
    linewidth_factor = 7e2

    # Drop non-electric buses so they don't clutter the plot
    n_elec_comp.buses.drop(
        n_elec_comp.buses.index[n_elec_comp.buses.carrier != "AC"],
        inplace=True,
    )
    to_drop = n_elec_comp.links.index[
        (n_elec_comp.links.carrier != "DC")
        & (n_elec_comp.links.carrier != "B2B")
    ]
    n_elec_comp.links.drop(to_drop, inplace=True)
    n_elec_comp.links = n_elec_comp.links.query("~reversed")

    # Calculate lines + links for scenario2
    n_pos = n_elec_comp.copy()
    n_pos.links[n_pos.links.query("p_nom_opt<0").index] = 0
    n_pos.lines[n_pos.lines.query("s_nom_opt<0").index] = 0
    line_widths_pos = n_elec_comp.lines.s_nom_opt
    link_widths_pos = n_elec_comp.links.p_nom_opt
    line_widths_pos = line_widths_pos.clip(
        line_lower_threshold, line_upper_threshold
    )
    link_widths_pos = link_widths_pos.clip(
        line_lower_threshold, line_upper_threshold
    )
    line_widths_pos = line_widths_pos.replace(line_lower_threshold, 0)
    link_widths_pos = link_widths_pos.replace(line_lower_threshold, 0)

    # Calculate lines + links for scenario 1
    n_neg = n_elec_comp.copy()
    n_neg.links[n_neg.links.query("p_nom_opt>0").index] = 0
    n_neg.lines[n_neg.lines.query("s_nom_opt>0").index] = 0
    line_widths_neg = -n_elec_comp.lines.s_nom_opt
    link_widths_neg = -n_elec_comp.links.p_nom_opt
    line_widths_neg = line_widths_neg.clip(
        line_lower_threshold, line_upper_threshold
    )
    link_widths_neg = link_widths_neg.clip(
        line_lower_threshold, line_upper_threshold
    )
    line_widths_neg = line_widths_neg.replace(line_lower_threshold, 0)
    link_widths_neg = link_widths_neg.replace(line_lower_threshold, 0)

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})
    # Set options
    map_opts = {"boundaries": boundary_network_plots(country_to_plot)}
    ac_color_pos = color_pos
    dc_color_pos = color_pos
    ac_color_neg = color_neg
    dc_color_neg = color_neg

    # Plot scenario2
    n_pos.plot(
        bus_colors="k",
        line_colors=ac_color_pos,
        link_colors=dc_color_pos,
        line_widths=line_widths_pos / linewidth_factor,
        link_widths=link_widths_pos / linewidth_factor,
        ax=ax,
        **map_opts,
    )
    # Plot scenario1
    n_neg.plot(
        bus_colors="k",
        line_colors=ac_color_neg,
        link_colors=dc_color_neg,
        line_widths=line_widths_neg / linewidth_factor,
        link_widths=link_widths_neg / linewidth_factor,
        ax=ax,
        **map_opts,
    )

    ## Legend
    # Set handels + labels
    handles = []
    labels = []
    for s in (4, 1):
        handles.append(
            plt.Line2D(
                [0], [0], color=color_neg, linewidth=s * 1e3 / linewidth_factor
            )
        )
        labels.append(f"additional {s} GW in {scenario1}")
    for s in (1, 4):
        handles.append(
            plt.Line2D(
                [0], [0], color=color_pos, linewidth=s * 1e3 / linewidth_factor
            )
        )
        labels.append(f"additional {s} GW in {scenario2}")

    # Add legend for colormapping + linewidth
    l1_1 = ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0, 1.01),
        labelspacing=0.3,
        handletextpad=1.0,
        frameon=True,
        facecolor="white",
        framealpha=1.0,
    )
    ax.add_artist(l1_1)

    # Saving plot
    plt.tight_layout()
    fig.savefig(FN, bbox_inches="tight")
    plt.close(fig)


def plot_h2_map_comp(
    network,
    save_path,
    color_neg,
    color_pos,
    scenario1,
    scenario2,
    country_to_plot,
):
    """
    Creates map for H2 grid as described in plot_grid_comparisons.

    Parameters
    ----------
    network : pypsa.Network
        network of one year for comparison
    save_path : str or pathlib.Path
        path + filename for saving the plot
    color_neg : str
        color for scenario1
    color_pos : str
        color for scenario2
    scenario1 : str
        name of scenario1
    scenario2 : str
        name of scenario2
    country_to_plot : str
        region to be plotted

    Returns
    -------
    None
    """
    # Get network + assign location
    n_h2_comp = network.copy()
    if "H2 pipeline" not in n_h2_comp.links.carrier.unique():
        return
    assign_location(n_h2_comp)

    ## Calculation
    # Set bounds
    linewidth_factor = 3e3
    # MW below which not drawn
    line_lower_threshold = 750

    # Drop non-electric buses so they don't clutter the plot
    n_h2_comp.buses.drop(
        n_h2_comp.buses.index[n_h2_comp.buses.carrier != "AC"], inplace=True
    )
    # Drop all links which are not H2 pipelines
    n_h2_comp.links.drop(
        n_h2_comp.links.index[
            ~n_h2_comp.links.carrier.str.contains("H2 pipeline")
        ],
        inplace=True,
    )

    # Initialize H2 new, retro and inframap
    h2_new = n_h2_comp.links[
        (n_h2_comp.links.carrier == "H2 pipeline") & ~n_h2_comp.links.reversed
    ]
    h2_retro = n_h2_comp.links[
        (n_h2_comp.links.carrier == "H2 pipeline retrofitted")
        & ~n_h2_comp.links.reversed
    ]
    h2_inframap = n_h2_comp.links[
        (n_h2_comp.links.carrier == "H2 pipeline (Kernnetz)")
        & ~n_h2_comp.links.reversed
    ]
    h2_inframap = group_pipes(h2_inframap, drop_direction=True)
    # Sum capacitiy for pipelines from different investment periods
    h2_new = group_pipes(h2_new, drop_direction=True)

    # Calculate h2_total
    if not h2_retro.empty:
        h2_retro = (
            group_pipes(h2_retro, drop_direction=True)
            .reindex(h2_new.index)
            .dropna()
        )
        to_concat_total = [h2_new, h2_retro, h2_inframap]
        h2_total = pd.concat(to_concat_total).p_nom_opt.groupby(level=0).sum()
    else:
        h2_total = h2_new.p_nom_opt

    # Calculate link_widths
    # Total
    link_widths_total = h2_total / linewidth_factor
    n_h2_comp.links.rename(index=lambda x: x.split("-2")[0], inplace=True)
    n_h2_comp.links.rename(
        index=lambda x: x.split("-kernnetz")[0], inplace=True
    )
    n_h2_comp.links.rename(
        index=lambda x: x.replace(" retrofitted", ""), inplace=True
    )
    n_h2_comp.links.rename(
        index=lambda x: x.replace("<->", "->"), inplace=True
    )
    n_h2_comp.links.rename(index=lambda x: x.replace("<-", "->"), inplace=True)
    n_h2_comp.links = n_h2_comp.links.groupby(level=0).agg(
        {
            "p_nom_opt": sum,
            "bus0": "first",
            "bus1": "first",
            "carrier": "first",
        }
    )
    link_widths_total = link_widths_total.reindex(
        n_h2_comp.links.index
    ).fillna(0.0)
    # H2 infra
    h2_infra = n_h2_comp.links.p_nom_opt.where(
        n_h2_comp.links.carrier == "H2 pipeline (Kernnetz)", other=0.0
    )
    link_widths_h2infra = h2_infra / linewidth_factor
    link_widths_h2infra[n_h2_comp.links.p_nom_opt < line_lower_threshold] = 0.0
    # H2 retro
    retro = (
        n_h2_comp.links.p_nom_opt.where(
            n_h2_comp.links.carrier == "H2 pipeline retrofitted", other=0.0
        )
        + h2_infra
    )
    link_widths_retro = retro / linewidth_factor
    link_widths_retro[n_h2_comp.links.p_nom_opt < line_lower_threshold] = 0.0

    n_h2_comp.links.bus0 = n_h2_comp.links.bus0.str.replace(" H2", "")
    n_h2_comp.links.bus1 = n_h2_comp.links.bus1.str.replace(" H2", "")

    # Calculate link_widths for both scenarios
    # scenario1
    n_neg = n_h2_comp.copy()
    n_neg.links.loc[n_neg.links.query("p_nom_opt>0").index, "p_nom_opt"] = 0
    link_widths_neg = link_widths_total.copy()
    link_widths_neg[link_widths_total > 0] = 0
    # scenario2
    n_pos = n_h2_comp.copy()
    n_pos.links.loc[n_pos.links.query("p_nom_opt<0").index, "p_nom_opt"] = 0
    link_widths_pos = link_widths_total.copy()
    link_widths_pos[link_widths_total < 0] = 0

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})
    # Set options
    map_opts = {"boundaries": boundary_network_plots(country_to_plot)}

    # Plot scenario1
    n_neg.plot(
        geomap=True,
        bus_colors="k",
        link_colors=color_neg,
        link_widths=link_widths_neg,
        branch_components=["Link"],
        ax=ax,
        **map_opts,
    )
    # Plot scenario2
    n_pos.plot(
        geomap=True,
        bus_colors="k",
        link_colors=color_pos,
        link_widths=link_widths_pos,
        branch_components=["Link"],
        ax=ax,
        **map_opts,
    )

    ## Legend
    # Set handels + labels
    handles = []
    labels = []
    for s in (20, 5):
        handles.append(
            plt.Line2D(
                [0], [0], color=color_neg, linewidth=s * 1e3 / linewidth_factor
            )
        )
        labels.append(f"additional {s} GW in {scenario1}")
    for s in (5, 20):
        handles.append(
            plt.Line2D(
                [0], [0], color=color_pos, linewidth=s * 1e3 / linewidth_factor
            )
        )
        labels.append(f"additional {s} GW in {scenario2}")

    # Add legend for colormapping + linewidth
    l1_1 = ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0, 1.01),
        labelspacing=0.3,
        handletextpad=1.0,
        frameon=True,
        facecolor="white",
        framealpha=1.0,
    )
    ax.add_artist(l1_1)

    # Saving plot
    plt.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)


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
            # These have already been assigned defaults
            if i == -1:
                continue
            names = ifind.index[ifind == i]
            c.df.loc[names, "location"] = names.str[:i]


def group_pipes(df, drop_direction=False):
    """
    Group pipes which connect same buses and return overall capacity.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame of filtered network (index contains 'H2')
    drop_direction : bool, optional
        whether to drop flow direction, by default False

    Returns
    -------
    pandas.DataFrame
        DataFrame with overall capacity
    """
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
            f"H2 pipeline {x.bus0.replace(' H2', '')} -> "
            f"{x.bus1.replace(' H2', '')}"
        ),
        axis=1,
    )

    return df.groupby(level=0).agg(
        {"p_nom_opt": sum, "bus0": "first", "bus1": "first"}
    )


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
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

    scenarios_for_comp = ["scenario_1", "scenario_2"]

    scenario_colors = {
        "scenario_1": "#39C1CD",
        "scenario_2": "#F58220",
        "scenario_3": "#179C7D",
        "scenario_4": "#854006",
    }

    scenario_colors_comp = {
        key: scenario_colors[key]
        for key in scenario_colors
        if key in scenarios_for_comp
    }

    # Specify for which country network plots are generated
    country_to_plot = "EU27"

    plot_grid_comparisons(
        networks_year, years, resultdir, scenario_colors_comp, country_to_plot
    )
