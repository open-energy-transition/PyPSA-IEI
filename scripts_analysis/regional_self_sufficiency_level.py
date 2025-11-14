import os
from datetime import datetime
from itertools import islice
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa
from matplotlib.cm import ScalarMappable


def evaluate_self_sufficiency(
    networks_year,
    scenarios,
    scenario_colors,
    scenarios_comp,
    main_dir,
    resultdir,
    runs,
    years,
):
    """
    Analysis of self sufficiency in europe of H2 and electricity for
    every scenario and every year. Further it compares self sufficiency
    for two selected scenarios.
    This function calls the related plot functions.

    Parameters
    ----------
    networks_year : dict
        dict of years with calculated data per scenario
        ({year: {scenario: df}})
    scenarios : list of str
        list of scenarios
    scenario_colors : dict
        list of scenario colors
    scenarios_comp : list of str
        list of two scenarios to be compared
    main_dir : pathlib.Path
        path of maindirectory
    resultdir : pathlib.Path
        path of resultdirectory
    runs : dict
        dict folders of scenarios
    years : list of int or str
        list of relevant years

    Returns
    -------
    None
    """
    # Initial variables/settings
    eu27_countries = [
        "AT",
        "BE",
        "BG",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
    ]  # excluding Malta and Cyprus
    proj = ccrs.EqualEarth()
    # Region dependent on this boolean
    per_country = True
    # Colors for scenarios to compare
    scenario_colors_comp = {
        key: scenario_colors[key]
        for key in scenario_colors
        if key in scenarios_comp
    }

    # Calculation + plots for every year and scenario
    for year in years:
        # Years 2020 and 2025 not relevant
        if (year == "2020") or (year == "2025"):
            continue

        for scen in scenarios:
            # Get network for year and scenario
            this_network = networks_year[year][scen]
            # Color of current scenario
            color = scenario_colors[scen]

            # Get shapes
            # Regions
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
            regions = (
                gpd.read_file(regions_path)
                .set_index("name")
                .to_crs(proj.proj4_init)
            )
            # Countries
            country_shapes_path = (
                main_dir
                / "scripts_analysis"
                / "shapes"
                / "country_shapes.geojson"
            )
            if not os.path.exists(country_shapes_path):
                country_shapes_path = (
                    main_dir
                    / "resources"
                    / runs[scen]
                    / "country_shapes.geojson"
                )
            country_shapes = (
                gpd.read_file(country_shapes_path)
                .set_index("name")
                .to_crs(proj.proj4_init)
            )

            # Select available locations
            location = (
                this_network.buses.location
                if "location" in this_network.buses.columns
                else pd.Series(
                    this_network.buses.index, index=this_network.buses.index
                )
            )

            # Calculate H2/elec demand + self sufficiency
            demand_h2, self_sufficiency_h2 = calculate_H2_self_sufficiency(
                this_network, location, per_country, eu27_countries
            )
            demand_elec, self_sufficiency_elec = (
                calculate_elec_self_sufficiency(
                    this_network, location, per_country, eu27_countries
                )
            )

            # Plot self suffiency map
            FN = resultdir / (f"elec_self-sufficiency_map_{scen}_{year}.png")
            plot_self_sufficiency(
                demand_elec,
                self_sufficiency_elec,
                regions,
                country_shapes,
                FN,
                per_country,
                year,
                scen,
                carrier="Electricity",
            )
            FN = resultdir / (f"h2_self-sufficiency_map_{scen}_{year}.png")
            plot_self_sufficiency(
                demand_h2,
                self_sufficiency_h2,
                regions,
                country_shapes,
                FN,
                per_country,
                year,
                scen,
                carrier="H2",
            )

            # Plot self sufficiency barcharts
            plot_self_sufficiency_per_country(
                self_sufficiency_h2, resultdir, scen, color, year, carrier="H2"
            )
            plot_self_sufficiency_per_country(
                self_sufficiency_elec,
                resultdir,
                scen,
                color,
                year,
                carrier="Electricity",
            )

            # Extract data for scenario comparison
            if scen == scenarios_comp[0]:
                self_sufficiency_elec_1 = self_sufficiency_elec
                self_sufficiency_h2_1 = self_sufficiency_h2
            elif scen == scenarios_comp[1]:
                self_sufficiency_elec_2 = self_sufficiency_elec
                self_sufficiency_h2_2 = self_sufficiency_h2

        # Compare scenarios
        # Calculate difference
        self_sufficiency_elec_diff = (
            self_sufficiency_elec_1 - self_sufficiency_elec_2
        )
        self_sufficiency_h2_diff = (
            self_sufficiency_h2_1 - self_sufficiency_h2_2
        )
        # Plot self sufficiency difference map
        filename = resultdir / (
            f"h2_self-sufficiency_diff_"
            f"{scenarios_comp[0]}_{scenarios_comp[1]}_{year}.png"
        )
        plot_self_sufficiency_comp(
            self_sufficiency_h2_diff,
            regions,
            country_shapes,
            filename,
            per_country,
            scenario_colors_comp,
            year,
            carrier="H2",
        )
        filename = resultdir / (
            f"elec_self-sufficiency_diff_"
            f"{scenarios_comp[0]}_{scenarios_comp[1]}_{year}.png"
        )
        plot_self_sufficiency_comp(
            self_sufficiency_elec_diff,
            regions,
            country_shapes,
            filename,
            per_country,
            scenario_colors_comp,
            year,
            carrier="Electricity",
        )


def plot_self_sufficiency(
    demand,
    self_sufficiency,
    regions,
    country_shapes,
    FN,
    per_country,
    year,
    scenario,
    carrier,
):
    """
    Plots self sufficiency in Europe for one scenario and year and for
    H2 or electricity.

    Parameters
    ----------
    demand : pd.Series
        series of H2/elec demand
    self_sufficiency : pd.Series
        series of H2/elec self sufficiency
    regions : geopandas.GeoDataFrame
        gpd.DataFrame with region geometry
    country_shapes : geopandas.GeoDataFrame
        gpd.DataFrame with country geometry
    FN : str or pathlib.Path
        string of filename
    per_country : bool
        boolean (plot dependent on per_country)
    year : str or int
        string of year
    scenario : str
        string of scenario
    carrier : str
        string ('H2','Electricity')

    Returns
    -------
    None
    """
    # Select region (dependent on per country)
    if per_country:
        self_sufficiency_regions = country_shapes
    else:
        self_sufficiency_regions = regions

    # Add self_sufficiency column to geometry
    self_sufficiency_regions["self_sufficiency"] = self_sufficiency * 100

    # Set vmax and vmin for self-sufficiency
    if carrier == "Electricity":
        vmax = 150
        vmin = 50
    elif carrier == "H2":
        vmax = 200
        vmin = 0
    # Print warning if self-sufficiency out of bounds
    if max(self_sufficiency_regions["self_sufficiency"]) > vmax:
        over_vmax = self_sufficiency_regions["self_sufficiency"][
            self_sufficiency_regions["self_sufficiency"] > vmax
        ]
        print(
            f"Warning! The {carrier} self-sufficiency is higher than the "
            f"axis limit({vmax}) in {year} in the following"
            f' regions:\n{over_vmax}'
        )

    ## Plot map
    # Updated stylesheet for self-suff map
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})

    # Plot self-sufficiency
    self_sufficiency_regions.plot(
        ax=ax,
        column="self_sufficiency",
        legend=True,
        vmax=vmax,
        vmin=vmin,
        legend_kwds={
            "label": "Self-sufficiency (%)",
            "shrink": 0.7,
            "extend": "max",
        },
    )
    # Add country shapes and region shapes
    country_shapes.plot(
        ax=ax, edgecolor="black", facecolor="none", linewidth=0.5
    )
    regions.plot(ax=ax, edgecolor="grey", facecolor="none", linewidth=0.2)

    # Plot setting + saving
    ax.set_facecolor("white")
    fig.savefig(FN, bbox_inches="tight")
    plt.close(fig)


def plot_self_sufficiency_per_country(
    self_sufficiency, resultdir, scenario, color, year, carrier
):
    """
    Plots barchart of self sufficiency per country for one scenario and
    year and for H2 or electricity.

    Parameters
    ----------
    self_sufficiency : pandas.Series
        series of H2/elec self sufficiency
    resultdir : str or pathlib.Path
        path of resultdirectory
    scenario : str
        string of scenario
    color : str
        string of scenario color
    year : str or int
        string of year
    carrier : str
        string ('H2','Electricity')

    Returns
    -------
    None
    """
    # Drop not relevant countries
    countries_to_drop = ["RS", "BA", "AL", "MK"]
    self_sufficiency = self_sufficiency.drop(countries_to_drop)

    # Sort the series from highest to lowest value
    self_sufficiency_sorted = self_sufficiency.sort_values(ascending=False)

    ## Plot barchart
    # Updated stylesheet for self-suff barchart (essential for fontsize)
    plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
    # Initialize figure (figsize hardcoded; does not match to stylesheet)
    fig, ax = plt.subplots(figsize=(6.2, 2.5))

    # Plot the bar chart with percent values
    bars = ax.bar(
        self_sufficiency_sorted.index,
        self_sufficiency_sorted * 100,
        color=color,
    )

    # Set the color of the 'EU27' bar to blue
    eu27_index = self_sufficiency_sorted.index.get_loc("EU27")
    bars[eu27_index].set_color("#003399")

    # Add exogenous minimum horizontal line for CN and SN
    if (scenario == "CN" or scenario == "SN") and year > "2025":
        # Limits
        limits = {
            "Electricity": {
                "2030": 80,
                "2035": 85,
                "2040": 90,
                "2045": 95,
                "2050": 100,
            },
            "H2": {"2030": 70, "2035": 70, "2040": 70, "2045": 70, "2050": 70},
        }
        limit = limits[carrier][str(year)]
        # Add a horizontal dashed line at 'limit' value + label on the right
        ax.axhline(y=limit, color="dimgray", linestyle="--")
        ax.text(
            ax.get_xlim()[1] * 1.02,
            limit,
            f"Exogenous minimum\nself-sufficiency: {limit}%",
            ha="left",
            va="center",
            color="dimgray",
            fontsize=8,
        )
        if limit < 100:
            ax.axhline(y=110, color="dimgray", linestyle="--")
            ax.text(
                ax.get_xlim()[1] * 0.98,
                112,
                "Exogenous maximum\nself-sufficiency: 110%",
                ha="right",
                va="bottom",
                color="dimgray",
                fontsize=8,
            )
    # Technical: hide label for CE and SE
    else:
        limit = 0.8
        ax.text(
            ax.get_xlim()[1] * 1.02,
            limit,
            f"Exogenous minimum\nself-sufficiency: {limit}%",
            ha="left",
            va="center",
            color="white",
            fontsize=8,
        )
        # Add a horizontal dashed line at 100% + label on the right
        ax.axhline(y=100, color="darkgrey", linestyle="--")
        ax.text(
            ax.get_xlim()[1] * 0.98,
            110,
            "100% self-sufficiency",
            ha="right",
            va="center",
            color="darkgrey",
            fontsize=8,
        )

    # Handling ymax
    ymax = 200
    # Warning message
    if max(self_sufficiency_sorted) > ymax:
        over_ymax = self_sufficiency_sorted[self_sufficiency_sorted > ymax]
        print(
            f"Warning! The {carrier} self-sufficiency is higher than the "
            f"axis limit({ymax}) in {year} in the following"
            f" regions:\n{over_ymax}"
        )
    # Set ylim
    ax.set_ylim(bottom=0, top=ymax)

    # Add text inside bars
    for bar, index in zip(bars, self_sufficiency_sorted.index):
        # Set labelcolors
        if (scenario == "SN") or (scenario == "SE"):
            label_color = "white"
        else:
            label_color = "black"
        if index == "EU27":
            label_color = "#FFD700"
        height = bar.get_height()

        # Add text with color dependent on bar height
        if height < (ymax * 0.1):  # Adjust the threshold to your preference
            label_color = "black"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + ymax / 100 * 2,
                index,
                ha="center",
                va="bottom",
                rotation="vertical",
                color=label_color,
                fontsize=8,
            )
        elif height > ymax:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                ymax / 2,
                index,
                ha="center",
                va="bottom",
                rotation="vertical",
                color=label_color,
                fontsize=8,
            )
        else:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height / 2,
                index,
                ha="center",
                va="center",
                rotation="vertical",
                color=label_color,
                fontsize=8,
            )

    # Further plot settings + saving
    ax.set_xlabel("Country")
    ax.set_ylabel("Self-sufficiency (%)")
    plt.xticks([])
    plt.tight_layout()
    filename = resultdir / (
        f"{carrier}_self-sufficiency_{scenario}_{year}.png"
    )
    plt.savefig(filename)


def plot_self_sufficiency_comp(
    self_sufficiency,
    regions,
    country_shapes,
    FN,
    per_country,
    scenario_colors_comp,
    year,
    carrier,
):
    """
    Plots difference in self sufficiency between two scenarios in
    europe for one year and for H2 or electricity.

    Parameters
    ----------
    self_sufficiency : pandas.Series
        series of H2/elec self sufficiency
    regions : geopandas.GeoDataFrame
        gpd.DataFrame with region geometry
    country_shapes : geopandas.GeoDataFrame
        gpd.DataFrame with country geometry
    FN : str or pathlib.Path
        string of filename
    per_country : bool
        boolean (plot dependent on per_country)
    scenario_colors_comp : dict
        dict of scenario colors ({scenario: colorstring})
    year : str or int
        year of the scenario
    carrier : str
        string ('H2','Electricity')

    Returns
    -------
    None
    """
    # Select scenarios to compare
    scenario1 = next(iter(scenario_colors_comp))
    scenario2 = next(islice(scenario_colors_comp.keys(), 1, 2))

    # Select region (dependent on per country)
    if per_country:
        self_sufficiency_regions = country_shapes
    else:
        self_sufficiency_regions = regions
    self_sufficiency_regions["self_sufficiency"] = self_sufficiency * 100

    ## Plot map
    # Updated stylesheet for self-suff_diff map
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    fig, ax = plt.subplots(subplot_kw={"projection": ccrs.EqualEarth()})

    ## Color mapping
    # Select colors for scenarios
    color1 = scenario_colors_comp[scenario1]
    color2 = scenario_colors_comp[scenario2]
    # Convert the hex color codes to rgb
    color1_rgb = mcolors.hex2color(color2)
    color2_rgb = mcolors.hex2color(color1)
    # Define the color gradients
    colors1 = plt.cm.colors.LinearSegmentedColormap.from_list(
        "", [color1_rgb, (1, 1, 1)]
    )
    colors2 = plt.cm.colors.LinearSegmentedColormap.from_list(
        "", [(1, 1, 1), color2_rgb]
    )
    # Combine them and build a new colormap
    colors = np.vstack(
        (colors1(np.linspace(0.0, 1, 128)), colors2(np.linspace(0, 1, 128)))
    )
    mymap = mcolors.LinearSegmentedColormap.from_list("my_colormap", colors)
    # Normalize colors
    norm = mcolors.TwoSlopeNorm(
        vmin=min(self_sufficiency_regions["self_sufficiency"]),
        vcenter=0,
        vmax=max(self_sufficiency_regions["self_sufficiency"]),
    )

    # Plot self sufficiency
    self_sufficiency_regions.plot(
        ax=ax,
        column="self_sufficiency",
        cmap=mymap,
        norm=norm,
        linewidths=1,
    )
    # Add country shapes and region shapes
    country_shapes.plot(
        ax=ax, edgecolor="black", facecolor="none", linewidth=0.5
    )
    regions.plot(ax=ax, edgecolor="grey", facecolor="none", linewidth=0.2)

    # Add legend for colormapping
    sm = ScalarMappable(cmap=mymap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0)
    # Set colorbar label
    cbar.set_label(
        "Difference in self-sufficiency limits (%)", rotation=270, labelpad=20
    )

    # Generate ticks for colormap legend
    def generate_ticks(max_value, num_ticks=5):
        if max_value < 0:
            sign = -1
        else:
            sign = 1
        order_of_magnitude = round(np.log10(sign * max_value))
        order_of_magnitude_ticks = order_of_magnitude - 1
        ugly_steps = sign * max_value / (num_ticks)
        pretty_steps = round(ugly_steps, -order_of_magnitude_ticks)
        new_ticks = np.arange(0, sign * max_value, pretty_steps)

        if max_value < 0:
            new_ticks = np.flip(new_ticks * sign)

        return new_ticks

    # Customizing ticks
    positive_ticks = generate_ticks(
        max(self_sufficiency_regions["self_sufficiency"])
    )
    negative_ticks = generate_ticks(
        min(self_sufficiency_regions["self_sufficiency"])
    )
    cbar.set_ticks(
        np.concatenate([negative_ticks, positive_ticks[1:]])
    )  # merge ticks and exclude 0 from positive

    # Add text boxes at the top and bottom of the colorbar
    plt.text(
        1,
        1.02,
        f"High self-sufficiency\nin {scenario1}",
        transform=ax.transAxes,
        va="bottom",
    )
    plt.text(
        1,
        -0.02,
        f"High self-sufficiency\nin {scenario2}",
        transform=ax.transAxes,
        va="top",
    )

    # Saving plot
    ax.set_facecolor("white")
    fig.savefig(FN, bbox_inches="tight")
    plt.close(fig)


def group(df, location, network, per_country, b="bus", eu=None):
    """
    Group given dataframe df by bus location or country. The optional
    argument `b` allows clustering by bus0 or bus1 for lines and links.
    If a list of EU countries is given as 'eu', all these countries
    will receive 'EU' as location.

    Parameters
    ----------
    df : pd.DataFrame
        df of data to be grouped
    location : pd.Series
        series of cluster abbreviations
    network : pypsa.Network
        network of one scenario and year
    per_country : bool
        boolean (return dependent on per_country)
    b : str, optional
        string for clustering by bus ('bus0', 'bus1'), by default "bus"
    eu : list, optional
        string for 'EU' as location, by default None

    Returns
    -------
    pd.Series
        df grouped
    """
    if per_country:
        if eu is None:
            return df[b].map(location).map(network.buses.country)
        else:
            group_country = df[b].map(location).map(network.buses.country)
            group_eu_index = group_country.isin(eu)
            group_country[group_eu_index] = "EU27"
            return group_country
    else:
        return df[b].map(location)


def calculate_H2_self_sufficiency(
    network, location, per_country, eu27_countries
):
    """
    Calculates demand and self sufficiency of H2 for given clusters
    with the following steps:
        - Calculate the energy of the hydrogen generation
        - Calculate energy of cross-border hydrogen transport
        - Calculate the energy imported from outside of Europe
        - Calculate the demand for H2 as energy carrier

    Parameters
    ----------
    network : pypsa.Network
        network of one scenario and year
    location : pd.Series
        series of cluster abbreviations
    per_country : bool
        boolean (return dependent on per_country)
    eu27_countries : list of str
        list of eu27 countries

    Returns
    -------
    pd.Series
        series with demand
    pd.Series
        series with self sufficiency of H2 for each country
    """
    # Get network + initialize variables
    n_self_h2 = network.copy()
    p_links = n_self_h2.links_t.p0
    p_generators = n_self_h2.generators_t.p

    ## Create constraint for hydrogen
    # Calculate the energy of the hydrogen generation
    h2_generation_carrier = ["H2 Electrolysis", "SMR CC", "SMR"]
    idx_gen_h2 = n_self_h2.links[
        (n_self_h2.links.carrier.isin(h2_generation_carrier))
    ].index
    efficiencies = n_self_h2.links.loc[idx_gen_h2, "efficiency"]
    generation_p_at_h2bus = p_links.loc[:, idx_gen_h2] * efficiencies
    generation_p_per_country_h2 = generation_p_at_h2bus.groupby(
        group(
            n_self_h2.links.loc[idx_gen_h2],
            location,
            n_self_h2,
            per_country,
            b="bus1",
        ),
        axis=1,
    ).sum()
    generation_e_h2 = (
        (
            generation_p_per_country_h2.multiply(
                n_self_h2.snapshot_weightings.generators, axis=0
            )
        )
    ).sum()
    generation_e_h2["EU27"] = generation_e_h2[
        generation_e_h2.index.isin(eu27_countries)
    ].sum()

    # Calculate energy of cross-border hydrogen transport
    h2_pipe_carrier = [
        "H2 pipeline retrofitted",
        "H2 pipeline",
        "H2 pipeline (Kernnetz)",
    ]
    if per_country:
        idx_cross_border_pipes_h2 = n_self_h2.links[
            (n_self_h2.links.carrier.isin(h2_pipe_carrier))
            & (n_self_h2.links.bus0.str[:2] != n_self_h2.links.bus1.str[:2])
        ].index
    else:
        idx_cross_border_pipes_h2 = n_self_h2.links[
            (n_self_h2.links.carrier.isin(h2_pipe_carrier))
        ].index
    p_pipes_out_per_country = (
        p_links.loc[:, idx_cross_border_pipes_h2]
        .groupby(
            group(
                n_self_h2.links.loc[idx_cross_border_pipes_h2],
                location,
                n_self_h2,
                per_country,
                b="bus0",
            ),
            axis=1,
        )
        .sum()
    )
    e_pipes_out = (
        (
            p_pipes_out_per_country.multiply(
                n_self_h2.snapshot_weightings.generators, axis=0
            )
        )
        .rename({"bus0": "bus"})
        .sum()
    )
    p_pipes_in_per_country = (
        p_links.loc[:, idx_cross_border_pipes_h2]
        .groupby(
            group(
                n_self_h2.links.loc[idx_cross_border_pipes_h2],
                location,
                n_self_h2,
                per_country,
                b="bus1",
            ),
            axis=1,
        )
        .sum()
    )
    e_pipes_in = (
        (
            p_pipes_in_per_country.multiply(
                n_self_h2.snapshot_weightings.generators, axis=0
            )
        )
        .rename({"bus1": "bus"})
        .sum()
    )
    idx_cross_border_pipes_h2_EU = n_self_h2.links[
        (n_self_h2.links.carrier.isin(h2_pipe_carrier))
        & (n_self_h2.links.bus0.str[:2] != n_self_h2.links.bus1.str[:2])
        & ~(
            n_self_h2.links.bus0.str[:2].isin(eu27_countries)
            & n_self_h2.links.bus1.str[:2].isin(eu27_countries)
        )
    ].index
    p_pipes_out_EU = (
        p_links.loc[:, idx_cross_border_pipes_h2_EU]
        .groupby(
            group(
                n_self_h2.links.loc[idx_cross_border_pipes_h2_EU],
                location,
                n_self_h2,
                per_country,
                b="bus0",
                eu=eu27_countries,
            ),
            axis=1,
        )
        .sum()
    )
    e_pipes_out_EU = (
        (
            p_pipes_out_EU.multiply(
                n_self_h2.snapshot_weightings.generators, axis=0
            )
        )
        .rename({"bus0": "bus"})
        .sum()
    )
    p_pipes_in_EU = (
        p_links.loc[:, idx_cross_border_pipes_h2_EU]
        .groupby(
            group(
                n_self_h2.links.loc[idx_cross_border_pipes_h2_EU],
                location,
                n_self_h2,
                per_country,
                b="bus1",
                eu=eu27_countries,
            ),
            axis=1,
        )
        .sum()
    )
    e_pipes_in_EU = (
        (
            p_pipes_in_EU.multiply(
                n_self_h2.snapshot_weightings.generators, axis=0
            )
        )
        .rename({"bus1": "bus"})
        .sum()
    )
    e_pipes_out = pd.concat(
        [e_pipes_out, e_pipes_out_EU[e_pipes_out_EU.index == "EU27"]]
    )
    e_pipes_in = pd.concat(
        [e_pipes_in, e_pipes_in_EU[e_pipes_in_EU.index == "EU27"]]
    )

    # Calculate the energy imported from outside of Europe
    h2_import_gen_carrier = ["import pipeline-H2", "import shipping-H2"]
    idx_h2_import = n_self_h2.generators[
        (n_self_h2.generators.carrier.isin(h2_import_gen_carrier))
    ].index
    if not idx_h2_import.empty:  # some years have no import generators
        p_h2_import_per_country = (
            p_generators.loc[:, idx_h2_import]
            .groupby(
                group(
                    n_self_h2.generators.loc[idx_h2_import],
                    location,
                    n_self_h2,
                    per_country,
                ),
                axis=1,
            )
            .sum()
        )
        e_h2_import = (
            p_h2_import_per_country.multiply(
                n_self_h2.snapshot_weightings.generators, axis=0
            )
        ).sum()
        e_h2_import["EU27"] = e_h2_import[
            e_h2_import.index.isin(eu27_countries)
        ].sum()
        # Calculate import balances for countries/clusters
        local_import_h2 = e_h2_import.add(e_pipes_in, fill_value=0).add(
            -e_pipes_out, fill_value=0
        )
    else:
        # Calculate import balances for countries/clusters
        local_import_h2 = e_pipes_in.add(-e_pipes_out, fill_value=0)

    # Calculate the demand for H2 as energy carrier
    demand_h2 = local_import_h2.add(generation_e_h2, fill_value=0)
    self_sufficiency_h2 = generation_e_h2 / demand_h2
    self_sufficiency_h2 = self_sufficiency_h2.fillna(0)
    return demand_h2, self_sufficiency_h2


def calculate_elec_self_sufficiency(
    network, location, per_country, eu27_countries
):
    """
    Calculates demand and self sufficiency of electricity for given
    clusters with the following steps:
        - Calculate electric energy generated in each country/cluster
        - Calculate total electricity generated in each country/cluster
        - Calculate the net electricity imported per country/cluster
          (with dc links and ac lines)
        - Calculate total demand for electricity

    Parameters
    ----------
    network : pypsa.Network
        network of one scenario and year
    location : pd.Series
        series of cluster abbreviations
    per_country : bool
        boolean (return dependent on per_country)
    eu27_countries : list of str
        list of eu27 countries

    Returns
    -------
    pd.Series
        series with demand
    pd.Series
        series with self sufficiency of electricity for each country
    """
    # Get network + initialize variables
    n_self_elec = network.copy()
    p0_links = n_self_elec.links_t.p0
    p1_links = n_self_elec.links_t.p1
    p_generators = n_self_elec.generators_t.p
    p_storage = n_self_elec.storage_units_t.p
    s0_line = n_self_elec.lines_t.p0
    s1_line = n_self_elec.lines_t.p1

    ## Create electricity constraint
    # Calculate electric energy generated in each country/cluster
    gen_carrier_elec = [
        "offwind-ac",
        "onwind",
        "ror",
        "solar",
        "offwind-dc",
        "solar rooftop",
    ]
    idx_gens_elec = n_self_elec.generators[
        (n_self_elec.generators.carrier.isin(gen_carrier_elec))
    ].index
    p_generation_per_country_elec = (
        p_generators.loc[:, idx_gens_elec]
        .groupby(
            group(
                n_self_elec.generators.loc[idx_gens_elec],
                location,
                n_self_elec,
                per_country,
            ),
            axis=1,
        )
        .sum()
    )
    e_generation_elec = p_generation_per_country_elec.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()

    # Calculate electrical energy generated via storage units
    # in each cluster/country
    storage_unit_carrier = ["hydro"]
    idx_storage_units = n_self_elec.storage_units[
        (n_self_elec.storage_units.carrier.isin(storage_unit_carrier))
    ].index
    p_storage_units_per_country = (
        p_storage.loc[:, idx_storage_units]
        .groupby(
            group(
                n_self_elec.storage_units.loc[idx_storage_units],
                location,
                n_self_elec,
                per_country,
            ),
            axis=1,
        )
        .sum()
    )
    e_storage_units = p_storage_units_per_country.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    # Calculate electrical energy generated via links in each cluster/country
    link_carrier_elec = [  # hydrogen to electricity
        "H2 Fuel Cell",
        "H2 turbine",
        # combined heat and power
        "residential rural micro gas CHP",
        "services rural micro gas CHP",
        "residential urban decentral micro gas CHP",
        "services urban decentral micro gas CHP",
        "urban central gas CHP",
        "urban central gas CHP CC",
        "urban central solid biomass CHP",
        "urban central solid biomass CHP CC",
        # conventional carriers
        "coal",
        "OCGT",
        "CCGT",
        "lignite",
        "nuclear",
        "oil",
        "allam",
    ]
    idx_links_elec = n_self_elec.links[
        (n_self_elec.links.carrier.isin(link_carrier_elec))
    ].index
    efficiencies = n_self_elec.links.loc[idx_links_elec, "efficiency"]
    p_links_at_ac_bus = p0_links.loc[:, idx_links_elec] * efficiencies
    p_links_per_country_elec = p_links_at_ac_bus.groupby(
        group(
            n_self_elec.links.loc[idx_links_elec],
            location,
            n_self_elec,
            per_country,
            b="bus1",
        ),
        axis=1,
    ).sum()
    e_links_elec = p_links_per_country_elec.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    # Calculate total electricity generated in each country/cluster
    generation_elec = e_generation_elec.add(e_storage_units, fill_value=0).add(
        e_links_elec, fill_value=0
    )
    generation_elec["EU27"] = generation_elec[
        generation_elec.index.isin(eu27_countries)
    ].sum()

    # Calculate the cross-border electricity import via DC links
    # per country/cluster
    if per_country:
        idx_dc = n_self_elec.links[
            (n_self_elec.links.carrier == "DC")
            & (
                n_self_elec.links.bus0.str[:2]
                != n_self_elec.links.bus1.str[:2]
            )
        ].index
    else:
        idx_dc = n_self_elec.links[(n_self_elec.links.carrier == "DC")].index
    # For all locations
    p_dc_out = (
        p0_links.loc[:, idx_dc]
        .groupby(
            group(
                n_self_elec.links.loc[idx_dc],
                location,
                n_self_elec,
                per_country,
                b="bus0",
            ),
            axis=1,
        )
        .sum()
    )
    e_dc_out = p_dc_out.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    p_dc_in = (
        -p1_links.loc[:, idx_dc]
        .groupby(
            group(
                n_self_elec.links.loc[idx_dc],
                location,
                n_self_elec,
                per_country,
                b="bus1",
            ),
            axis=1,
        )
        .sum()
    )
    e_dc_in = p_dc_in.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    # For eu27 countries
    p_dc_out_eu = (
        p0_links.loc[:, idx_dc]
        .groupby(
            group(
                n_self_elec.links.loc[idx_dc],
                location,
                n_self_elec,
                per_country,
                b="bus0",
                eu=eu27_countries,
            ),
            axis=1,
        )
        .sum()
    )
    e_dc_out_eu = p_dc_out_eu.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    p_dc_in_eu = (
        -p1_links.loc[:, idx_dc]
        .groupby(
            group(
                n_self_elec.links.loc[idx_dc],
                location,
                n_self_elec,
                per_country,
                b="bus1",
                eu=eu27_countries,
            ),
            axis=1,
        )
        .sum()
    )
    e_dc_in_eu = p_dc_in_eu.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    # Combined
    e_dc_in = pd.concat([e_dc_in, e_dc_in_eu[e_dc_in_eu.index == "EU27"]])
    e_dc_out = pd.concat([e_dc_out, e_dc_out_eu[e_dc_out_eu.index == "EU27"]])

    # Calculate the cross-border electricity import
    # via AC lines per country/cluster
    if per_country:
        idx_lines = n_self_elec.lines[
            (n_self_elec.lines.bus0.str[:2] != n_self_elec.lines.bus1.str[:2])
        ].index
    else:
        idx_lines = n_self_elec.lines.index
    # For all locations
    s_ac_in = (
        -s1_line.loc[:, idx_lines]
        .groupby(
            group(
                n_self_elec.lines.loc[idx_lines],
                location,
                n_self_elec,
                per_country,
                b="bus1",
            ),
            axis=1,
        )
        .sum()
    )
    e_ac_in = s_ac_in.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    s_ac_out = (
        s0_line.loc[:, idx_lines]
        .groupby(
            group(
                n_self_elec.lines.loc[idx_lines],
                location,
                n_self_elec,
                per_country,
                b="bus0",
            ),
            axis=1,
        )
        .sum()
    )
    e_ac_out = s_ac_out.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    # For eu27 countries
    s_ac_in_eu = (
        -s1_line.loc[:, idx_lines]
        .groupby(
            group(
                n_self_elec.lines.loc[idx_lines],
                location,
                n_self_elec,
                per_country,
                b="bus1",
                eu=eu27_countries,
            ),
            axis=1,
        )
        .sum()
    )
    e_ac_in_eu = s_ac_in_eu.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    s_ac_out_eu = (
        s0_line.loc[:, idx_lines]
        .groupby(
            group(
                n_self_elec.lines.loc[idx_lines],
                location,
                n_self_elec,
                per_country,
                b="bus0",
                eu=eu27_countries,
            ),
            axis=1,
        )
        .sum()
    )
    e_ac_out_eu = s_ac_out_eu.multiply(
        n_self_elec.snapshot_weightings.generators, axis=0
    ).sum()
    # Combined
    e_ac_in = pd.concat([e_ac_in, e_ac_in_eu[e_ac_in_eu.index == "EU27"]])
    e_ac_out = pd.concat([e_ac_out, e_ac_out_eu[e_ac_out_eu.index == "EU27"]])

    # Calculate the net electricity imported per country/cluster
    local_import_elec = (
        e_dc_in.add(-e_dc_out, fill_value=0)
        .add(e_ac_in, fill_value=0)
        .add(-e_ac_out, fill_value=0)
    )

    # Calculate total demand for electricity
    demand_elec = local_import_elec.add(generation_elec, fill_value=0)
    self_sufficiency_elec = generation_elec / demand_elec
    return demand_elec, self_sufficiency_elec


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
    main_dir = Path(os.getcwd()).parent  # Repository directory
    resultdir = (
        Path(main_dir) / full_name
    )  # folder where Excel files and graphs are stored
    if not os.path.exists(resultdir):
        os.makedirs(resultdir)

    self_sufficiency_dir = resultdir / "self-sufficiency"
    if not os.path.exists(self_sufficiency_dir):
        os.mkdir(self_sufficiency_dir)

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
    evaluate_self_sufficiency(
        networks_year,
        scenarios,
        scenario_colors,
        scenarios_for_comp,
        main_dir,
        self_sufficiency_dir,
        runs,
        years,
    )
