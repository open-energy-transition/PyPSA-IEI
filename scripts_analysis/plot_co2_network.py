import os
import re
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import pypsa
from pypsa.plot import add_legend_circles, add_legend_lines, add_legend_patches

from networks_regional_dictionary import boundary_network_plots



def plot_co2_map_years(
    networks_year, resultdir, years, scenarios, country_to_plot
):
    """
    Creates map of CO2 storage + usage in the region 'country_to_plot'
    for one year and scenario by calling plot function.

    Parameters
    ----------
    networks_year : dict
        dict with networks per scenario and year
        ({year: {scen: network}})
    resultdir : str or Path
        path of resultdirectory
    years : list
        list of relevant years
    scenarios : list
        list of scenario names
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    for scen in scenarios:
        for year in years:
            this_network = networks_year[year][scen]

            filename = f"{resultdir}/co2_network_{scen}_{year}.png"
            plot_co2_map(this_network, filename, country_to_plot)





def plot_co2_map(network, save_path, country_to_plot):
    """
    Creates map as described in plot_co2_map_years.

    Parameters
    ----------
    network : pypsa.Network
        network of one year and scenario
    save_path : str or Path
        string of path + filename
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    n_co2_single = network.copy()
    assign_location(n_co2_single)
    co2_sequestered = n_co2_single.stores.query("carrier == 'co2 sequestered'")

    # Setting bounds
    bus_size_factor = 2e7
    linewidth_factor = 400
    # MW below which not drawn
    line_lower_threshold = 0.05
    flow_arrow_factor = 4e4
    # Setting carriers + mapping
    carriers = ["methanolisation", "Sabatier", "Fischer-Tropsch"]
    bus_mapping_co2_stored = {
        "methanolisation": "p3",
        "Sabatier": "p2",
        "Fischer-Tropsch": "p2",
    }

    # Drop non-electric buses so they don't clutter the plot
    n_co2_single.buses.drop(
        n_co2_single.buses.index[n_co2_single.buses.carrier != "AC"],
        inplace=True,
    )

    # Calculate bus sizes
    # Transform data
    bus_size_co2_seq = (
        co2_sequestered.e_nom_opt.groupby(level=0).sum().div(bus_size_factor)
    )
    bus_size_co2_seq.rename(
        index=lambda x: re.sub(" co2 sequestered.*$", "", x),
        level=0,
        inplace=True,
    )
    bus_size_co2_seq.index = pd.MultiIndex.from_product(
        [bus_size_co2_seq.index, ["co2 sequestered"]]
    )
    bus_sizes_list = [bus_size_co2_seq]
    snapshots = n_co2_single.snapshot_weightings.generators
    # Get bus sizes for every carrier
    for carrier_name in carriers:
        carrier_names_unfiltered = n_co2_single.links[
            n_co2_single.links.carrier.isin([carrier_name])
        ].index
        bus_sizes = (
            getattr(n_co2_single.links_t, bus_mapping_co2_stored[carrier_name])
            .loc[:, carrier_names_unfiltered]
            .mul(snapshots, axis=0)
            .sum()
            .abs()
            / bus_size_factor
        )
        # Make a fake MultiIndex so that area is correct for legend
        bus_sizes.index = pd.MultiIndex.from_product(
            [bus_sizes.index, [carrier_name]]
        )
        bus_sizes.rename(
            index=lambda x: re.sub(f" {carrier_name}.*$", "", x),
            level=0,
            inplace=True,
        )
        bus_sizes_list.append(bus_sizes)
    # Put data together
    bus_sizes = pd.concat(bus_sizes_list)
    bus_sizes = bus_sizes.groupby(level=[0, 1]).sum()
    carriers.append("co2 sequestered")

    # Drop all links which are not CO2 pipelines
    n_co2_single.links.drop(
        n_co2_single.links.index[
            ~n_co2_single.links.carrier.str.contains("CO2 pipeline")
        ],
        inplace=True,
    )

    # Get flow direction
    co2_new = n_co2_single.links[n_co2_single.links.carrier == "CO2 pipeline"]
    co2_new_t = n_co2_single.links_t
    flow_direction = co2_new_t.p0.loc[
        :, co2_new_t.p0.columns.str.contains("CO2")
    ].sum()
    flow_direction.rename(
        index=lambda x: re.sub("-20.*$", "", x), level=0, inplace=True
    )
    flow_direction = flow_direction.groupby(level=0).sum()

    # Get link width
    co2_total = group_pipes_CO2(co2_new).p_nom_opt
    link_widths_total = co2_total / linewidth_factor
    n_co2_single.links.rename(index=lambda x: x.split("-2")[0], inplace=True)
    n_co2_single.links = n_co2_single.links.groupby(level=0).first()
    link_widths_total = link_widths_total.reindex(
        n_co2_single.links.index
    ).fillna(0.0)
    link_widths_total[link_widths_total < line_lower_threshold] = 0.0

    n_co2_single.links.bus0 = n_co2_single.links.bus0.str.replace(
        " co2 stored", ""
    )
    n_co2_single.links.bus1 = n_co2_single.links.bus1.str.replace(
        " co2 stored", ""
    )

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig_co2, ax_co2 = plt.subplots(
        subplot_kw={"projection": ccrs.EqualEarth()}
    )

    color_co2_pipe = "#466171"
    bus_colors = {
        "methanolisation": "#636EFA",
        "Sabatier": "#EF553B",
        "Fischer-Tropsch": "#00CC96",
        "co2 sequestered": "#AB63FA",
    }
    map_opts = {
        "boundaries": boundary_network_plots(
            country_to_plot
        ), 
        "color_geomap": {"ocean": "white", "land": "white"},
    }
    flow = pd.concat(
        [flow_direction / flow_arrow_factor],
        keys=["Link"],
        names=["Components"],
    )

    # Plot
    n_co2_single.plot(
        geomap=True,
        bus_sizes=bus_sizes,
        bus_colors=bus_colors,
        flow=flow,
        link_colors=color_co2_pipe,
        link_widths=link_widths_total,
        branch_components=["Link"],
        ax=ax_co2,
        **map_opts,
    )

    # Legend
    sizes = [20000, 5000]
    labels = [f"{s} t" for s in sizes]
    sizes = [s / bus_size_factor * 1e3 for s in sizes]
    original_bounds = [-11, 30, 34, 71]
    are_equal = original_bounds == map_opts["boundaries"]
    if are_equal == False:
        y_area = original_bounds[-1] - original_bounds[-2]
        x_area = original_bounds[1] - original_bounds[0]
        y_new = map_opts["boundaries"][-1] - map_opts["boundaries"][-2]
        x_new = map_opts["boundaries"][1] - map_opts["boundaries"][0]
        sizes = [
            sizes[i] * (x_new * y_new) / (x_area * y_area)
            for i in range(0, len(sizes))
        ]

    # Add legend for pie charts
    legend_kw = dict(
        loc="upper left",
        bbox_to_anchor=(0, 0.9),
        labelspacing=0.3,
        handletextpad=0,
        frameon=True,
        facecolor="white",
        framealpha=1.0,
    )
    add_legend_circles(
        ax_co2,
        sizes,
        labels,
        srid=n_co2_single.srid,
        patch_kw=dict(facecolor="lightgrey"),
        legend_kw=legend_kw,
    )

    # Add legend for linewidth
    sizes = [1000, 500]
    labels = [f"{s} t/h CO2 pipeline" for s in sizes]
    scale = 1 / linewidth_factor
    sizes = [s * scale for s in sizes]
    legend_kw = dict(
        loc="upper left",
        bbox_to_anchor=(0, 1.01),
        labelspacing=0.3,
        handletextpad=1.0,
        frameon=True,
        facecolor="white",
        framealpha=1.0,
    )
    add_legend_lines(
        ax_co2,
        sizes,
        labels,
        patch_kw=dict(color="#466171"),
        legend_kw=legend_kw,
    )

    # Add legend for colormapping
    legend_kw = dict(
        bbox_to_anchor=(0.5, 1),
        ncol=2,
        frameon=False,
    )
    add_legend_patches(
        ax_co2, list(bus_colors.values()), carriers, legend_kw=legend_kw
    )

    plt.tight_layout()
    fig_co2.savefig(save_path, bbox_inches="tight")
    plt.close(fig_co2)




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


def group_pipes_CO2(df, drop_direction=False):
    """
    Group pipes which connect same buses and return overall capacity.

    Parameters
    ----------
    df : pd.DataFrame
        df of filtered network (index contains 'CO2')
    drop_direction : bool, optional
        boolean (drops flow direction), by default False

    Returns
    -------
    pd.DataFrame
        df with overall capacity
    """
    # Drop reversed pipelines
    reversed_pipes = df.query('index.str.contains("-reversed")').index
    df = df.drop(reversed_pipes)
    df = df.copy()
    # Drop flow direction
    if drop_direction:
        positive_order = df.bus0 < df.bus1
        df_p = df[positive_order]
        swap_buses = {"bus0": "bus1", "bus1": "bus0"}
        df_n = df[~positive_order].rename(columns=swap_buses)
        df = pd.concat([df_p, df_n])

    # There are pipes for each investment period rename
    # to AC buses name for plotting
    df["index_orig"] = df.index
    df.index = df.apply(
        lambda x: (
            f"CO2 pipeline {x.bus0.replace(' co2 stored', '')} -> "
            f"{x.bus1.replace(' co2 stored', '')}"
        ),
        axis=1,
    )

    return df.groupby(level=0).agg(
        {
            "p_nom_opt": "sum",
            "bus0": "first",
            "bus1": "first",
            "index_orig": "first",
        }
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

    # Specify for which country network plots are generated
    country_to_plot = "EU27"

    plot_co2_map_years(
        networks_year, resultdir, years, scenarios, country_to_plot
    )
