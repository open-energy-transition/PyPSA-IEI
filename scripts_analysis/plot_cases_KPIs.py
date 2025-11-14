import os
from datetime import datetime
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

from networks_regional_dictionary import boundary_network_plots



def plot_case_study_KPIs(networks, years, runs, main_dir, KPI_dir):
    """
    Plots barchart to compare offshore capacity, H2 storage and CO2
    storage for all scenarios over all years in specific clusters
    defined below.
    Adds a map of the clusters.

    Parameters
    ----------
    networks : dict
        dict with postnetworks data
    years : list
        list of considered years
    runs : dict
        dict of scenarios with associated folders
    main_dir : str or Path
        path of maindirectory
    KPI_dir : str or Path
        path of resultdirectory

    Results
    -------
    None
    """
    cluster_sea_north = {
        "northsea": {
            "BE1 0": "Belgium",
            "NL1 0": "E. Netherlands",
            "NL1 1": "W. Netherlands",
            "DE1 1": "N. Germany",
            "DE1 3": "N.W. Germany",
            "DK1 0": "Denmark",
        }
    }
    cluster_sea_balt = {
        "balticum": {
            "EE6 0": "Estonia",
            "LT6 0": "Lithuania",
            "LV6 0": "Latvia",
            "PL1 2": "N. Poland",
            "PL1 4": "N.W. Poland",
        }
    }
    cluster_land_north = {
        "northsea": {
            "BE1 0": "Belgium",
            "NL1 0": "E. Netherlands",
            "NL1 1": "W. Netherlands",
            "DE1 1": "N. Germany",
            "DE1 3": "N.W. Germany",
            "DK1 0": "Denmark",
            "LU1 0": "Luxemburg",
            "DE1 2": "W. Germany",
        }
    }
    cluster_land_balt = {
        "balticum": {
            "EE6 0": "Estonia",
            "LT6 0": "Lithuania",
            "LV6 0": "Latvia",
            "PL1 2": "N. Poland",
            "PL1 4": "N.W. Poland",
            "PL1 0": "E. Poland",
            "PL1 1": "S.W. Poland",
            "PL1 3": "S. Poland",
        }
    }

    # Offshore plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks, runs, years, cluster_sea_north, "offshore"
    )
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks, runs, years, cluster_sea_balt, "offshore"
    )

    # H2 plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks, runs, years, cluster_land_north, "H2"
    )
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks, runs, years, cluster_land_balt, "H2"
    )

    # CO2 plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks, runs, years, cluster_land_north, "CO2"
    )
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks, runs, years, cluster_land_balt, "CO2"
    )

    # H2 import plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir,
        KPI_dir,
        networks,
        runs,
        years,
        cluster_land_north,
        "H2_import",
    )




def plot_cluster_map(main_dir, ax, dict_cluster, colors, KPI):
    """
    Creates map for considered cluster.

    Parameters
    ----------
    main_dir : str or Path
        path of maindirectory
    ax : matplotlib.axes._subplots.AxesSubplot
        plot object
    dict_cluster : dict
        dict of clusternames ({name: [list cluster]})
    colors : list
        list of colors for clusters
    KPI : str
        string of KPI ('offshore', 'H2', 'CO2')

    Returns
    -------
    None
    """
    # Select region
    key = list(dict_cluster.keys())
    dict_region = dict_cluster[key[0]]

    # Get borders
    proj = ccrs.EqualEarth()
    # Path
    path_regions_sea = (
        main_dir
        / "scripts_analysis"
        / "shapes"
        / "regions_offshore_elec_s_62.geojson"
    )
    path_regions_land = (
        main_dir
        / "scripts_analysis"
        / "shapes"
        / "regions_onshore_elec_s_62.geojson"
    )
    path_countries = (
        main_dir / "scripts_analysis" / "shapes" / "country_shapes.geojson"
    )
    # Data
    shape_region_sea = (
        gpd.read_file(path_regions_sea)
        .set_index("name")
        .to_crs(proj.proj4_init)
    )
    shape_region_land = (
        gpd.read_file(path_regions_land)
        .set_index("name")
        .to_crs(proj.proj4_init)
    )
    shape_country = (
        gpd.read_file(path_countries).set_index("name").to_crs(proj.proj4_init)
    )

    # Reduce by region and boundaries
    cluster = list(dict_region.keys())
    index = shape_region_sea.index.isin(cluster)
    offshore = shape_region_sea[index].index.tolist()
    sequence = [s for s in cluster if s in offshore]
    shape_region_sea = shape_region_sea.loc[sequence]
    if key[0] == "northsea":
        boundaries = boundary_network_plots("Benelux")
    else:
        boundaries = boundary_network_plots("PL_and_Baltics")
    shape_region_land = shape_region_land.loc[cluster]

    # Plot begin
    if KPI == "offshore":
        shape_region_sea.plot(
            ax=ax,
            edgecolor="grey",
            facecolor="none",
            linewidth=0.2,
            color=colors,
        )
        shape_region_land.plot(
            ax=ax, edgecolor="grey", facecolor="none", linewidth=0.2
        )
    else:
        shape_region_sea.plot(
            ax=ax, edgecolor="grey", facecolor="none", linewidth=0.2
        )
        shape_region_land.plot(
            ax=ax,
            edgecolor="grey",
            facecolor="none",
            linewidth=0.2,
            color=colors,
        )
    shape_country.plot(
        ax=ax, edgecolor="black", facecolor="none", linewidth=0.5
    )
    ax.set_extent(boundaries, crs=ccrs.PlateCarree())


def plot_KPI_barchart_map(
    main_dir, resultdir, networks_year, runs, years, dict_cluster, KPI
):
    """
    Creates primary barchart of CO2 storage, H2 storage and offshore
    capacity to compare scenarios by years. Call plot_cluster_map for
    map next to barplot.

    Parameters
    ----------
    main_dir : str or Path
        path of maindirectory
    resultdir : str or Path
        path of resultdirectory
    networks_year : dict
        dict with postnetworks data
    runs : dict
        dict of scenarios with associated folders
    years : list
        list of considered years
    dict_cluster : dict
        dict of region and clusters ({region: [clusternames: cluster]}
    KPI : str
        string of KPI ('offshore', 'H2', 'CO2')

    Returns
    -------
    None
    """

    # Stylesheet for plot + colors
    plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
    # Calculate offshore power per scenario and year
    if KPI == "offshore":
        dict_data = calculate_offshore(networks_year, runs, years)
        scalar = 1e-3
    elif KPI == "H2_import":
        dict_data = calculate_H2_import(
            networks_year, runs, years, dict_cluster
        )
        scalar = 1e-6
    else:
        dict_data = calculate_H2_CO2(networks_year, runs, years, KPI)
        scalar = 1e-6
    ## Transform dict
    dict_data = {key: df * scalar for key, df in dict_data.items()}
    # Cluster
    cluster_key = list(dict_cluster.keys())
    cluster = list(dict_cluster[cluster_key[0]].keys())
    dict_data = {key: df.loc[cluster] for key, df in dict_data.items()}

    # Plot begin
    gs = gridspec.GridSpec(1, 2, width_ratios=[2, 1])
    fig = plt.figure(figsize=(6.3, 3.65))
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], projection=ccrs.EqualEarth())

    # Position of bars for dict_df[first_scenario] on x axis
    scenarios = dict_data.keys()
    scenarios_use = list(scenarios) * len(years)
    first_scenario, first_value = next(iter(dict_data.items()))
    r = {}
    x_ticks = []
    # Colors
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    ## Plot associated map
    plot_cluster_map(main_dir, ax2, dict_cluster, colors, KPI)

    ## Plot barchart
    barWidth = 0.8 / len(dict_data)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in dict_data.items():
        r[scenario] = [x + i * barWidth + 0.3 for x in r0]
        i = i + 1

    # Plot-routine
    for scenario in dict_data.keys():
        # Plot settings
        for j in range(0, len(r[scenario])):
            r[scenario][j] = np.round(r[scenario][j], 1)
        dict_data[scenario] = dict_data[scenario].rename(
            index=dict_cluster[cluster_key[0]]
        )
        keys = dict_data[scenario].index

        # Barplot for one scenario with bottoms
        diff = 0.0115
        bottoms = np.zeros(len(years))
        for i in range(0, len(keys)):
            arr = np.array(dict_data[scenario].loc[keys[i]])
            if i > 0:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        arr,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=colors[i],
                        label=keys[i],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        arr,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=colors[i],
                    )
                bottoms = np.add(bottoms, arr)
            else:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        arr,
                        width=barWidth - diff,
                        color=colors[i],
                        label=keys[i],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        arr,
                        width=barWidth - diff,
                        color=colors[i],
                    )
                bottoms = np.add(bottoms, arr)

        for j in range(0, len(r[scenario])):
            if r[scenario][j] not in x_ticks:
                x_ticks.append(r[scenario][j])

        # Plot settings
        if KPI == "offshore":
            ax1.set_ylabel(
                "Installed capacity (GW)"
            ) 
        elif KPI == "H2":
            ax1.set_ylabel("Total energy stored (TWh)")
        elif KPI == "CO2":
            ax1.set_ylabel("CO$_2$ sequestered per year (Mt/a)")
            ylim = ax1.get_ylim()
            ax1.set_ylim(ylim[0], ylim[1] * 1.05)
        elif KPI == "H2_import":
            ax1.set_ylabel("Non-European hydrogen import (TWh)")
            ylim = ax1.get_ylim()
            ax1.set_ylim(ylim[0], ylim[1] * 1.05)
        handles, labels = (
            ax1.get_legend_handles_labels()
        )
        ax1.legend(
            reversed(handles),
            reversed(labels),
            loc="lower center",
            bbox_to_anchor=(0.5, 1.1),
            frameon=False,
            ncol=2,
        )
    # Final settings
    x_lab = [
        r[scenario][i] - (len(dict_data) - 1) * (barWidth - diff) / 2
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
    secax.tick_params(labelsize=10)

    plt.tight_layout()
    if KPI == "offshore":
        plt.savefig(
            resultdir / f"{KPI}_capacity_{cluster_key[0]}.png"
        )
    elif KPI == "H2_import":
        plt.savefig(resultdir / f"{KPI}_{cluster_key[0]}.png")
    else:
        plt.savefig(resultdir / f"{KPI}_storage_{cluster_key[0]}.png")
    plt.close()




def calculate_offshore(networks_year, runs, years):
    """
    Calculates offshore capacity for every network cluster in MW. Data
    is calculated for every scenario and every year.

    Parameters
    ----------
    networks_year : dict
        dict with postnetworks data
    runs : dict
        dict of scenarios with associated folders
    years : list
        list of considered years

    Returns
    -------
    dict
        dict with dfs of offshore capacity for every scenario
    """
    dict_scen = dict()

    for scenario in runs.keys():
        df_offshore_scen = pd.DataFrame()

        for year in years:
            network_offshore = networks_year[year][scenario].copy()
            df = network_offshore.generators

            # Transform dataframe
            df_offshore_year = (
                df.query("carrier == 'offwind-ac' | carrier == 'offwind-dc'")
                .groupby("bus")["p_nom_opt"]
                .sum()
                .reset_index()
            )
            # Treat missing offshore entries
            if year == years[0]:
                df_offshore_scen[year] = df_offshore_year["p_nom_opt"]
                df_offshore_scen.index = df_offshore_year["bus"]
            else:
                df_col = df_offshore_year[["p_nom_opt"]].rename(
                    columns={"p_nom_opt": year}
                )
                df_col.index = df_offshore_year["bus"]
                df_offshore_scen = df_offshore_scen.join(df_col)
                df_offshore_scen = df_offshore_scen.fillna(0)

        dict_scen[scenario] = df_offshore_scen

    return dict_scen


def calculate_H2_CO2(networks_year, runs, years, KPI):
    """
    Calculates CO2 storage or H2 storage for every network cluster
    in MW. Data is calculated for every scenario and every year.

    Parameters
    ----------
    networks_year : dict
        dict with postnetworks data
    runs : dict
        dict of scenarios with associated folders
    years : list
        list of considered years
    KPI : str
        string of KPI (possible: 'H2', 'CO2')

    Returns
    -------
    dict
        dict with dfs of H2/CO2 storage for every scenario
    """
    dict_scen = dict()

    for scenario in runs.keys():
        df_scen = pd.DataFrame()

        for year in years:
            network_H2_CO2 = networks_year[year][scenario].copy()
            df = network_H2_CO2.stores_t.e

            # Transform KPI dataframe
            if KPI == "H2":
                df = df.filter(regex="H2 Store")
            else:
                df = df.filter(regex="co2 sequestered")
            new_colnames = [x[:5] for x in list(df.columns)]
            df = df.set_axis(new_colnames, axis=1)
            df = df.T
            df = df.groupby(df.index).sum()
            df = df.diff(axis=1).drop(df.columns[0], axis=1)
            df[df < 0] = 0
            df_scen[year] = df.sum(axis=1)

        dict_scen[scenario] = df_scen

    return dict_scen


def calculate_H2_import(networks_year, runs, years, dict_cluster):
    """
    Calculates Non-European H2 import for dict_cluster in MWh. Data is
    calculated for every scenario and every year.

    Parameters
    ----------
    networks_year : dict
        dict with postnetworks data
    runs : dict
        dict of scenarios with associated folders
    years : list
        list of considered years
    dict_cluster : dict
        dict of region and clusters ({region: [clusternames: cluster]}

    Returns
    -------
    dict
        dict with dfs of H2 import for every scenario
    """
    dict_scen = dict()

    for scenario in runs.keys():
        df_scen = pd.DataFrame()

        for year in years:
            network_H2_import = networks_year[year][scenario].copy()
            snapshot_weightings = (
                network_H2_import.snapshot_weightings.generators
            )
            idx = network_H2_import.generators[
                network_H2_import.generators.carrier.isin(
                    ["import shipping-H2"]
                )
            ].index
            df = network_H2_import.generators_t.p[idx].mul(
                snapshot_weightings, axis=0
            )

            # Transform dataframe in right shape
            new_colnames = [x[:5] for x in list(df.columns)]
            df = df.set_axis(new_colnames, axis=1)
            df = df.T
            # Aggregate data for unique buses (new + retrofitted)
            df = df.groupby(df.index).sum().sum(axis=1)

            # Fill missing index for cluster
            clustername = list(dict_cluster.keys())[0]
            cluster = list(dict_cluster[clustername].keys())
            df_all = pd.Series(0.0, index=cluster)
            df_all.update(df)

            df_scen[year] = df_all

        dict_scen[scenario] = df_scen

    return dict_scen


if __name__ == "__main__":
    # User configuration for input data
    cluster_sea_north = {
        "northsea": {
            "BE1 0": "Belgium",
            "NL1 0": "E. Netherlands",
            "NL1 1": "W. Netherlands",
            "DE1 1": "N. Germany",
            "DE1 3": "N.W. Germany",
            "DK1 0": "Denmark",
        }
    }
    cluster_sea_balt = {
        "balticum": {
            "EE6 0": "Estonia",
            "LT6 0": "Lithuania",
            "LV6 0": "Latvia",
            "PL1 2": "N. Poland",
            "PL1 4": "N.W. Poland",
        }
    }
    cluster_land_north = {
        "northsea": {
            "BE1 0": "Belgium",
            "NL1 0": "E. Netherlands",
            "NL1 1": "W. Netherlands",
            "DE1 1": "N. Germany",
            "DE1 3": "N.W. Germany",
            "DK1 0": "Denmark",
            "LU1 0": "Luxemburg",
            "DE1 2": "W. Germany",
        }
    }
    cluster_land_balt = {
        "balticum": {
            "EE6 0": "Estonia",
            "LT6 0": "Lithuania",
            "LV6 0": "Latvia",
            "PL1 2": "N. Poland",
            "PL1 4": "N.W. Poland",
            "PL1 0": "E. Poland",
            "PL1 1": "S.W. Poland",
            "PL1 3": "S. Poland",
        }
    }

    years = ["2030", "2035", "2040", "2045", "2050"]
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    # insert run names for scenarios here:
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

    KPI_dir = resultdir / "KPIs"
    if not os.path.exists(KPI_dir):
        os.mkdir(KPI_dir)
    scenarios = list(runs.keys())

    # load all network files from results folder into a nested dictionary
    networks_year = {}
    for year in years:  # years:
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

    # Possible: ['offshore', 'H2', 'CO2', 'H2_import]
    # Offshore plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir,
        KPI_dir,
        networks_year,
        runs,
        years,
        cluster_sea_north,
        "offshore",
    )
    plot_KPI_barchart_map(
        main_dir,
        KPI_dir,
        networks_year,
        runs,
        years,
        cluster_sea_balt,
        "offshore",
    )

    # H2 plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks_year, runs, years, cluster_land_north, "H2"
    )
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks_year, runs, years, cluster_land_balt, "H2"
    )

    # CO2 plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir,
        KPI_dir,
        networks_year,
        runs,
        years,
        cluster_land_north,
        "CO2",
    )
    plot_KPI_barchart_map(
        main_dir, KPI_dir, networks_year, runs, years, cluster_land_balt, "CO2"
    )

    # H2 import plot (barchart+map)
    plot_KPI_barchart_map(
        main_dir,
        KPI_dir,
        networks_year,
        runs,
        years,
        cluster_land_north,
        "H2_import",
    )
