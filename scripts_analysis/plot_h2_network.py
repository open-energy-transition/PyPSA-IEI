import os
import re
from datetime import datetime
from pathlib import Path
from typing import List

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from pypsa.plot import add_legend_circles, add_legend_lines, add_legend_patches

from networks_regional_dictionary import boundary_network_plots



def plot_h2_map_years(
    networks_year, main_dir, resultdir, years, scenarios, runs, country_to_plot
):
    """
    Creates 4 different maps of H2 installation/pipelines in the area
    'country_to_plot' for one year and scenario by calling plot
    function:
        - H2 all network
        - H2 electrolysis network
        - H2 net flows network
        - H2 storage only

    Parameters
    ----------
    networks_year : dict
        dict with networks per scenario and year
        ({year: {scen: network}})
    main_dir : pathlib.Path
        path of maindirectory
    resultdir : pathlib.Path
        path of resultdirectory
    years : list of str
        list of relevant years
    scenarios : list of str
        list of scenario names
    runs : dict
        dict with network storage folder ({scen: folder})
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    for scen in scenarios:
        regions_path = (
            main_dir
            / "scripts_analysis"
            / "shapes"
            / "regions_onshore_elec_s_62.geojson"
        )
        if not os.path.exists(regions_path):
            regions_path = (
                main_dir
                / "resources"
                / runs[scen]
                / "regions_onshore_elec_s_62.geojson"
            )
        regions = gpd.read_file(regions_path).set_index("name")

        for year in years:
            this_network = networks_year[year][scen]

            filename = f"{resultdir}/h2_electrolysis_network_{scen}_{year}.png"
            plot_h2_map(
                this_network,
                regions,
                filename,
                ["H2 Electrolysis"],
                "p_inst",
                country_to_plot,
            )

            # Pie chart with all carriers
            filename = f"{resultdir}/h2_all_network_{scen}_{year}.png"
            carriers = [
                "H2 Electrolysis",
                "SMR",
                "SMR CC",
                "import pipeline-H2",
                "import shipping-H2",
            ]
            plot_h2_map(
                this_network,
                regions,
                filename,
                carriers,
                "produced",
                country_to_plot,
            )

            # Pie chart with net flows
            filename = f"{resultdir}/h2_net_flows_network_{scen}_{year}.png"
            carriers = [
                "H2 Electrolysis",
                "SMR",
                "SMR CC",
                "import pipeline-H2",
                "import shipping-H2",
            ]
            plot_h2_map(
                this_network,
                regions,
                filename,
                carriers,
                "produced",
                country_to_plot,
                True,
            )

            # Map with H2 storage only
            filename = f"{resultdir}/h2_storage_{scen}_{year}.png"
            plot_h2_storage_map(
                this_network, regions, filename, country_to_plot
            )





def plot_h2_map(
    network,
    regions,
    save_path,
    carriers,
    type,
    country_to_plot,
    plot_flows=False,
):
    """
    Creates 3 different maps as described in plot_h2_map_years. Output
    is dependent on 'carriers', 'type' ('produced', 'p_inst') and
    'plot_flows' (boolean).

    Parameters
    ----------
    network : pypsa.Network
        network of one year and scenario
    regions : geopandas.GeoDataFrame
        gpd df with region geometries
    save_path : str or pathlib.Path
        string of path + filename
    carriers : list of str
        list of relevant carriers (like ['H2 Electrolysis', 'SMR',
        'SMR CC', 'import pipeline-H2',...])
    type : str
        string of H2 existence ('p_inst', 'produced')
    country_to_plot : str
        string of region to be plotted
    plot_flows : bool, optional
        boolean if flows are taken into account, by default False

    Returns
    -------
    None
    """
    n_h2_single = network.copy()
    if "H2 pipeline" not in n_h2_single.links.carrier.unique():
        return
    assign_location(n_h2_single)

    # Get H2 storage + filter regions
    h2_storage = n_h2_single.stores.query("carrier == 'H2'")
    regions["H2"] = (
        h2_storage.groupby(h2_storage.bus.map(n_h2_single.buses.location))
        .e_nom_opt.sum()
        .div(1e6)
    )  # TWh
    regions["H2"] = regions["H2"].where(regions["H2"] > 0.1).fillna(0.0)

    ## Calculation
    # Settings / bounds
    bus_size_factor = {
        "p_inst": 1e5,
        "produced": 2e8,
    }
    linewidth_factor = 9e3
    # MW below which not drawn
    line_lower_threshold = 750

    # Drop non-electric buses so they don't clutter the plot
    n_h2_single.buses.drop(
        n_h2_single.buses.index[n_h2_single.buses.carrier != "AC"],
        inplace=True,
    )
    # Calculate bus sizes
    bus_sizes = get_bus_sizes(
        bus_size_factor[type], carriers, n_h2_single, type
    )
    # Drop all links which are not H2 pipelines
    n_h2_single.links.drop(
        n_h2_single.links.index[
            ~n_h2_single.links.carrier.str.contains("H2 pipeline")
        ],
        inplace=True,
    )

    # Calculate flow
    flow_factor = {
        True: 1e3,
        False: 0,
    }
    flow_direction = get_bus_sizes(
        bus_size_factor[type],
        ["H2 pipeline", "H2 pipeline retrofitted", "H2 pipeline (Kernnetz)"],
        n_h2_single,
        "produced",
        rename=False,
    )
    flow_direction.rename(
        index=lambda x: re.sub("-20.*$", "", x), level=0, inplace=True
    )
    flow_direction.index = flow_direction.index.droplevel(1)
    flow_direction = flow_direction.groupby(level=0).sum()
    flow = pd.concat(
        [flow_direction * flow_factor[plot_flows]],
        keys=["Link"],
        names=["Components"],
    )

    # Initialize H2 new, retro and inframap
    h2_new = n_h2_single.links[(n_h2_single.links.carrier == "H2 pipeline")]
    h2_retro = n_h2_single.links[
        (n_h2_single.links.carrier == "H2 pipeline retrofitted")
    ]
    h2_inframap = n_h2_single.links[
        (n_h2_single.links.carrier == "H2 pipeline (Kernnetz)")
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
    link_widths_total = h2_total / linewidth_factor
    n_h2_single.links.rename(index=lambda x: x.split("-2")[0], inplace=True)
    n_h2_single.links = n_h2_single.links.groupby(level=0).agg(
        {
            "p_nom_opt": sum,
            "bus0": "first",
            "bus1": "first",
            "carrier": "first",
        }
    )
    link_widths_total = link_widths_total.reindex(
        n_h2_single.links.index
    ).fillna(0.0)
    link_widths_total[n_h2_single.links.p_nom_opt < line_lower_threshold] = 0.0
    # H2 infra
    h2_infra = n_h2_single.links.p_nom_opt.where(
        n_h2_single.links.carrier == "H2 pipeline (Kernnetz)", other=0.0
    )
    link_widths_h2infra = h2_infra / linewidth_factor
    link_widths_h2infra[n_h2_single.links.p_nom_opt < line_lower_threshold] = (
        0.0
    )
    # H2 retro
    retro = (
        n_h2_single.links.p_nom_opt.where(
            n_h2_single.links.carrier == "H2 pipeline retrofitted", other=0.0
        )
        + h2_infra
    )
    link_widths_retro = retro / linewidth_factor
    link_widths_retro[n_h2_single.links.p_nom_opt < line_lower_threshold] = 0.0

    n_h2_single.links.bus0 = n_h2_single.links.bus0.str.replace(" H2", "")
    n_h2_single.links.bus1 = n_h2_single.links.bus1.str.replace(" H2", "")

    ## Plot
    # Updated stylesheet (ignore figsize)
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    proj = ccrs.EqualEarth()
    regions = regions.to_crs(proj.proj4_init)
    fig, ax = plt.subplots(
        figsize=(4.72, 6.29), subplot_kw={"projection": proj}
    )

    # Set plot options
    color_h2_pipe = "#E8C5FF"
    color_retrofit = "#BF40BF"
    color_h2infra = "#5D3FD3"
    bus_colors = {
        "H2 Electrolysis": "#ff29d9",
        "SMR": "#301934",
        "SMR CC": "#870c71",
        "import pipeline-H2": "#25c49a",
        "import shipping-H2": "#98FB98",
    }
    map_opts = {
        "boundaries": boundary_network_plots(
            country_to_plot
        ),
        "color_geomap": {"ocean": "white", "land": "white"},
    }
    if plot_flows is True:
        link_widths_total = 0.3
        link_widths_retro = 0
        link_widths_h2infra = 0
        color_h2_pipe = "#499a9c"

    # Plot H2
    # H2 total with flow
    n_h2_single.plot(
        geomap=True,
        bus_sizes=bus_sizes,
        bus_colors=bus_colors,
        flow=flow,
        link_colors=color_h2_pipe,
        link_widths=link_widths_total,
        branch_components=["Link"],
        ax=ax,
        **map_opts,
    )
    # H2 retrofit
    n_h2_single.plot(
        geomap=True,
        bus_sizes=0,
        link_colors=color_retrofit,
        link_widths=link_widths_retro,
        branch_components=["Link"],
        ax=ax,
        **map_opts,
    )
    # H2 infrastructure
    n_h2_single.plot(
        geomap=True,
        bus_sizes=0,
        link_colors=color_h2infra,
        link_widths=link_widths_h2infra,
        branch_components=["Link"],
        ax=ax,
        **map_opts,
    )

    # Plot regions
    vmax = 3.1
    if (max(regions["H2"]) if not regions["H2"].empty else 0) > vmax:
        print(
            f"Warning! The H2 storage is higher than the axis limit({vmax}) "
            f"in the following"
            f' regions:\n{regions["H2"][regions["H2"] > vmax]}'
        )
    regions.loc[regions.H2 > 0].plot(
        ax=ax,
        column="H2",
        cmap="Blues",
        legend=True,
        vmax=vmax,
        vmin=0,
        legend_kwds={
            "label": "Hydrogen Storage [TWh]",
            "shrink": 0.5,
            "extend": "max",
        },
    )
    regions.boundary.plot(
        ax=ax,
        color="gray",
        linewidth=0.2,
    )

    # Legend
    sizes_type = {
        "p_inst": [50, 10],
        "produced": [200, 50],
    }
    unit = {
        "p_inst": "GW",
        "produced": "TWh",
    }
    unit_factor = {
        "p_inst": 1e3,
        "produced": 1e6,
    }
    labels = [f"{s} {unit[type]}" for s in sizes_type[type]]
    sizes = [
        s / bus_size_factor[type] * unit_factor[type] for s in sizes_type[type]
    ]
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
        bbox_to_anchor=(0, 1.01),
        labelspacing=0.3,
        handletextpad=0,
        frameon=True,
        facecolor="white",
        framealpha=1.0,
    )
    add_legend_circles(
        ax,
        sizes,
        labels,
        srid=n_h2_single.srid,
        patch_kw=dict(facecolor="lightgrey"),
        legend_kw=legend_kw,
    )

    # Add legend for linewidth
    if plot_flows is False:
        sizes = [50, 20]
        labels = [f"{s} GW" for s in sizes]
        scale = 1e3 / linewidth_factor
        sizes = [s * scale for s in sizes]

        legend_kw = dict(
            loc="upper left",
            bbox_to_anchor=(0, 0.9),
            labelspacing=0.3,
            handletextpad=1.0,
            frameon=True,
            facecolor="white",
            framealpha=1.0,
        )
        add_legend_lines(
            ax,
            sizes,
            labels,
            patch_kw=dict(color="lightgrey"),
            legend_kw=legend_kw,
        )

        colors = [bus_colors[c] for c in carriers] + [
            color_h2infra,
            color_h2_pipe,
            color_retrofit,
        ]
        labels = carriers + [
            "German H$_{2}$-Core Network & H$_{2}$-Infrastructure Map",
            "Endogenous new pipeline",
            "Endogenous repurposed pipeline",
        ]
    else:
        colors = [bus_colors[c] for c in carriers] + [color_h2_pipe]
        labels = carriers + ["Net Energy Flow (TWh)"]

    # Add legend for colormapping
    legend_kw = dict(
        loc="lower left",
        bbox_to_anchor=(0, 1),
        frameon=False,
    )
    add_legend_patches(ax, colors, labels, legend_kw=legend_kw)

    plt.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close()


def plot_h2_storage_map(network, regions, save_path, country_to_plot):
    """
    Creates a map that shows the hydrogen storage in more distinct
    colors than the plot with the network.

    Parameters
    ----------
    network : pypsa.Network
        network of one year and scenario
    regions : geopandas.GeoDataFrame
        gpd df with region geometries
    save_path : str or pathlib.Path
        string of path + filename
    country_to_plot : str
        string of region to be plotted

    Returns
    -------
    None
    """
    n_h2_storage = network.copy()

    h2_storage = n_h2_storage.stores.query("carrier == 'H2'")
    regions["H2"] = (
        h2_storage.groupby(h2_storage.bus.map(n_h2_storage.buses.location))
        .e_nom_opt.sum()
        .div(1e6)
    )  # TWh
    regions["H2"] = regions["H2"].where(regions["H2"] > 0.1).fillna(0.0)

    # Plot
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    proj = ccrs.EqualEarth()
    regions = regions.to_crs(proj.proj4_init)
    fig, ax = plt.subplots(subplot_kw={"projection": proj})


    boundaries = boundary_network_plots(country_to_plot)
    vmax = 3.1
    if (max(regions["H2"]) if not regions["H2"].empty else 0) > vmax:
        print(
            f"Warning! The H2 storage is higher than the axis limit({vmax}) "
            f"in the following"
            f' regions:\n{regions["H2"][regions["H2"] > vmax]}'
        )
    # Colormapping for regions with not zero H2
    regions.plot(
        ax=ax,
        column="H2",
        cmap="gnuplot",
        legend=True,
        vmax=vmax,
        vmin=0,
        legend_kwds={
            "label": "Hydrogen Storage [TWh]",
            "shrink": 0.5,
            "extend": "max",
        },
    )
    # Region boundaries
    regions.boundary.plot(
        ax=ax,
        color="white",
        linewidth=0.2,
    )
    ax.set_extent(boundaries, crs=ccrs.PlateCarree())
    plt.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close()




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
    sizes = np.atleast_1d(sizes)
    labels = np.atleast_1d(labels)
    assert len(sizes) == len(
        labels
    ), "Sizes and labels must have the same length."
    handles = [plt.Line2D([0], [0], linewidth=s, **patch_kw) for s in sizes]

    legend = ax.legend(handles, labels, **legend_kw)
    ax.get_figure().add_artist(legend)


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
        df of filtered network (index contains 'H2')
    drop_direction : bool, optional
        boolean (drops flow direction), by default False

    Returns
    -------
    pandas.DataFrame
        df with overall capacity
    """
    # Drop reversed pipelines
    reversed_pipes = df.query('index.str.contains("-reversed")').index
    df = df.drop(reversed_pipes)
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


def get_bus_sizes(
    bus_size_factor: float,
    carriers: List[str],
    n_h2_single: pypsa.Network,
    type: str,
    rename: bool = True,
):
    """
    Calculate bus_sizes for plot map.

    Parameters
    ----------
    bus_size_factor : float
        float factor
    carriers : List[str]
        list of carriers (like ['H2 Electrolysis', 'SMR', 'SMR CC',
        'import pipeline-H2',...])
    n_h2_single : pypsa.Network
        network of one year and scenario
    type : str
        string of type ('p_inst', 'produced')
    rename : bool, optional
        boolean to rename with regex_mapping, by default True

    Returns
    -------
    pandas.Series
        series with bus sizes per region
    """
    carrier_mapping = {
        "H2 Electrolysis": "links",
        "SMR": "links",
        "SMR CC": "links",
        "import pipeline-H2": "generators",
        "import shipping-H2": "generators",
        "H2 pipeline": "links",
        "H2 pipeline retrofitted": "links",
        "H2 pipeline (Kernnetz)": "links",
    }
    bus_mapping = {
        "H2 Electrolysis": "p1",
        "SMR": "p1",
        "SMR CC": "p1",
        "import pipeline-H2": "p",
        "import shipping-H2": "p",
        "H2 pipeline": "p0",
        "H2 pipeline retrofitted": "p0",
        "H2 pipeline (Kernnetz)": "p0",
    }
    regex_mapping = {
        "H2 Electrolysis": "H2 Electrolysis",
        "SMR": "SMR",
        "SMR CC": "SMR CC",
        "import pipeline-H2": "pipeline-H2",
        "import shipping-H2": "shipping-H2",
    }
    t_suffix = "_t"

    # Calculate bus sizes dependent on 'p_inst'
    if type == "p_inst":
        elec = n_h2_single.links[
            n_h2_single.links.carrier.isin(carriers)
        ].index
        bus_sizes = (
            n_h2_single.links.loc[elec, "p_nom_opt"]
            .groupby([n_h2_single.links["bus0"], n_h2_single.links.carrier])
            .sum()
            / bus_size_factor
        )
        # Make a fake MultiIndex so that area is correct for legend
        bus_sizes.rename(
            index=lambda x: x.replace(" H2", ""), level=0, inplace=True
        )

    # Calculate bus sizes dependent on 'produced'
    if type == "produced":
        snapshots = n_h2_single.snapshot_weightings.generators
        bus_sizes_list = []
        for carrier_name in carriers:
            network_attribute = getattr(
                n_h2_single, carrier_mapping[carrier_name]
            )
            carrier_names_unfiltered = network_attribute[
                network_attribute.carrier.isin([carrier_name])
            ].index
            bus_sizes = (
                getattr(
                    getattr(
                        n_h2_single, carrier_mapping[carrier_name] + t_suffix
                    ),
                    bus_mapping[carrier_name],
                )
                .loc[:, carrier_names_unfiltered]
                .mul(snapshots, axis=0)
                .sum()
                .abs()
                / bus_size_factor
            )
            bus_sizes.index = pd.MultiIndex.from_product(
                [bus_sizes.index, [carrier_name]]
            )
            if rename is True:
                bus_sizes.rename(
                    index=lambda x: re.sub(
                        f" {regex_mapping[carrier_name]}.*$", "", x
                    ),
                    level=0,
                    inplace=True,
                )
            bus_sizes_list.append(bus_sizes)
        bus_sizes = pd.concat(bus_sizes_list)
        bus_sizes = bus_sizes.groupby(level=[0, 1]).sum()

    return bus_sizes


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

    plot_h2_map_years(
        networks_year,
        main_dir,
        resultdir,
        years,
        scenarios,
        runs,
        country_to_plot,
    )
