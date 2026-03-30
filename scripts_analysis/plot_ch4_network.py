import os
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd
import pypsa
from pypsa.plot import add_legend_circles, add_legend_lines, add_legend_patches

from networks_regional_dictionary import boundary_network_plots
from common import log


def plot_ch4_map_years(
    networks_year, resultdir, years, scenarios, country_to_plot
):
    """
    Creates map of CH4 grid + sources (especially for 'fossil gas',
    'methanation', 'biogas') in the region 'country_to_plot' for one
    year and scenario by calling plot function. With the parameter
    'capa' it is possible to plot 'gas demand' (see plot function).

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
    log("Starting: plot_ch4_map_years")

    for scen in scenarios:
        for year in years:
            this_network = networks_year[year][scen]

            filename = f"{resultdir}/ch4_network_{scen}_{year}.png"
            plot_ch4_map(this_network, filename, country_to_plot)

    log("Done: plot_ch4_map_years")



def plot_ch4_map(network, filename, country_to_plot, capa=True):
    """
    Creates map as described in plot_ch4_map_years.

    Parameters
    ----------
    network : pypsa.Network
        network of one year and scenario
    filename : str
        string of path + filename
    country_to_plot : str
        string of region to be plotted
    capa : bool, optional
        boolean for sources (True) or demand (False), by default True

    Returns
    -------
    None
    """
    n_ch4 = network.copy()
    assign_location(n_ch4)

    # Setting bounds
    bus_size_factor = 1e5
    linewidth_factor = 1e4
    # MW below which not drawn
    line_lower_threshold = 1e3

    # Drop non-electric buses so they don't clutter the plot
    n_ch4.buses.drop(
        n_ch4.buses.index[n_ch4.buses.carrier != "AC"], inplace=True
    )

    if capa:
        fossil_carrier = [
            "import lng gas",
            "import pipeline gas",
            "production gas",
        ]
        fossil_gas_i = n_ch4.generators[
            n_ch4.generators.carrier.isin(fossil_carrier)
        ].index
        fossil_gas = (
            n_ch4.generators.loc[fossil_gas_i].groupby("bus").sum().p_nom_opt
            / bus_size_factor
        )
        fossil_gas.rename(index=lambda x: x.replace(" gas", ""), inplace=True)
        fossil_gas = fossil_gas.reindex(n_ch4.buses.index).fillna(0)
        # Make a fake MultiIndex so that area is correct for legend
        fossil_gas.index = pd.MultiIndex.from_product(
            [fossil_gas.index, ["fossil gas"]]
        )

        # Calculate methanation
        # Data from generators
        import_carrier = ["import pipeline-syngas", "import shipping-syngas"]
        import_gas_i = n_ch4.generators[
            n_ch4.generators.carrier.isin(import_carrier)
        ].index
        import_gas = (
            n_ch4.generators.loc[import_gas_i].groupby("bus").sum().p_nom_opt
            / bus_size_factor
        )
        import_gas.rename(
            index=lambda x: x.replace(" syngas", ""), inplace=True
        )
        import_gas = import_gas.reindex(n_ch4.buses.index).fillna(0)
        # Data from links
        sabatier_i = n_ch4.links.query("carrier == 'Sabatier'").index
        sabatier = (
            n_ch4.links.loc[sabatier_i].groupby("bus1").sum().p_nom_opt
            / bus_size_factor
        )
        sabatier = (
            sabatier.groupby(sabatier.index)
            .sum()
            .rename(index=lambda x: x.replace(" gas", ""))
        )
        methanation = sabatier + import_gas
        # Make a fake MultiIndex so that area is correct for legend
        methanation.index = pd.MultiIndex.from_product(
            [methanation.index, ["methanation"]]
        )

        # Calculate biogas
        biogas_i = n_ch4.links.filter(like="biogas to gas", axis=0).index
        biogas = (
            n_ch4.links.loc[biogas_i].groupby("bus1").sum().p_nom_opt
            / bus_size_factor
        )
        biogas.rename(index=lambda x: x.replace(" gas", ""), inplace=True)
        # Make a fake MultiIndex so that area is correct for legend
        biogas.index = pd.MultiIndex.from_product([biogas.index, ["biogas"]])

        # Put data together
        bus_sizes = pd.concat([fossil_gas, methanation, biogas])
        bus_sizes.sort_index(inplace=True)

    else:
        # Calculate demand
        bus_size_factor *= 1e3
        gas_loads = (
            (
                n_ch4.snapshot_weightings.generators
                @ n_ch4.loads_t.p.filter(like="gas")
            )
            .groupby(n_ch4.loads.filter(like="gas", axis=0).bus)
            .sum()
        )
        gas_loads = gas_loads / bus_size_factor
        # Change the index of gas_loads so the string terminates
        # before the second whitespace
        gas_loads = gas_loads.rename(
            index=lambda x: " ".join(x.split(" ")[:2])
        )
        gas_loads = gas_loads.reindex(n_ch4.buses.index).fillna(0)
        # Make a fake MultiIndex so that area is correct for legend
        gas_loads.index = pd.MultiIndex.from_product(
            [gas_loads.index, ["gas demand"]]
        )
        bus_sizes = gas_loads
        bus_sizes.sort_index(inplace=True)

    # Drop all links which are not gas pipelines
    to_remove = n_ch4.links.index[
        ~n_ch4.links.carrier.str.contains("gas pipeline")
    ]
    n_ch4.links.drop(to_remove, inplace=True)

    # Group pipelines and drop reversed
    n_ch4.links = group_pipes_CH4(n_ch4.links, drop_direction=True)
    # Calculate linewidth
    link_widths = n_ch4.links.p_nom_opt / linewidth_factor
    link_widths[n_ch4.links.p_nom_opt < line_lower_threshold] = 0.0

    n_ch4.links.bus0 = n_ch4.links.bus0.str.replace(" gas", "")
    n_ch4.links.bus1 = n_ch4.links.bus1.str.replace(" gas", "")

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})

    # Set color options
    if capa:
        bus_colors = {
            "fossil gas": "#e05b09",
            "methanation": "#c44ce6",
            "biogas": "seagreen",
        }
    else:
        bus_colors = {"gas demand": "#e05b09"}
    # Color for gas pipeline
    color = "#f08080"

    # Plot
    n_ch4.plot(
        bus_sizes=bus_sizes,
        bus_colors=bus_colors,
        link_colors=color,
        link_widths=link_widths,
        branch_components=["Link"],
        boundaries=boundary_network_plots(country_to_plot),
        ax=ax,
    )

    ## Legend
    # Pie charts dependent on capa
    if capa:
        # Set legend options (labels + sizes)
        sizes = [100, 10]
        labels = [f"{s} GW" for s in sizes]
        sizes = [s / bus_size_factor * 1e3 for s in sizes]
        original_bounds = [
            n_ch4.buses.x.min() - 5,
            n_ch4.buses.x.max() + 5,
            n_ch4.buses.y.min() - 5,
            n_ch4.buses.y.max() + 5,
        ]
        are_equal = original_bounds == boundary_network_plots(country_to_plot)
        if are_equal == False:
            y_area = original_bounds[-1] - original_bounds[-2]
            x_area = original_bounds[1] - original_bounds[0]
            y_new = (
                boundary_network_plots(country_to_plot)[-1]
                - boundary_network_plots(country_to_plot)[-2]
            )
            x_new = (
                boundary_network_plots(country_to_plot)[1]
                - boundary_network_plots(country_to_plot)[0]
            )
            sizes = [
                sizes[i] * (x_new * y_new) / (x_area * y_area)
                for i in range(0, len(sizes))
            ]

        # Add legend for pie charts
        legend_kw = dict(
            loc="upper left",
            bbox_to_anchor=(0.3, 1.15),
            labelspacing=0.3,
            handletextpad=0,
            title="gas sources",
            frameon=True,
            facecolor="white",
            framealpha=1.0,
        )
        add_legend_circles(
            ax,
            sizes,
            labels,
            srid=n_ch4.srid,
            patch_kw=dict(facecolor="lightgrey"),
            legend_kw=legend_kw,
        )

    else:
        # Set legend options (labels + sizes)
        sizes = [100, 10]
        labels = [f"{int(s)} TWh" for s in sizes]
        sizes = [s / bus_size_factor * 1e6 for s in sizes]

        # Add legend for pie charts
        legend_kw = dict(
            loc="upper left",
            bbox_to_anchor=(0.25, 1.15),
            labelspacing=0.8,
            frameon=False,
            handletextpad=1,
            title="gas demand",
        )
        add_legend_circles(
            ax,
            sizes,
            labels,
            srid=n_ch4.srid,
            patch_kw=dict(facecolor="#e05b09"),
            legend_kw=legend_kw,
        )

    # Add legend for linewidth
    # Set legend options (labels + sizes
    sizes = [50, 10]
    labels = [f"{s} GW" for s in sizes]
    scale = 1e3 / linewidth_factor
    sizes = [s * scale for s in sizes]
    # Add legend
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
        patch_kw=dict(color=color),
        legend_kw=legend_kw,
    )

    # Add legend for colormapping
    colors = list(bus_colors.values())
    labels = list(bus_colors.keys())
    if capa:
        legend_kw = dict(
            bbox_to_anchor=(0.5, 1.1),
            ncol=3,
            frameon=False,
        )
        add_legend_patches(
            ax,
            colors,
            labels,
            legend_kw=legend_kw,
        )

    plt.tight_layout()
    fig.savefig(filename, bbox_inches="tight")
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
            f"gas pipeline {x.bus0.replace(' gas', '')} -> "
            f"{x.bus1.replace(' gas', '')}"
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

    # Specify for which country network plots are generated
    country_to_plot = "EU27"

    plot_ch4_map_years(
        networks_year, resultdir, years, scenarios, country_to_plot
    )
