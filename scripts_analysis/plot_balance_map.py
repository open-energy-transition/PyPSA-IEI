import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import cartopy.crs as ccrs
import geopandas
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import pypsa
import yaml
from pypsa.plot import add_legend_circles, add_legend_lines, add_legend_patches
from pypsa.statistics import get_transmission_carriers

from common import import_network, log
from networks_regional_dictionary import boundary_network_plots

# Adapted from
# Fabian Hofmann, Christoph Tries, Fabian Neumann, Elisabeth Zeyen, Tom
# Brown (2024). Code for "H2 and CO2 Network Strategies for the European
# Energy System". https://arxiv.org/abs/2402.19042v2;
# https://github.com/FabianHofmann/carbon-networks

warnings.filterwarnings("ignore", category=UserWarning)




def plot_balance_map_years(
    networks_scen_years: Dict[str, Dict[str, pypsa.Network]],
    out_directory: Path,
    years: List[str],
    scenarios: List[str],
    config: Dict[str, Dict],
    off_regions: geopandas.GeoDataFrame,
    country_to_plot: str,
    sel_scen: str,
):
    """
    Creates 2 different types of balance maps for given carriers and
    for every year and scenario by calling plot functions. Carriers
    come from config.plotting.yaml and could be 'carbon', 'co2',
    'electricity', 'gas', 'hydrogen'.
        - balance map for carrier and one scenario and year
        - balance map for carrier and one year. Difference between
          selected scenario and the others is plotted.

    Parameters
    ----------
    networks_scen_years : Dict[str, Dict[str, pypsa.Network]]
        dict with networks per year and scenario ({year: {scen: network}})
    out_directory : Path
        path of resultdirectory
    years : List[str]
        list of relevant years
    scenarios : List[str]
        list of scenarios
    config : Dict[str, Dict]
        dict with data that come from config.plotting.yaml
    off_regions : geopandas.GeoDataFrame
        gpd df with offshore regions geometry
    country_to_plot : str
        string of region to be plotted
    sel_scen : str
        string of selected scenario

    Returns
    -------
    None
    """
    log("Starting: plot_balance_map_years")

    # Initialize + plot for every scenario and year
    buses = dict()
    flows = dict()
    for scen in scenarios:
        buses[scen] = dict()
        flows[scen] = dict()
        for year in years:
            buses[scen][year] = dict()
            flows[scen][year] = dict()

            # Create plot for every carrier
            # ['carbon', 'co2', 'electricity', 'gas', 'hydrogen']
            for kind in config["constants"]["kinds"]:
                # Calculate data
                (
                    buses[scen][year][kind],
                    flows[scen][year][kind],
                    df_carriers,
                ) = calculate_balance_components(
                    config, networks_scen_years[year][scen], kind
                )
                # Plot
                plot_balance_maps(
                    config,
                    out_directory,
                    networks_scen_years[year][scen],
                    scen,
                    year,
                    off_regions,
                    country_to_plot,
                    kind,
                    buses[scen][year][kind],
                    flows[scen][year][kind],
                    df_carriers,
                )

    # Create plot for difference between scenarios
    generate_difference_plots(
        sel_scen,
        scenarios,
        years,
        buses,
        flows,
        out_directory,
        networks_scen_years,
        df_carriers,
        config,
        country_to_plot,
        off_regions,
    )

    log("Done: plot_balance_map_years")


def load_config(directory: Path) -> Dict[str, Dict]:
    """
    Loads configuration file for plotting.

    Parameters
    ----------
    directory : Path
        path to file

    Returns
    -------
    Dict[str, Dict]
        dict with data of config file
    """
    with open(directory, "r") as yamlfile:
        conf = yaml.load(yamlfile, Loader=yaml.FullLoader)
    return conf




def generate_difference_plots(
    scen1,
    scenarios,
    years,
    buses,
    flows,
    out_directory,
    networks_scen_years,
    df_carriers,
    config,
    country_to_plot,
    off_regions,
):
    """
    Calculates difference between a selected scenario and the other
    scenarios and calls plot function.

    Parameters
    ----------
    scen1 : str
        str name of main scenario for comparison
    scenarios : list of str
        list of str of scenario names
    years : list of int
        list of int with all relevant optimization years
    buses : dict
        dict of pd.Series with bus sizes for all carriers, years and
        scenarios
    flows : dict
        dict of pd.Series with flow numbers for all carriers, years
        and scenarios
    out_directory : pathlib.Path
        Path of the results directory
    networks_scen_years : dict
        dict of pypsa.Network files for all years and scenarios
    df_carriers : dict
        dict of pd.Index with all carriers for all years and scenarios
    config : dict
        dict of the plotting options from the config file
    country_to_plot : str
        str defining the relevant region for plotting
    off_regions : geopandas.GeoDataFrame
        gpd.DataFrame containing the offshore-region shapes

    Returns
    -------
    None
    """
    for scen2 in scenarios:
        if scen1 == scen2:
            continue
        for year in years:

            # Generate a combined network that contains all links
            # and carriers from both networks that are compared
            combined_network = networks_scen_years[year][scen1].copy()
            network_2 = networks_scen_years[year][scen2].copy()
            different_links_idx = [
                index
                for index in networks_scen_years[year][scen2].links.index
                if index not in combined_network.links.index
            ]
            combined_network.import_components_from_dataframe(
                network_2.links.loc[different_links_idx, :], "Link"
            )
            different_carrier_idx = [
                index
                for index in networks_scen_years[year][scen2].carriers.index
                if index not in combined_network.carriers.index
            ]
            combined_network.import_components_from_dataframe(
                network_2.carriers.loc[different_carrier_idx, :], "Carrier"
            )

            # Loop through all carriers that shall be plotted...
            for kind in config["constants"]["kinds"]:
                # ... but skip carbon as a dirty work-around
                if kind == "carbon":
                    continue

                # Extract relevant pd.Series for the bus sizes & define
                # supply and demand components
                buses_1 = buses[scen1][year][kind]
                buses_2 = buses[scen2][year][kind]
                supply_idx = (
                    buses_1[buses_1 >= 0]
                    .index.append(buses_2[buses_2 >= 0].index)
                    .drop_duplicates()
                )
                demand_idx = (
                    buses_1[buses_1 <= 0]
                    .index.append(buses_2[buses_2 <= 0].index)
                    .drop_duplicates()
                )
                buses_diff = buses_1.sub(buses_2, fill_value=0)

                # Extract relevant pd.Series for flow sizes
                flow_1 = flows[scen1][year][kind]
                flow_2 = flows[scen2][year][kind]
                # Identify the direction of flow
                initial_flow_direction_1 = flow_1 / abs(flow_1)
                initial_flow_direction_2 = flow_2 / abs(flow_2)
                # Check, which lines flow in the same directions in
                # both networks
                shared_flows = initial_flow_direction_1.index.intersection(
                    initial_flow_direction_2.index
                )
                same_direction = (
                    initial_flow_direction_1.loc[shared_flows]
                    == initial_flow_direction_2.loc[shared_flows]
                )
                unique_flows_1 = initial_flow_direction_1.index.difference(
                    initial_flow_direction_2.index
                )

                ## Identify buses and flows that are larger in network 1
                ## than in network 2
                # Set all buses that are larger in network 2 to zero
                buses_diff_1 = buses_diff.copy()
                buses_supply_1_idx = buses_diff_1[supply_idx][
                    buses_diff_1[supply_idx] > 0
                ].index
                buses_demand_1_idx = buses_diff_1[demand_idx][
                    buses_diff_1[demand_idx] < 0
                ].index
                buses_diff_1.loc[
                    buses_diff_1.index.difference(
                        buses_supply_1_idx.append(buses_demand_1_idx)
                    )
                ] = 0
                # Set all flows that are larger in network 2 to 0 and ensure
                # the correct flow direction
                same_direction_1 = pd.concat(
                    [
                        same_direction,
                        initial_flow_direction_1.loc[unique_flows_1],
                    ]
                )
                same_direction_1.loc[unique_flows_1] = True
                same_direction_1 = same_direction_1.astype(bool)
                flow_diff_1 = flow_1.sub(flow_2, fill_value=0).loc[
                    initial_flow_direction_1.index
                ]
                new_flow_direction_1 = flow_diff_1 / abs(flow_diff_1)
                flow_diff_1[
                    initial_flow_direction_1 != new_flow_direction_1
                ] = 0
                # For the components that have opposite flow directions in
                # the two networks, only consider the part in network 1.
                flow_diff_1[~same_direction_1] = flow_1[~same_direction_1]

                # Plot everything that is additional in network 1
                # in a balance map
                diff_scen = scen1 + " vs " + scen2
                plot_balance_maps(
                    config,
                    out_directory,
                    combined_network,
                    diff_scen,
                    year,
                    off_regions,
                    country_to_plot,
                    kind,
                    buses_diff_1,
                    flow_diff_1,
                    df_carriers,
                )

                ## Identify buses and flows that are larger in network 2
                ## than in network 1
                # Set all buses that are larger in network 1 to zero
                buses_diff_2 = -buses_diff.copy()
                buses_supply_2_idx = buses_diff_2[supply_idx][
                    buses_diff_2[supply_idx] > 0
                ].index
                buses_demand_2_idx = buses_diff_2[demand_idx][
                    buses_diff_2[demand_idx] < 0
                ].index
                buses_diff_2.loc[
                    buses_diff_2.index.difference(
                        buses_supply_2_idx.append(buses_demand_2_idx)
                    )
                ] = 0
                # Set all flows that are larger in network 1 to 0 and ensure
                # the correct flow direction
                unique_flows_2 = initial_flow_direction_2.index.difference(
                    initial_flow_direction_1.index
                )
                same_direction_2 = pd.concat(
                    [
                        same_direction,
                        initial_flow_direction_2.loc[unique_flows_2],
                    ]
                )
                same_direction_2.loc[unique_flows_2] = True
                same_direction_2 = same_direction_2.astype(bool)
                flow_diff_2 = flow_2.sub(flow_1, fill_value=0).loc[
                    initial_flow_direction_2.index
                ]
                new_flow_direction_2 = flow_diff_2 / abs(flow_diff_2)
                flow_diff_2[
                    initial_flow_direction_2 != new_flow_direction_2
                ] = 0
                # For the components that have opposite flow directions in the
                # two networks, only consider the part in network 2.
                flow_diff_2[~same_direction_2] = flow_2[~same_direction_2]

                # Plot everything that is additional in network 1 in
                # a balance map
                diff_scen = scen2 + " vs " + scen1
                plot_balance_maps(
                    config,
                    out_directory,
                    combined_network,
                    diff_scen,
                    year,
                    off_regions,
                    country_to_plot,
                    kind,
                    buses_diff_2,
                    flow_diff_2,
                    df_carriers,
                    "compare",
                )




def plot_balance_maps(
    config: Dict[str, Dict],
    out_directory: Path,
    network: pypsa.Network,
    scenario: str,
    year: str,
    off_regions: geopandas.GeoDataFrame,
    country_to_plot: str,
    kind: str,
    bus_sizes,
    flow,
    df_carriers,
    mode="single",
):
    """
    Plots balance map with 'kind'-grid of one 'scenario' and 'year' in
    a specific region.

    Parameters
    ----------
    config : Dict[str, Dict]
        dict of the plotting options from the config file
    out_directory : Path
        Path of the results directory
    network : pypsa.Network
        network of one year and scenario
    scenario : str
        string of scenario
    year : str
        string of year
    off_regions : geopandas.GeoDataFrame
        gpd.DataFrame containing the offshore-region shapes
    country_to_plot : str
        str defining the relevant region for plotting
    kind : str
        string of kind ['carbon', 'co2', 'electricity', 'gas',
        'hydrogen']
    bus_sizes : pd.Series
        pd.series with float bus sizes (multiindex: (bus, carrier))
    flow : pd.Series
        pd.series with float flow sizes (multiindex: (line, int))
    df_carriers : pd.Index
        pd.Index with all carriers
    mode : str, optional
        string to identify, whether to use settings for comparison
        ['single', 'compare'], by default "single"

    Results
    -------
    None
    """
    n_balances = network.copy()
    current_bus_sizes = bus_sizes.copy()
    # Drop EU buses so they don't clutter the plot
    n_balances.buses.drop(
        n_balances.buses.query('index.str.contains("EU")').index, inplace=True
    )
    drop_eu = current_bus_sizes.index[
        current_bus_sizes.index.get_level_values(0).str.contains("EU")
    ]
    current_bus_sizes.drop(drop_eu, inplace=True)
    new_nice_names = config["plotting"]["nice_names"]
    n_balances.carriers = n_balances.carriers.replace(new_nice_names)

    if kind != "electricity":
        flow_df = flow.reset_index()
        flow_df.columns = ["type", "index", "value"]
        flow_df.set_index("index", inplace=True)
        merged_df = pd.merge(
            n_balances.links, flow_df, left_index=True, right_index=True
        )
        summed_flow = (
            merged_df.groupby(["bus0", "bus1"])["value"].sum().reset_index()
        )
        summed_flow.columns = ["bus0", "bus1", "summed_flow"]
        new_df = pd.merge(
            merged_df, summed_flow, on=["bus0", "bus1"], how="left"
        )
        new_df.index = merged_df.index
        new_flow = new_df.summed_flow.reset_index()
        new_flow.columns = ["level1", "value"]
        new_flow["level0"] = "Link"
        new_flow.set_index(["level0", "level1"], inplace=True)
        flow = new_flow.value
    # Set plot options for region
    labels = config["labels"]
    if country_to_plot in ["PL_and_Baltics", "Benelux", "EU27"]:
        regional_plotting_options = config["plotting"]["balance_map"][mode][
            country_to_plot
        ]
    else:
        regional_plotting_options = config["plotting"]["balance_map"][mode][
            "EU27"
        ]
    alpha = regional_plotting_options["alpha"]
    region_alpha = regional_plotting_options["region_alpha"]

    # Set colors for every technology
    STANDARD_COLOR = "#faa945"
    carriers = n_balances.carriers.set_index("nice_name")
    carriers.loc["", "color"] = "None"
    for carrier, color in carriers.color.items():
        new_color = STANDARD_COLOR
        if color == "":
            if carrier in config["plotting"]["technology_group_colors"]:
                new_color = config["plotting"]["technology_group_colors"][
                    carrier
                ]
            carriers.loc[carrier, "color"] = new_color
    colors = carriers.color.loc[carriers.index != ""]

    # Set bus sizes + scale
    current_bus_sizes = remove_supply_demand(current_bus_sizes)
    specs = regional_plotting_options[kind]
    bus_scale = float(specs["bus_scale"])
    branch_scale = float(specs["branch_scale"])
    flow_scale = float(specs["flow_scale"])

    # Set branch colors for transmission
    kinds = config["constants"]["carrier_to_buses"].get(kind, [kind])
    _ = get_transmission_carriers(n_balances, bus_carrier=kinds)
    transmission_carriers = _.set_levels(
        n_balances.carriers.nice_name[_.get_level_values(1)], level=1
    )
    branch_colors = {
        c: config["plotting"]["transmission_colors"][kind]
        for c, carrier in transmission_carriers
    }

    # Set bounds/factor for regions
    original_bounds = config["plotting"]["extent"]
    are_equal = original_bounds == boundary_network_plots(country_to_plot)
    if are_equal == False:
        y_area = abs(original_bounds[-1] - original_bounds[-2])
        x_area = abs(original_bounds[1] - original_bounds[0])
        y_new = abs(
            boundary_network_plots(country_to_plot)[-1]
            - boundary_network_plots(country_to_plot)[-2]
        )
        x_new = abs(
            boundary_network_plots(country_to_plot)[1]
            - boundary_network_plots(country_to_plot)[0]
        )
        factor = (x_new * y_new) / (x_area * y_area)
    else:
        factor = 1
    config["plotting"]["extent"] = boundary_network_plots(country_to_plot)

    # Print information for run
    print(f"{year}-{scenario}: {kind}")
    print(bus_scale)
    print(branch_scale)

    ## Plot
    # Updated stylesheet
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    if country_to_plot == "EU27":
        figwidth = 4.13
        pad = -0.075
        plt.rcParams["font.size"] = 10
    else:
        figwidth = 3.15
        pad = 0
        plt.rcParams["font.size"] = 7.5

    fig, ax = plt.subplots(
        figsize=(figwidth, 7),
        subplot_kw={"projection": ccrs.EqualEarth()},
        layout="constrained",
    )

    # For carrier carbon add offshore regions for co2 sequestration
    if kind == "carbon" and len(current_bus_sizes > 0):
        sequestration_sizes = 1
        if "CO$_2$ Sequestration" in df_carriers:
            sequestration_sizes = -current_bus_sizes.loc[
                :, ["CO$_2$ Sequestration"]
            ]  # / 2
            sequestration_sizes = sequestration_sizes.rename(
                lambda x: (
                    x.replace(" offshore", "")
                    if x not in n_balances.buses.index
                    else x
                ),
                level=0,
            )
            to_drop = current_bus_sizes[
                current_bus_sizes.index.get_level_values(0).str.contains(
                    "offshore"
                )
            ].index
            current_bus_sizes = current_bus_sizes.drop(to_drop)
        # Plot sequestration
        n_balances.plot(
            bus_sizes=sequestration_sizes * bus_scale * factor,
            bus_colors=colors,
            bus_alpha=alpha,
            line_widths=0,
            link_widths=0,
            ax=ax,
            color_geomap=False,
            geomap=True,
            boundaries=config["plotting"]["extent"],
        )
        # Plot offshore borders
        off_regions.plot(
            ax=ax,
            facecolor="None",
            edgecolor="darkgrey",
            linewidth=0.1,
            alpha=region_alpha,
            transform=ccrs.PlateCarree(),
            aspect="equal",
        )

    # Plot lines, links, flow, piecharts for all carriers
    fallback = pd.Series()
    n_balances.plot(
        bus_sizes=current_bus_sizes * bus_scale * factor,
        bus_colors=colors,
        bus_alpha=alpha,
        bus_split_circles=True,
        line_widths=flow.get("Line", fallback)
        .abs()
        .reindex(n_balances.lines.index, fill_value=0)
        * branch_scale
        * factor,
        link_widths=flow.get("Link", fallback)
        .abs()
        .reindex(n_balances.links.index, fill_value=0)
        * branch_scale
        * factor,
        line_colors=branch_colors.get("Line", "lightgrey"),
        link_colors=branch_colors.get("Link", "lightgrey"),
        flow=flow * flow_scale,
        ax=ax,
        margin=0.2,
        color_geomap={"border": "darkgrey", "coastline": "darkgrey"},
        geomap=True,
        boundaries=config["plotting"]["extent"],
    )

    # Add legend
    legend_kwargs = {
        "loc": "upper left",
        "frameon": True,
        "framealpha": 1,
        "edgecolor": "None",
        "facecolor": "white",
    }
    # Filter buses inside country_to_plot
    if country_to_plot == "PL_and_Baltics":
        relevant_clusters = [
            "CZ1 0",
            "DE1 7",
            "EE6 0",
            "LT6 0",
            "LV6 0",
            "PL1 0",
            "PL1 1",
            "PL1 2",
            "PL1 3",
            "PL1 4",
        ]
        current_bus_sizes[
            ~current_bus_sizes.index.get_level_values(0).isin(
                relevant_clusters
            )
        ] = 0
    elif country_to_plot == "Benelux":
        relevant_clusters = [
            "BE1 0",
            "DE1 1",
            "DE1 2",
            "DE1 3",
            "DE1 5",
            "DE1 6",
            "DK1 0",
            "DK2 0",
            "FR1 2",
            "LU1 0",
        ]
        current_bus_sizes[
            ~current_bus_sizes.index.get_level_values(0).isin(
                relevant_clusters
            )
        ] = 0
    # Filter carriers by production and consumption for 2 legend columns
    threshold = (
        0.02
        * abs(current_bus_sizes[current_bus_sizes > 0])
        .groupby(level=0)
        .sum()
        .max()
    )
    prod_carriers = (
        current_bus_sizes[current_bus_sizes > threshold]
        .index.unique("carrier")
        .sort_values()
    )
    cons_carriers = (
        current_bus_sizes[current_bus_sizes < -threshold]
        .index.unique("carrier")
        .sort_values()
    )

    # Production
    add_legend_patches(
        ax,
        carriers.color[prod_carriers],
        prod_carriers,
        patch_kw={"alpha": alpha},
        legend_kw={
            "bbox_to_anchor": (0, -pad),
            "ncol": 1,
            "title": "Supply",
            "labelspacing": 0.35,
            **legend_kwargs,
        },
    )
    if kind == "carbon":
        legend_pos = 0.5
    else:
        legend_pos = 0.5
    # Consumption
    add_legend_patches(
        ax,
        carriers.color[cons_carriers],
        cons_carriers,
        patch_kw={"alpha": alpha},
        legend_kw={
            "bbox_to_anchor": (legend_pos, -pad),
            "ncol": 1,
            "title": "Consumption",
            "labelspacing": 0.35,
            **legend_kwargs,
        },
    )
    ax.set_extent(config["plotting"]["extent"])

    ## Add legend for circels + lines
    # Set legend options
    unit_line = specs["unit_line"]
    unit_pie = specs["unit_pie"]
    conversion = float(specs["unit_conversion"])
    legend_bus_sizes = specs["bus_sizes"]
    legend_bus_sizes_two = [
        legend_bus_sizes[i] * factor for i in range(0, len(legend_bus_sizes))
    ]
    if country_to_plot in ["PL_and_Baltics", "Benelux"]:
        label_spacing = 2
        legend_position = 0.8
    else:
        label_spacing = 1
        legend_position = 0.85

    # Circles
    if legend_bus_sizes is not None:
        add_legend_circles(
            ax,
            [s * bus_scale * conversion for s in legend_bus_sizes_two],
            [f"{s} {unit_pie}" for s in legend_bus_sizes],
            legend_kw={
                "bbox_to_anchor": (0, 1),
                "labelspacing": label_spacing,
                **legend_kwargs,
            },
        )

    # Lines
    legend_branch_sizes = specs["branch_sizes"]
    legend_branch_sizes_two = [
        legend_branch_sizes[i] * factor
        for i in range(0, len(legend_branch_sizes))
    ]
    if (legend_branch_sizes is not None) and (len(branch_colors) != 0):
        add_legend_lines(
            ax,
            [s * branch_scale * conversion for s in legend_branch_sizes_two],
            [f"{s} {unit_line}" for s in legend_branch_sizes],
            patch_kw={"color": list(branch_colors.values())[0]},
            legend_kw={
                "bbox_to_anchor": (0, legend_position),
                **legend_kwargs,
            },
        )
    # Include footnote explaining distribution grid.
    if kind == "electricity":
        footnote_position = {
            "EU27": -0.35,
            "PL_and_Baltics": -0.43,
            "Benelux": -0.3,
        }
        ax.text(
            0,
            footnote_position[country_to_plot],
            "$^{1}$End consumers and suppliers from distribution-grid level.",
            transform=ax.transAxes,
            fontsize=plt.rcParams["font.size"] - 2,
            verticalalignment="top",
        )
    # Saving plot
    plt.tight_layout()
    filename = (
        f"{out_directory}/{kind}_{country_to_plot}_balance_map_"
        f"{scenario}_{year}.png"
    )
    fig.savefig(filename, dpi=300, bbox_inches="tight")
    config["plotting"]["extent"] = original_bounds
    plt.close()




def rename_duplicates(bus_sizes_original: pd.Series):
    """
    Appends bus names that occur both on the demand and the supply side
    with the respective string.

    Parameters
    ----------
    bus_sizes_original : pd.Series
        pd.Series containing bus sizes with duplicate indexes

    Returns
    -------
    pd.Series
        pd.Series with renamed indexes for duplicated components
    """
    duplicates_mask = bus_sizes_original.index.duplicated(keep=False)

    index_list = []
    value_list = []

    for is_duplicate, (multi_index, value) in zip(
        duplicates_mask, bus_sizes_original.items()
    ):
        key1, key2 = multi_index
        if is_duplicate:
            if value > 0:
                # Append ' supply' to duplicates with positive values
                new_key = (key1, key2 + " Supply")
            elif value < 0:
                # Append ' demand' to duplicates with negative values
                new_key = (key1, key2 + " Demand")
        else:
            new_key = (
                multi_index  # Keep the original index tuple for non-duplicates
            )

        index_list.append(new_key)
        value_list.append(value)

    return pd.Series(
        value_list,
        index=pd.MultiIndex.from_tuples(
            index_list, names=bus_sizes_original.index.names
        ),
    )


def remove_supply_demand(series):
    """
    Replaces ' Supply' and ' Demand' for carrier in multiindex series.

    Parameters
    ----------
    series : pd.Series
        pd.series with multiindex (bus, carrier)

    Returns
    -------
    pd.Series
        updated pd.series
    """
    # Fetch level 1, replace ' Supply' and ' Demand', then set it back
    level0 = series.index.get_level_values(0)
    level1 = (
        series.index.get_level_values(1)
        .str.replace(" Supply", "")
        .str.replace(" Demand", "")
    )
    series.index = pd.MultiIndex.from_arrays(
        [level0, level1], names=series.index.names
    )
    return series


def calculate_balance_components(
    config: Dict[str, Dict], network: pypsa.Network, kind: str
):
    """
    Calculates bus sizes and flows for an input network.

    Parameters
    ----------
    config : Dict[str, Dict]
        dict containing all options for plotting balance maps
    network : pypsa.Network
        pypsa.Network for extraction of parameters
    kind : str
        str of carrier that should be evaluated

    Returns
    -------
    pd.Series
        series with bus sizes (multiindex: bus, carrier)
    pd.Series
        series with flow sizes
    pd.Index
         index of all carriers for all years and scenarios.
    """
    n_balances = network.copy()

    new_nice_names = config["plotting"]["nice_names"]
    n_balances.carriers = n_balances.carriers.replace(new_nice_names)

    # Get statistic object from pypsa network
    s = n_balances.statistics

    # Get relevant carriers for this kind.
    carriers = config["constants"]["carrier_to_buses"].get(kind, [kind])

    # Calculate dispatch for all components
    grouper = s.groupers.get_bus_and_carrier
    df = s.dispatch(
        bus_carrier=carriers, groupby=grouper, aggregate_time="sum"
    )

    _ = get_transmission_carriers(n_balances, bus_carrier=carriers)
    transmission_carriers = _.set_levels(
        n_balances.carriers.nice_name[_.get_level_values(1)], level=1
    )
    sub = df.loc[["Link"]].drop(
        transmission_carriers.unique(1), level=2, errors="ignore"
    )

    df = pd.concat([df.drop("Link"), sub])
    df = df.rename(lambda x: x.replace(" CC", ""), level=2)
    df = (
        df.groupby(level=[1, 2])
        .sum()
        .rename(n_balances.buses.location, level=0)
    )
    df = df[df.abs() > 1]
    if "" in df.index.get_level_values(0):
        df = df[df.index.get_level_values(0).drop("")]
    df.drop_duplicates(inplace=True)

    # bus_sizes + flow
    bus_sizes = df.sort_index()
    bus_sizes = rename_duplicates(bus_sizes)
    flow = s.transmission(
        groupby=False, bus_carrier=carriers, aggregate_time="sum"
    )

    return bus_sizes, flow, df.index.get_level_values(1)


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
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

    balance_maps_dir = resultdir / "balance_maps"
    if not os.path.exists(balance_maps_dir):
        os.mkdir(balance_maps_dir)

    scenarios = list(runs.keys())
    sel_scen = "scenario_1"

    # load config
    config_dir = main_dir / "config" / "config.plotting.yaml"
    config = load_config(config_dir)

    off_regions_path = (
        main_dir
        / "scripts_analysis"
        / "shapes"
        / "regions_offshore_elec_s_62.geojson"
    )
    off_regions = gpd.read_file(off_regions_path).set_index("name")

    # load all network files from results folder into a nested dictionary
    networks_year = {}
    for year in years:
        curr_networks = {}
        for scen in scenarios:
            path_to_networks = Path(
                f"{main_dir}/results/{runs[scen]}/postnetworks"
            )
            n = import_network(
                path_to_networks / f"{sector_opts}_{year}.nc",
                revert_dac=True,
                offshore_sequestration=True,
                offshore_regions=off_regions,
            )
            curr_networks.update({scen: n})

        networks_year.update({year: curr_networks})

    # Specify for which country network plots are generated
    country_to_plot = "EU27"

    plot_balance_map_years(
        networks_year,
        balance_maps_dir,
        years,
        scenarios,
        config,
        off_regions,
        country_to_plot,
        sel_scen,
    )
