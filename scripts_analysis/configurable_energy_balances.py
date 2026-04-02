import copy
import itertools
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import pypsa
from matplotlib import pyplot as plt

from common import log
from energy_balance_dictionaries import get_components_for_carrier
from energy_balance_functions import (
    calculate_crossborder_transmission_losses,
    calculate_internal_transmission_losses,
    get_relevant_cross_border_losses,
    get_values_for_balance,
)

"""Script to generate configurable energy balances for different carriers"""

"""Careful: aggregates the balance of individual buses 
- take care of interpretation in case of carriers with imports and 
  especially in case of transmission losses
- Special case is implemented for AC/electricity balance.
"""

## Variables needed everywhere

countries = [
    "AL",
    "AT",
    "BA",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "ME",
    "MK",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "RS",
    "SE",
    "SI",
    "SK",
]

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

th_countries = [
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
    "GB",
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
]  # TransHyDE countries

# Updated first 19 colors (from stylesheet)
plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
style_colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
COLORS = style_colors + [
    "#808080",
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#000000",
    "#e6194b",
    "#3cb44b",
    "#ffe119",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
    "#fabebe",
]

COLUMNS_TO_IGNORE = {
    "electricity": [
        "AC transmission losses",
        "DC transmission losses",
        "Gas pipeline",
        "grid losses",
        "H2 pipeline",
    ],  #'AC', 'DC',
    "low voltage": [],
    "H2": [],
    "heat": [],
    "urban central heat": [],
    "gas": [],
}


def get_standard_balances(
    networks,
    carrier_for_balance,
    years,
    scenarios,
    balance_resultdir,
    country_to_plot,
    compare_scenarios,
    en_balance_cache=None,
):
    """
    The function creates 3 different types of balance plots with
    supply and demand for a specific carrier (e.g. 'electricity',
    'low voltage', 'H2', 'heat', 'urban central heat') and a specific
    region. Firstly the data is calculated by get_energy_balance_df.
    Thereafter the plots are created and saved by
    calling create_and_save_balance():
        - Folder bar_plots: barplot for each scenario over all years
        - Folder timeseries_plots_line_chart: html linechart with
          timeseries for one scenario and year (selectable)
        - Folder timeseries_plots_stacked_bar_chart: html barplot with
          timeseries for one scenario and year (selectable)
    Further the data is stored in Exel files with sheets
    for every country.

    Parameters
    ----------
    networks : dict
        dict with networks for scenarios per year
        ({year: {scen: network}})
    carrier_for_balance : str
        balance carrier ('electricity', 'low voltage', 'H2',
        'heat', 'urban central heat')
    years : list
        list of relevant years
    scenarios : list
        list of scenario names
    balance_resultdir : str or pathlib.Path
        path of result directory
    country_to_plot : str
        region for which the data is calculated/plotted
    compare_scenarios : list of bool
        list indicating if scenarios should be compared or not

    Returns
    -------
    None
    """
    log(f"Starting: get_standard_balances — {carrier_for_balance}")

    # Calculate data
    #   - df: index -> country/carrier/(Generation or Demand)
    #         columns -> scenario/year
    #   - hourly_data: dict {year: {scen: df with timestamps}}
    #   - cross_border_losses: dict {year: {scen: list with cross border
    #                          losses ((country1, country2), loss)
    #   - extra_comps: list with additional losses
    df, hourly_data, cross_border_losses, extra_comps = get_energy_balance_df(
        networks,
        years,
        scenarios,
        carrier_for_balance,
        geo_resolution="national",
        en_balance_cache=en_balance_cache,
    )

    # Create barplots + exelsheet for 'All'
    create_and_save_balance(
        networks,
        countries,
        "All",
        balance_resultdir,
        carrier_for_balance,
        df,
        hourly_data,
        cross_border_losses,
        extra_comps,
        country_to_plot,
        compare_scenarios,
    )

    # Create barplots + exelsheet for 'EU27'
    create_and_save_balance(
        networks,
        eu27_countries,
        "EU27",
        balance_resultdir,
        carrier_for_balance,
        df,
        hourly_data,
        cross_border_losses,
        extra_comps,
        country_to_plot,
        compare_scenarios,
    )

    # Create barplots for country_to_plot + exelsheet for every country
    for country in countries:
        create_and_save_balance(
            networks,
            [country],
            country,
            balance_resultdir,
            carrier_for_balance,
            df,
            hourly_data,
            cross_border_losses,
            extra_comps,
            country_to_plot,
            compare_scenarios,
        )

    log(f"Done: get_standard_balances — {carrier_for_balance}")


def create_and_save_balance(
    all_networks,
    list_loc,
    my_name,
    balance_resultdir,
    carrier_name,
    df,
    hourly_data,
    cross_border_losses,
    extra_comps,
    country_to_plot: str,
    compare_scenarios,
):
    """
    Calls functions for barplots (png + html) and linechart and
    saves excel sheets.

    Parameters
    ----------
    all_networks : dict
        dict containing all original networks
        {year: {scenario: pypsa.Network}}
    list_loc : list of str
        list with country abbreviations that will be summarized
        for calculation/Excel sheet
    my_name : str
        name of the region
    balance_resultdir : str or pathlib.Path
        path of result directory
    carrier_name : str
        balance carrier ('electricity', 'low voltage', 'H2',
        'heat', 'urban central heat')
    df : pd.DataFrame
        DataFrame with generation/demand data
        (see get_standard_balances)
    hourly_data : dict
        dict with timestamps per scenario and year
        {year: {scenario: df with timestamps}}
    cross_border_losses : dict
        dict with cross-border losses {year: {scenario: list with
        cross-border losses ((country1, country2), loss)}}
    extra_comps : list
        list with additional losses
    country_to_plot : str
        region for which the plots are generated
    compare_scenarios : list of bool
        list indicating if scenarios should be compared or not

    Returns
    -------
    None
    """
    # Aggregate data from df for region (list_loc)
    country_df = create_local_balance_df(
        df,
        list_loc,
        extra_comps,
        cross_border_losses,
        add_sums=True,
        str_name=my_name,
    )

    # Save excel sheet for my_name
    filename = f"{balance_resultdir}/balance_{carrier_name}.xlsx"
    if not os.path.exists(filename):
        country_df.to_excel(filename, sheet_name=my_name, index=True)
    else:
        with pd.ExcelWriter(
            filename, mode="a", engine="openpyxl", if_sheet_exists="replace"
        ) as writer:
            country_df.to_excel(writer, sheet_name=my_name, index=True)

    # Save gas_turbine_backup.xlsx (if for uniqueness)
    if carrier_name == "electricity":
        estimate_backup_capacities(
            hourly_data, balance_resultdir, all_networks, my_name, list_loc
        )

    # Plot balance charts for 'EU27' or country_to_plot (if given)
    if my_name in ["All", "EU27", country_to_plot]:

        # Plots stored in folder bar_plots
        for comp in compare_scenarios:
            plot_local_balance_df(
                country_df, my_name, carrier_name, balance_resultdir, comp
            )

        # Calculate hourly data
        country_hourly_dfs = create_local_balance_df_hourly(
            hourly_data, list_loc, add_sums=False, str_name=my_name
        )
        #
        # Plots stored in folder timeseries_plots_line_chart
        plot_time_series_html(
            country_hourly_dfs[my_name],
            my_name,
            carrier_name,
            balance_resultdir,
        )
        # Plots stored in folder timeseries_plots_stacked_bar_chart
        plot_time_series_html(
            country_hourly_dfs[my_name],
            my_name,
            carrier_name,
            balance_resultdir,
            "bar",
        )
        plot_time_series_png(
            country_hourly_dfs[my_name],
            my_name,
            carrier_name,
            balance_resultdir,
        )

        plt.close("all")


def plot_local_balance_df(
    local_balance_df: pd.DataFrame,
    loc_str_write: str,
    carrier_name: str,
    result_path: str,
    compare_scenarios: bool,
):
    """
    Creates balance barplot with supply and demand for a specific
    carrier (e.g. 'electricity', 'low voltage', 'H2', 'heat',
    'urban central heat'), a specific region and one scenario or all
    scenarios in one plot over all years (dependent on
    compare_scenarios).

    Parameters
    ----------
    local_balance_df : pd.DataFrame
        Multi-index DataFrame containing balances of the region
    loc_str_write : str
        Region name to be plotted
    carrier_name : str
        Carrier name ('electricity', 'low voltage', 'H2', 'heat',
        'urban central heat')
    result_path : str
        Path of the result directory where plots will be saved
    compare_scenarios : bool
        whether to plot all scenarios in one figure (True)
        or a single scenario per figure (False)

    Returns
    -------
    None
    """
    ## 2020: Load statistical data for electricity
    # Dummy variable
    stat_data_label = ""

    is_using_statistical_data = (loc_str_write == "EU27") and (
        carrier_name == "electricity"
    )
    if is_using_statistical_data:
        # x-Label for plot
        if compare_scenarios:
            stat_data_label = "2020"
        else:
            stat_data_label = "2020\nStatistical Data"

        # Calculate df with 2020 data
        # Load data
        energy_supply = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "electricity_balances_2020.xlsx",
        )
        energy_data_2020 = pd.read_excel(energy_supply, sheet_name="EU27")
        # Calculate supply & demand
        cumulative_demand = energy_data_2020["electricity supply"].sum()
        elec_data = energy_data_2020["electricity supply"].tolist() + [
            -cumulative_demand
        ]
        elec_data = [value / 1000 for value in elec_data]  # TWh
        # Create multiindex (carrier/Generation)
        carrier = energy_data_2020["carrier"].tolist() + ["Cumulative Demand"]
        type = ["Generation"] * len(carrier)
        multi_index = pd.MultiIndex.from_arrays([carrier, type])
        # Create df
        historic_data_2020 = pd.DataFrame(
            {stat_data_label: elec_data}, index=multi_index
        )

    ## Transform local balance data
    # Get data of location
    df_balance = local_balance_df.loc[loc_str_write]

    # Calculate threshold over all scenarios
    df_balance = df_balance[
        df_balance.index.get_level_values(0) != "Sum"
    ]  # Drop Sum if contained
    maximum = df_balance.where(df_balance > 0).sum().max()
    threshold = maximum * 0.025

    # Filter data
    energy_sources_filtered = [
        x
        for x in list(df_balance.index.get_level_values(0))
        if x not in COLUMNS_TO_IGNORE[carrier_name]
    ]
    df_balance = df_balance.loc[energy_sources_filtered]

    # Summarize AC & DC
    if carrier_name == "electricity":
        net_acdc = (
            df_balance.loc["DC"].values[0] + df_balance.loc["AC"].values[0]
        )
        df_balance.rename(index={"AC": "Import/Export"}, inplace=True)
        df_balance.loc["Import/Export"] = net_acdc
        df_balance = df_balance.drop("DC")

    ## Aggregate data to 'Other supply' & 'Other demand' + get labels
    ## for footnote
    # Get indizes below threshold (for legend; without 'Other supply' +
    # 'Other demand')
    used_row_indices_below = df_balance.index[
        (df_balance.abs() < threshold).all(axis=1)
    ]
    indices_below_threshold = [
        df_balance.index.get_loc(value) for value in used_row_indices_below
    ]

    # Initialize 'Other supply' & 'Other demand' data (below threshold)
    data = {y: 0 for y in df_balance.columns}
    my_row_supply = pd.DataFrame(
        data, index=pd.MultiIndex.from_tuples([("Other supply", "Generation")])
    )
    my_row_demand = pd.DataFrame(
        data, index=pd.MultiIndex.from_tuples([("Other demand", "Demand")])
    )
    df_balance = pd.concat([df_balance, my_row_supply, my_row_demand], axis=0)
    df_balance.fillna(0, inplace=True)  # important (e.g. nuclear)

    # Initialize labels + arrays
    labels = list(df_balance.index)
    labels_below_sup = []
    labels_below_dem = []
    for idx_below in indices_below_threshold:
        col_len = len(df_balance.columns)
        arr_temp_pos = np.zeros(col_len)
        arr_temp_neg = np.zeros(col_len)
        values = df_balance.iloc[idx_below].values
        # Assign values to supply or demand
        for j in range(0, col_len):
            if values[j] >= 0:
                arr_temp_pos[j] = values[j]
            else:
                arr_temp_neg[j] = values[j]
        # Split labels into supply and demand
        # (special handling for 'Import' & 'Export' (split if necessary))
        if (all(t >= 0 for t in arr_temp_pos)) and (
            all(u == 0 for u in arr_temp_neg)
        ):
            if labels[idx_below][0] == "Import/Export":
                labels_below_sup.append("Import")
            else:
                labels_below_sup.append(labels[idx_below][0])
        elif (all(k <= 0 for k in arr_temp_neg)) and (
            all(m == 0 for m in arr_temp_pos)
        ):
            if labels[idx_below][0] == "Import/Export":
                labels_below_dem.append("Export")
            else:
                labels_below_dem.append(labels[idx_below][0])
        else:
            if labels[idx_below][0] == "Import/Export":
                labels_below_sup.append("Import")
                labels_below_dem.append("Export")
            else:
                labels_below_sup.append(labels[idx_below][0])
                labels_below_dem.append(labels[idx_below][0])
        # Aggregate data
        df_balance.loc[("Other supply", "Generation")] += arr_temp_pos
        df_balance.loc[("Other demand", "Demand")] += arr_temp_neg

    # Reduce df if data over threshold (important for legend)
    if all(u == 0 for u in df_balance.loc["Other supply"].values[0]) == True:
        indices_below_threshold.append(
            labels.index(("Other supply", "Generation"))
        )
        indices_below_threshold.sort()
    if all(u == 0 for u in df_balance.loc["Other demand"].values[0]) == True:
        indices_below_threshold.append(
            labels.index(("Other demand", "Demand"))
        )
        indices_below_threshold.sort()

    # Set labels that are shown in footnote + reduce df by this rows
    labels = [
        labels[indices_below_threshold[j]]
        for j in range(0, len(indices_below_threshold))
    ]
    df_balance = df_balance.drop(labels)

    # Extract scenarios
    for level in local_balance_df.columns.levels:
        if level.name == "Scenario":
            scenarios = level.values

    ## Plot settings
    # For all scenarios
    plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
    fig, ax = plt.subplots(figsize=(6.2, 5.1))
    if carrier_name == "H2":
        carrier_string = "Hydrogen"
        footnote = "$^{3}$"
    else:
        carrier_string = carrier_name.capitalize()
        footnote = ""
    plt.ylabel(f"{carrier_string} demand{footnote} & supply (PWh/yr.)")
    # Width + space for all_scenarios (updated later for one scenario)
    bar_width = 0.7
    scenario_seperation_whitespace = 0.01
    bar_width_single_scenario = bar_width / len(scenarios)
    x_ticks_per_scenario = {}

    # Create plot/subplot for every scenario
    for pos_scenario, scenario in enumerate(scenarios):

        # Get data for scenario + merge statistical data (column)
        df = df_balance[scenario]
        if is_using_statistical_data:
            df = historic_data_2020.merge(
                df, how="outer", left_index=True, right_index=True
            ).fillna(0)

        # Further plot settings
        bar_colors = COLORS.copy()
        index = (
            np.arange(len(df.columns))
            + (0.5 + pos_scenario - (len(scenarios) * 0.5))
            * bar_width_single_scenario
        )
        x_ticks_per_scenario[scenario] = index
        bottom_values_pos = len(index) * [0]
        bottom_values_neg = len(index) * [0]

        # Plot settings for one scenario
        if not compare_scenarios:
            plt.close("all")
            plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
            fig, ax = plt.subplots(figsize=(6.2, 5.1))
            plt.ylabel(f"{carrier_string} demand{footnote} & supply (PWh/yr.)")
            # Reset choices made to aggregate all scenarios in one plot
            index = np.arange(len(df.columns))
            scenario_seperation_whitespace = 0
            bar_width_single_scenario = bar_width

        plt.xticks(np.arange(len(df.columns)), df.columns)  # years for x-axis

        ## Assign color + plot bar
        # Arrays for the colors and the order in which they were plotted of
        # the elements of the barchart, separately for
        # those with values larger zero and those with values smaller zero.
        order_pos = []
        order_neg = []
        colors_pos = []
        colors_neg = []
        lab = []
        counter = 0

        # Subbar for every remaining index in df
        for row_index in df.index:
            # Get color
            color = bar_colors.pop(0)

            # Further plot settings
            y_values = df.loc[row_index].values.tolist()
            positive_values = [y if y > 0 else 0 for y in y_values]
            negative_values = [y if y < 0 else 0 for y in y_values]
            plt.ylim(-maximum * 1.05, maximum * 1.05)
            width = bar_width_single_scenario - scenario_seperation_whitespace
            start = 0

            # Exception for historic 2020 data when all scenarios
            # are plotted (first bar)
            if stat_data_label in df.columns and compare_scenarios:
                start = 1
                plt.bar(
                    index[:start],
                    positive_values[:start],
                    width=bar_width_single_scenario,
                    bottom=bottom_values_pos[:start],
                    label=row_index[0],
                    color=color,
                )
                plt.bar(
                    index[:start],
                    negative_values[:start],
                    width=bar_width_single_scenario,
                    bottom=bottom_values_neg[:start],
                    label=row_index[0],
                    color=color,
                )
            # Barplot
            plt.bar(
                index[start:],
                positive_values[start:],
                width=width,
                bottom=bottom_values_pos[start:],
                label=row_index[0],
                color=color,
            )
            plt.bar(
                index[start:],
                negative_values[start:],
                width=width,
                bottom=bottom_values_neg[start:],
                label=row_index[0],
                color=color,
            )

            # Add values to bottom
            bottom_values_pos = [
                y1 + y2 for y1, y2 in zip(bottom_values_pos, positive_values)
            ]
            bottom_values_neg = [
                y1 + y2 for y1, y2 in zip(bottom_values_neg, negative_values)
            ]

            # Assign order for positive and negative values and color
            if (negative_values == np.zeros(len(negative_values))).all():
                order_pos.append(counter)
                colors_pos.append(color)
            elif (positive_values == np.zeros(len(positive_values))).all():
                order_neg.append(counter)
                colors_neg.append(color)
            else:
                if len(negative_values) > 0:
                    if negative_values[-1] == 0:
                        order_pos.append(counter)
                        colors_pos.append(color)
                    else:
                        order_neg.append(counter)
                        colors_neg.append(color)
                else:
                    order_pos.append(counter)
                    colors_pos.append(color)
            lab.append(row_index[0])
            counter += 1

        ## Legend
        # Get handels + labels in the right order
        order = np.zeros(len(order_pos) + len(order_neg))
        colors_all = []
        for i in range(0, len(order_pos)):
            order[i] = order_pos[len(order_pos) - i - 1]
            colors_all.append(colors_pos[len(order_pos) - i - 1])
        for j in range(0, len(order_neg)):
            order[j + len(order_pos)] = order_neg[j]
            colors_all.append(colors_neg[j])
        plt.axhline(y=0, color="black", linestyle="-")
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        order = np.array(order, dtype=int)
        handles_use = list(by_label.values())

        # Update string for supply & demand
        if ("Other supply" in np.array(lab)) and (len(labels_below_sup) > 0):
            lab[np.where(np.array(lab) == "Other supply")[0][0]] = (
                "Other supply$^{1}$"
            )
        if ("Other demand" in np.array(lab)) and (len(labels_below_dem) > 0):
            if "Other supply$^{1}$" in np.array(lab):
                lab[np.where(np.array(lab) == "Other demand")[0][0]] = (
                    "Other demand$^{2}$"
                )
            else:
                lab[np.where(np.array(lab) == "Other demand")[0][0]] = (
                    "Other demand$^{1}$"
                )

        plt.legend(
            [handles_use[idx] for idx in order],
            [lab[idx2] for idx2 in order],
            loc="center left",
            bbox_to_anchor=(1, 0.5),
        )

        ## Saving plot
        # For one scenario
        if not compare_scenarios:

            # Change y-ticks
            ticks = plt.yticks()[0]  # Current y-ticks
            plt.yticks(
                ticks, [tick / 1000 for tick in ticks]
            )  # Set y-ticks in PWh
            plt.tick_params(axis="both", labelsize=7)  # Labelsize for x & y

            # Footnote
            add_text_box(
                labels_below_sup=labels_below_sup,
                labels_below_dem=labels_below_dem,
                carrier=carrier_name,
                lab=lab,
            )

            timeseries_result_path = (
                result_path / "bar_plots"
            )  # folder where Excel files and graphs are stored
            if not os.path.exists(timeseries_result_path):
                os.makedirs(timeseries_result_path)
            fig.savefig(
                f"{timeseries_result_path}/plot_"
                f"{scenario}_{loc_str_write}_{carrier_name}.png",
                bbox_inches="tight",
            )
            plt.close()

    # For all scenarios
    if compare_scenarios:

        # Add second x-axis
        ax.xaxis.set_ticks_position("top")
        sec_ax = ax.secondary_xaxis("bottom")
        scenario_labels = list(scenarios) * len(df.columns)
        scenario_ticks = [
            item
            for tuple_ in zip(*x_ticks_per_scenario.values())
            for item in tuple_
        ]
        # Special handling for historic data (2020)
        if is_using_statistical_data:
            scenario_labels = ["Statistical\ndata"] + scenario_labels[
                len(scenarios) :
            ]
            scenario_ticks = [
                sum(scenario_ticks[: len(scenarios)]) / len(scenarios)
            ] + scenario_ticks[len(scenarios) :]
            sec_ax.set_xticks(
                scenario_ticks,
                scenario_labels,
                rotation=90,
                fontproperties={"weight": "normal", "style": "normal"},
                fontsize=7,
            )
            sec_ax.get_xticklabels()[0].set_rotation(0)
        else:
            sec_ax.set_xticks(
                scenario_ticks,
                scenario_labels,
                rotation=90,
                fontproperties={"weight": "normal", "style": "normal"},
                fontsize=7,
            )

        # Change y-ticks
        ticks = plt.yticks()[0]  # Current y-ticks
        plt.yticks(
            ticks, [tick / 1000 for tick in ticks]
        )  # Set y-ticks in PWh
        plt.tick_params(axis="both", labelsize=7)  # Labelsize for x & y

        # Footnote
        add_text_box(
            labels_below_sup=labels_below_sup,
            labels_below_dem=labels_below_dem,
            carrier=carrier_name,
            lab=lab,
        )

        timeseries_result_path = (
            result_path / "bar_plots"
        )  # folder where Excel files and graphs are stored
        if not os.path.exists(timeseries_result_path):
            os.makedirs(timeseries_result_path)
        fig.savefig(
            f"{timeseries_result_path}/plot_all_scenarios_"
            f"{loc_str_write}_{carrier_name}.png",
            bbox_inches="tight",
        )
        plt.close()


def plot_time_series_html(
    dict_dfs: Dict[str, Dict[str, pd.DataFrame]],
    str_name: str,
    carrier_name: str,
    result_path: str,
    plot_type: str = "scatter",
):
    """
    Creates html balance line chart or barplot with supply and demand
    for a specific carrier (e.g. 'electricity', 'low voltage', 'H2',
    'heat', 'urban central heat') and a specific region. In the browser
    there is the option to plot the timeseries of one year for
    one specific scenario (scenario - year).

    Parameters
    ----------
    dict_dfs : Dict[str, Dict[str, pd.DataFrame]]
        Nested dictionary with timestamped data
        {year: {scenario: pd.DataFrame}}
    str_name : str
        Region name to plot
    carrier_name : str
        Carrier name ('electricity', 'low voltage', 'H2', 'heat',
        'urban central heat')
    result_path : str
        directory path where the HTML plots will be saved
    plot_type : str, optional
        type of plot:, by default "scatter"

    Returns
    -------
    None
    """
    # Get data for every year and scenario
    df_list = []
    for year in dict_dfs:
        for scenario in dict_dfs[year]:
            df_temp = (
                dict_dfs[year][scenario]
                .loc[str_name]
                .reset_index(level=1, drop=True)
                .transpose()
            )
            energy_sources = list(df_temp.columns)
            energy_sources_filtered = [
                x
                for x in energy_sources
                if x not in COLUMNS_TO_IGNORE[carrier_name]
            ]
            df_temp["year"] = year
            df_temp["scenario"] = scenario
            df_list.append(df_temp)
    df_all = pd.concat(df_list)

    ## Initialize figure
    pio.renderers.default = "browser"
    fig = go.Figure()

    # Extract years + scenarios
    years = list(dict_dfs.keys())
    scenarios = list(dict_dfs[years[0]].keys())

    # Initialize variables for plot setting
    dropdown_buttons = [s + " " + y for s in scenarios for y in years]
    # Visibility for which part of the data
    # the plot is shown (selection in dropdown)
    visibility_mapping = {}
    visible = True
    visibility_list_true = [True] * len(energy_sources_filtered)
    visibility_list_false = [False] * len(energy_sources_filtered)

    # Create plot
    dropdown_number = 0
    for year in years:
        for scenario in scenarios:
            if scenario != scenarios[0] or year != years[0]:
                visible = False

            # Fill missing hours (predecessor) + data for x-axis
            df = df_all[(df_all.year == year) & (df_all.scenario == scenario)]
            df.loc[:, "timestamp"] = pd.to_datetime(df.index)
            df.set_index("timestamp", inplace=True)
            df = df.resample("h").ffill()
            df2 = df.index
            df2 = df2.map(lambda t: t.replace(year=int(year)))

            for idx, col in enumerate(energy_sources_filtered):
                # Line chart
                if plot_type == "scatter":
                    fig.add_trace(
                        go.Scatter(
                            x=df2,
                            y=df[col],
                            name=col,
                            visible=visible,
                            line=dict(color=COLORS[idx]),
                        )
                    )
                # Bar chart
                if plot_type == "bar":
                    fig.add_trace(
                        go.Bar(
                            x=df2,
                            y=df[col],
                            name=col,
                            visible=visible,
                            marker=dict(color=COLORS[idx]),
                        )
                    )

            # Update visibility mapping
            visibility_list = [
                visibility_list_false for y in years for s in scenarios
            ]
            visibility_list[dropdown_number] = visibility_list_true
            visibility_list_flattened = [x for y in visibility_list for x in y]
            visibility_mapping[f"{scenario} {year}"] = (
                visibility_list_flattened
            )
            dropdown_number += 1

    ## Update Layout
    # Button setting
    button_layer_1_height = 1.08
    buttons = [
        dict(
            label=x,
            method="restyle",
            args=[{"visible": visibility_mapping[x]}],
        )
        for x in dropdown_buttons
    ]

    # Plot appearance
    fig.update_layout(
        xaxis_title="year",
        yaxis_title="Energy demand & supply (TWh)",
        title=f"{str_name} {carrier_name} balances",
        title_x=0.5,
        updatemenus=[
            dict(
                active=0,
                buttons=buttons,
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.22,
                y=button_layer_1_height,
            ),
        ],
    )

    # Lettering for button
    fig.update_layout(
        annotations=[
            dict(
                text="Scenario year:",
                x=0,
                xref="paper",
                y=1.06,
                yref="paper",
                align="left",
                showarrow=False,
            ),
        ]
    )

    if plot_type == "bar":
        fig.update_layout(barmode="relative", bargap=0)

    # Dict for filename
    string_mapping = {"scatter": "line_chart", "bar": "stacked_bar_chart"}
    # Saving plot
    timeseries_result_path = (
        result_path / f"timeseries_plots_{string_mapping[plot_type]}"
    )  # folder where Excel files and graphs are stored
    if not os.path.exists(timeseries_result_path):
        os.makedirs(timeseries_result_path)
    fig.write_html(
        f"{timeseries_result_path}/{str_name}_{carrier_name}_balance_"
        f"timeseries_{string_mapping[plot_type]}.html"
    )


def plot_time_series_png(dict_dfs, str_name, carrier_name, result_path):
    """
    Creates stacked area chart (step="post") with supply and demand for
    a specific carrier and region showing the January timeseries.
    Uses raw time segments directly (no hourly resampling) via
    stackplot for fast rendering.

    Parameters
    ----------
    dict_dfs : dict
        Nested dictionary with timestamped data
        {year: {scenario: pd.DataFrame}}
    str_name : str
        Region name to plot
    carrier_name : str
        Carrier name ('electricity', 'low voltage', 'H2', 'heat',
        'urban central heat')
    result_path : str or pathlib.Path
        Directory path where the PNG plots will be saved

    Returns
    -------
    None
    """
    for year in dict_dfs.keys():
        for scenario in dict_dfs[year].keys():
            df_balance = dict_dfs[year][scenario].loc[str_name]
            maximum = df_balance.where(df_balance > 0).sum().max()
            threshold = maximum * 0.02

            # Filter data
            energy_sources_filtered = [
                x
                for x in list(df_balance.index.get_level_values(0))
                if x not in COLUMNS_TO_IGNORE[carrier_name]
            ]
            df_balance = df_balance.loc[energy_sources_filtered]

            # Summarize AC & DC
            if carrier_name == "electricity":
                net_acdc = (
                    df_balance.loc["DC"].values[0]
                    + df_balance.loc["AC"].values[0]
                )
                df_balance.rename(index={"AC": "Import/Export"}, inplace=True)
                df_balance.loc["Import/Export"] = net_acdc
                df_balance = df_balance.drop("DC")
            ## Aggregate data to 'Other supply' & 'Other demand'
            ## + get labels for footnote
            used_row_indices_below = df_balance.index[
                (df_balance.abs() < threshold).all(axis=1)
            ]
            indices_below_threshold = [
                df_balance.index.get_loc(value)
                for value in used_row_indices_below
            ]

            # Initialize 'Other supply' & 'Other demand' data (below threshold)
            data = {y: 0 for y in df_balance.columns}
            my_row_supply = pd.DataFrame(
                data,
                index=pd.MultiIndex.from_tuples(
                    [("Other supply", "Generation")]
                ),
            )
            my_row_demand = pd.DataFrame(
                data,
                index=pd.MultiIndex.from_tuples([("Other demand", "Demand")]),
            )
            df_balance = pd.concat(
                [df_balance, my_row_supply, my_row_demand], axis=0
            )
            df_balance.fillna(0, inplace=True)  # important (e.g. nuclear)

            # Initialize labels + arrays
            labels = list(df_balance.index)
            labels_below_sup = []
            labels_below_dem = []
            for idx_below in indices_below_threshold:
                col_len = len(df_balance.columns)
                arr_temp_pos = np.zeros(col_len)
                arr_temp_neg = np.zeros(col_len)
                values = df_balance.iloc[idx_below].values
                # Assign values to supply or demand
                for j in range(0, col_len):
                    if values[j] >= 0:
                        arr_temp_pos[j] = values[j]
                    else:
                        arr_temp_neg[j] = values[j]
                # Split labels into supply and demand (special handling
                # for 'Import' & 'Export' (split if necessary))
                if (all(t >= 0 for t in arr_temp_pos)) and (
                    all(u == 0 for u in arr_temp_neg)
                ):
                    if labels[idx_below][0] == "Import/Export":
                        labels_below_sup.append("Import")
                    else:
                        labels_below_sup.append(labels[idx_below][0])
                elif (all(k <= 0 for k in arr_temp_neg)) and (
                    all(m == 0 for m in arr_temp_pos)
                ):
                    if labels[idx_below][0] == "Import/Export":
                        labels_below_dem.append("Export")
                    else:
                        labels_below_dem.append(labels[idx_below][0])
                else:
                    if labels[idx_below][0] == "Import/Export":
                        labels_below_sup.append("Import")
                        labels_below_dem.append("Export")
                    else:
                        labels_below_sup.append(labels[idx_below][0])
                        labels_below_dem.append(labels[idx_below][0])
                # Aggregate data
                df_balance.loc[("Other supply", "Generation")] += arr_temp_pos
                df_balance.loc[("Other demand", "Demand")] += arr_temp_neg

            # Reduce df if data over threshold (important for legend)
            if (
                all(u == 0 for u in df_balance.loc["Other supply"].values[0])
                == True
            ):
                indices_below_threshold.append(
                    labels.index(("Other supply", "Generation"))
                )
                indices_below_threshold.sort()
            if (
                all(u == 0 for u in df_balance.loc["Other demand"].values[0])
                == True
            ):
                indices_below_threshold.append(
                    labels.index(("Other demand", "Demand"))
                )
                indices_below_threshold.sort()

            # Set labels shown in footnote + reduce df by these rows
            labels = [
                labels[indices_below_threshold[j]]
                for j in range(0, len(indices_below_threshold))
            ]
            df_balance = df_balance.drop(labels)

            # --- Filter to January using raw segments (no resample) ---
            # Keeps only the segment timestamps that fall in January.
            # step="post" in stackplot holds each value until the next
            # segment boundary, giving the same visual result as bars.
            jan_cols = df_balance.columns[
                pd.DatetimeIndex(df_balance.columns).month == 1
            ]
            df = df_balance[jan_cols].astype(float)
            x = pd.DatetimeIndex(df.columns)

            bar_colors = COLORS[: len(df.index)]
            lab = [idx[0] for idx in df.index]

            # Separate positive / negative parts for stacking
            pos_vals = df.clip(lower=0).values  # (n_components, n_timesteps)
            neg_vals = df.clip(upper=0).values

            # Determine legend order (same logic as original)
            order_pos = []
            order_neg = []
            for i, row_index in enumerate(df.index):
                y_vals = df.loc[row_index].values.astype(float)
                neg_v = np.where(y_vals < 0, y_vals, 0.0)
                pos_v = np.where(y_vals > 0, y_vals, 0.0)
                if (neg_v == 0).all():
                    order_pos.append(i)
                elif (pos_v == 0).all():
                    order_neg.append(i)
                else:
                    if neg_v[-1] == 0:
                        order_pos.append(i)
                    else:
                        order_neg.append(i)

            # Plot
            plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
            fig, ax = plt.subplots(figsize=(6.2, 5.1))
            ax.set_ylabel(carrier_name.capitalize() + " demand & supply (TWh)")

            # stackplot with step="post": each segment holds its value
            # until the next timestamp — visually identical to bars
            ax.stackplot(x, pos_vals, colors=bar_colors, labels=lab, step="post")
            ax.stackplot(x, neg_vals, colors=bar_colors, step="post")  # no labels (same colors)
            ax.axhline(y=0, color="black", linestyle="-")
            ax.set_ylim(-maximum * 1.1, maximum * 1.1)

            # Update "Other supply/demand" label strings
            if ("Other supply" in np.array(lab)) and len(labels_below_sup) > 0:
                lab[np.where(np.array(lab) == "Other supply")[0][0]] = (
                    "Other supply$^{1}$"
                )
            if ("Other demand" in np.array(lab)) and len(labels_below_dem) > 0:
                if "Other supply$^{1}$" in np.array(lab):
                    lab[np.where(np.array(lab) == "Other demand")[0][0]] = (
                        "Other demand$^{2}$"
                    )
                else:
                    lab[np.where(np.array(lab) == "Other demand")[0][0]] = (
                        "Other demand$^{1}$"
                    )

            # Legend in stacking order
            order = np.zeros(len(order_pos) + len(order_neg), dtype=int)
            for i in range(len(order_pos)):
                order[i] = order_pos[len(order_pos) - i - 1]
            for j in range(len(order_neg)):
                order[j + len(order_pos)] = order_neg[j]
            handles_all, _ = ax.get_legend_handles_labels()
            ax.legend(
                [handles_all[idx] for idx in order],
                [lab[idx2] for idx2 in order],
                loc="center left",
                bbox_to_anchor=(1, 0.5),
            )

            # x-axis: real date labels, tick every 3 days
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
            ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))
            ax.tick_params(axis="x", rotation=90, labelsize=7)
            ax.tick_params(axis="y", labelsize=7)

            # Footnote
            add_text_box(
                labels_below_sup=labels_below_sup,
                labels_below_dem=labels_below_dem,
                carrier=carrier_name,
                lab=lab,
            )

            timeseries_result_path = (
                result_path / "timeseries_plots_stacked_bar_chart"
            )  # folder where Excel files and graphs are stored
            if not os.path.exists(timeseries_result_path):
                os.makedirs(timeseries_result_path)
            fig.savefig(
                f"{timeseries_result_path}/plot_{scenario}_{str_name}_"
                f"{carrier_name}_{year}.png",
                bbox_inches="tight",
            )
            plt.close()


def add_sums_to_balance(curr_balance, loc_str):
    """
    Adding sums to the data frame with the local balance to
    additional rows.

    Parameters
    ----------
    curr_balance : pd.DataFrame
        DataFrame with balances of the location
    loc_str : str
        Name of the cluster or region

    Returns
    -------
    pd.DataFrame
        Updated DataFrame with additional sum rows
    """
    # Insert string for multiindex
    if loc_str == "All countries":
        index_tuple = ("Sum",)
        level_nb = 1
    else:
        index_tuple = (
            loc_str,
            "Sum",
        )
        level_nb = 2

    # Total generated
    generated = curr_balance.loc[
        curr_balance.index.get_level_values(level_nb) == ("Generation"), :
    ].sum()
    curr_balance = add_to_local_df(
        generated, index_tuple + ("Generation",), curr_balance
    )
    # Total imported
    imported = curr_balance.loc[
        curr_balance.index.get_level_values(level_nb) == ("Import"), :
    ].sum()
    curr_balance = add_to_local_df(
        imported, index_tuple + ("Import",), curr_balance
    )
    # Total demand
    demand = curr_balance.loc[
        curr_balance.index.get_level_values(level_nb) == ("Demand"), :
    ].sum()
    curr_balance = add_to_local_df(
        demand, index_tuple + ("Demand",), curr_balance
    )
    # Imported + generated
    curr_balance = add_to_local_df(
        generated + imported,
        index_tuple + ("Generation+Import",),
        curr_balance,
    )

    return curr_balance


def add_text_box(labels_below_sup, labels_below_dem, carrier, lab):
    """
    Inserts textbox for footnote with 'Other supply' and
    'Other demand'.

    Parameters
    ----------
    labels_below_sup : list of str
        Supply items below the threshold
    labels_below_dem : list of str
        Demand items below the threshold
    carrier : str
        Carrier name (e.g., 'electricity', 'H2', etc.)
    lab : list of str
        List of labels used for ordering in the plot

    Returns
    -------
    None
    """
    # Initial variables
    ax = plt.gca()
    info1 = ""
    info2 = ""
    props = dict(facecolor="none", edgecolor="none")

    # Split into supply & demand
    if len(labels_below_sup) > 0:
        sup_str = ", ".join(label for label in labels_below_sup)
    if len(labels_below_dem) > 0:
        dem_str = ", ".join(label for label in labels_below_dem)
    if ("Other supply$^{1}$" in np.array(lab)) and (len(labels_below_sup) > 0):
        info1 = "$^{1}$" + f" Other supply: {sup_str}"
    if ("Other demand$^{1}$" in np.array(lab)) and (len(labels_below_dem) > 0):
        info1 = "$^{1}$" + f" Other demand: {dem_str}"
    if ("Other demand$^{2}$" in np.array(lab)) and (len(labels_below_dem) > 0):
        info2 = "$^{2}$" + f" Other demand: {dem_str}"

    if carrier == "H2":
        h2_industry_footnote = (
            " \n$^{3}$ Excluding grey hydrogen demand for industrial "
            "processes, which is included as methane demand in the model."
        )
    else:
        h2_industry_footnote = ""
    # Add textbox to plot
    if (len(info2) > 0) and (len(info1) > 0):
        ax.text(
            -0.15,
            -0.175,
            f"{info1} \n{info2}{h2_industry_footnote}",
            transform=ax.transAxes,
            fontsize=7,
            verticalalignment="bottom",
            bbox=props,
        )
    elif (len(info2) == 0) and (len(info1) > 0):
        ax.text(
            -0.15,
            -0.175,
            f"{info1}{h2_industry_footnote}",
            transform=ax.transAxes,
            fontsize=7,
            verticalalignment="bottom",
            bbox=props,
        )

    plt.tight_layout()


def compute_energy_balance_cache(networks, years, scenarios):
    """
    Pre-compute and cache network.statistics.energy_balance() results
    for all (year, scenario) combinations. Call this once in
    analysis_main before the carrier loop and pass the result to
    get_standard_balances via the en_balance_cache parameter.

    Parameters
    ----------
    networks : dict
        {year: {scenario: pypsa.Network}}
    years : list of str
    scenarios : list of str

    Returns
    -------
    dict
        {year: {scenario: {"aggregated": DataFrame, "hourly": DataFrame}}}
    """
    log("Computing energy balance cache for all networks...")
    cache = {}
    for y in years:
        cache[y] = {}
        for s in scenarios:
            n = networks[y][s]
            log(f"  energy_balance: {y} / {s}")
            cache[y][s] = {
                "aggregated": n.statistics.energy_balance(
                    aggregate_bus=False
                ),
                "hourly": n.statistics.energy_balance(
                    aggregate_bus=False, aggregate_time=False
                ),
            }
    log("Energy balance cache complete.")
    return cache


def get_energy_balance_df(
    networks_year, years, scenarios, carrier_for_balance, geo_resolution,
    en_balance_cache=None,
):
    """
    Create a dataframe at georesolution (national, cluster) level with
    balance values carrier_for_balance.

    Parameters
    ----------
    networks_year : dict
        Dictionary with networks for scenarios per year
        ({year: {scenario: network}})
    years : list of str
        List of relevant years
    scenarios : list of str
        List of scenario names
    carrier_for_balance : str
        Carrier for which the balance is calculated ('electricity',
        'low voltage', 'H2', 'heat', 'urban central heat')
    geo_resolution : str
        Georesolution ('national' or 'cluster')

    Returns
    -------
    pd.DataFrame
        DataFrame with balances at the specified geo-resolution.
    dict
        Nested dictionary {year: {scenario: hourly DataFrame}}.
    dict
        Nested dictionary {year: {scenario: list of
        cross-border losses}}.
    list
        List of additional components considered in the
        balance calculation.
    """
    ## Define carriers + components + structure of output data
    # Component list to be considered for balance with assignment from
    # energy_balance_dictionaries.py
    component_type_dict, sub_component_typ_dict, extra_sub_comps = (
        get_components_for_carrier(carrier_for_balance)
    )
    extra_comps = []
    for sub_comp in extra_sub_comps:
        extra_comps.append(sub_component_typ_dict[sub_comp])
    components = component_type_dict.keys()

    # Retrieve cluster list from a network (use cache if available):
    n = networks_year[years[0]][scenarios[0]]
    if en_balance_cache is not None:
        en_balance = en_balance_cache[years[0]][scenarios[0]]["aggregated"]
    else:
        en_balance = n.statistics.energy_balance(aggregate_bus=False)
    temp_list = en_balance.index.get_level_values(3).str[:5].unique()
    clusters = [
        item
        for item in temp_list
        if not (item.startswith("EU") or item.startswith("co2"))
    ]

    # Define structure of output data frames with multiindex
    # For rows
    if geo_resolution == "national":
        row_index_names = ["Country", "Component", "Component_Type"]
        indices = [
            (c, comp, component_type_dict[comp])
            for c, comp in itertools.product(countries, components)
        ]
        df_index = pd.MultiIndex.from_tuples(indices, names=row_index_names)
    else:
        row_index_names = ["Cluster", "Component", "Component_Type"]
        indices = [
            (c, comp, component_type_dict[comp])
            for c, comp in itertools.product(clusters, components)
        ]
        df_index = pd.MultiIndex.from_tuples(indices, names=row_index_names)
    # For columns
    df_columns = pd.MultiIndex.from_product(
        [scenarios, years], names=["Scenario", "Year"]
    )
    df = pd.DataFrame(index=df_index, columns=df_columns)

    # Carrier for balance list dependent on carrier_for_balance:
    if carrier_for_balance == "electricity":
        carrier_for_balance_list = ["low voltage", "AC"]
    elif carrier_for_balance == "heat":
        carrier_for_balance_list = [
            "services urban decentral heat",
            "urban central heat",
            "residential rural heat",
            "residential urban decentral heat",
            "services rural heat",
        ]
    else:
        carrier_for_balance_list = [carrier_for_balance]

    # Initialize dict to be filled for return
    cross_border_losses = {}
    hourly_data = {}

    ## Calculate data
    # For each loaded network: fill the output data frames
    # with the desired values
    for y in years:
        scenarios = networks_year[y].keys()
        cross_border_losses_year = {}
        hourly_data[y] = {}

        for s in scenarios:
            # Get network and energy balance for carrier (use cache if available)
            n = networks_year[y][s]
            snapshots = n.snapshot_weightings.generators
            if en_balance_cache is not None:
                en_balance = en_balance_cache[y][s]["aggregated"]
                en_balance_hourly = en_balance_cache[y][s]["hourly"]
            else:
                en_balance = n.statistics.energy_balance(aggregate_bus=False)
                en_balance_hourly = n.statistics.energy_balance(
                    aggregate_bus=False, aggregate_time=False
                )
            hourly_columns = en_balance_hourly.columns
            df_hourly = pd.DataFrame(index=df_index, columns=hourly_columns)

            # Calculate data for every carrier in list
            for curr_carrier in carrier_for_balance_list:
                red_en_balance = en_balance.loc[
                    :,
                    en_balance.index.get_level_values(2).str.contains(
                        curr_carrier
                    ),
                ]
                red_en_balance_hourly = en_balance_hourly.loc[
                    en_balance_hourly.index.get_level_values(2).str.contains(
                        curr_carrier
                    )
                ]

                # Check: are all components considered?
                set1 = set(red_en_balance.index.get_level_values(1).unique())
                set2 = set(sub_component_typ_dict.keys())
                if not set1.issubset(set2):
                    print(
                        f"Not all sub-components of the energy balance seem "
                        f"to be included for {s} in {y}:"
                    )
                    print(set1 - set2)

                # Get values for each component and add to main data frame
                helper_to_check_completeness = copy.deepcopy(
                    sub_component_typ_dict
                )
                helper_to_check_completeness_hourly = copy.deepcopy(
                    sub_component_typ_dict
                )
                for comp in components:
                    # Retrieve all values that can be found
                    # in n.statistics energy balance
                    component_values, helper_to_check_completeness = (
                        get_values_for_balance(
                            red_en_balance,
                            comp,
                            sub_component_typ_dict,
                            geo_resolution,
                            y,
                            helper_to_check_completeness,
                            extra_sub_comps,
                            curr_carrier,
                        )
                    )
                    df = add_to_dataframe(
                        comp,
                        y,
                        s,
                        component_values,
                        df,
                        component_type_dict[comp],
                        df_columns,
                        row_index_names,
                    )
                    # Retrieve all values that can be found
                    # in n.statistics energy balance hourly
                    (
                        component_values_hourly,
                        helper_to_check_completeness_hourly,
                    ) = get_values_for_balance(
                        red_en_balance_hourly,
                        comp,
                        sub_component_typ_dict,
                        geo_resolution,
                        y,
                        helper_to_check_completeness_hourly,
                        extra_sub_comps,
                        curr_carrier,
                    )
                    df_hourly = add_to_dataframe_hourly(
                        comp,
                        component_values_hourly,
                        df_hourly,
                        component_type_dict[comp],
                        row_index_names,
                    )

                if geo_resolution == "national":
                    if curr_carrier == "AC":
                        # Calculate losses cross borders and store them
                        # in case of later aggregation
                        ac_dc_loss_list = (
                            calculate_crossborder_transmission_losses(
                                n, countries, geo_resolution
                            )
                        )
                        cross_border_losses_year.update({s: ac_dc_loss_list})
                        # Calculate losses from transmission links/lines
                        # within country but between clusters
                        ac_transmission_losses, dc_transmission_losses = (
                            calculate_internal_transmission_losses(
                                n, countries
                            )
                        )
                        helper_to_check_completeness.pop(extra_sub_comps[0])
                        helper_to_check_completeness.pop(extra_sub_comps[1])

                        # Correction: move transmission losses
                        # from "import" to "demand":
                        # Add transmission losses
                        if len(extra_comps) == 1:
                            comp = extra_comps[0]
                            input_losses = ac_transmission_losses.add(
                                dc_transmission_losses
                            )
                            df = add_to_dataframe(
                                comp,
                                y,
                                s,
                                input_losses,
                                df,
                                component_type_dict[comp],
                                df_columns,
                                row_index_names,
                            )
                        else:
                            for comp in extra_comps:
                                if "AC" in comp:
                                    df = add_to_dataframe(
                                        comp,
                                        y,
                                        s,
                                        ac_transmission_losses,
                                        df,
                                        component_type_dict[comp],
                                        df_columns,
                                        row_index_names,
                                    )
                                elif "DC" in comp:
                                    df = add_to_dataframe(
                                        comp,
                                        y,
                                        s,
                                        dc_transmission_losses,
                                        df,
                                        component_type_dict[comp],
                                        df_columns,
                                        row_index_names,
                                    )
                                else:  # else helper_to_check_completeness
                                    # is not going to be empty
                                    print(
                                        f"Warning: did not add {comp} to df."
                                    )
                        # Remove transmission losses from import
                        keys_with_value = [
                            key
                            for key, value in component_type_dict.items()
                            if value == "Import"
                        ]
                        if len(keys_with_value) == 1:
                            comp = keys_with_value[0]
                            df = add_to_dataframe(
                                comp,
                                y,
                                s,
                                -1 * input_losses,
                                df,
                                component_type_dict[comp],
                            )
                        else:
                            for comp in keys_with_value:
                                if "AC" in comp:
                                    df = add_to_dataframe(
                                        comp,
                                        y,
                                        s,
                                        -1 * ac_transmission_losses,
                                        df,
                                        component_type_dict[comp],
                                        df_columns,
                                        row_index_names,
                                    )
                                elif "DC" in comp:
                                    df = add_to_dataframe(
                                        comp,
                                        y,
                                        s,
                                        -1 * dc_transmission_losses,
                                        df,
                                        component_type_dict[comp],
                                        df_columns,
                                        row_index_names,
                                    )
                                else:  # else helper_to_check_completeness
                                    # is not going to be empty
                                    print(
                                        f"Warning: did not remove {comp} "
                                        f"from imports in df."
                                    )

                elif geo_resolution != "national":
                    if curr_carrier == "AC":
                        # Calculate losses cross borders and store them
                        # in case of later aggregation
                        ac_dc_loss_list = (
                            calculate_crossborder_transmission_losses(
                                n, clusters, geo_resolution
                            )
                        )
                        cross_border_losses_year.update({s: ac_dc_loss_list})

                if not (len(helper_to_check_completeness) == 0):
                    print(
                        f"Warning: Not all components have been checked "
                        f"({curr_carrier}):"
                    )
                    print(helper_to_check_completeness.keys())

                # Check the energy balance sum for current scenario
                # and year (should be close to 0):
                generated = df.loc[
                    df.index.get_level_values(2) == "Generation", (s, y)
                ].sum()
                imported = df.loc[
                    df.index.get_level_values(2) == "Import", (s, y)
                ].sum()
                demand = df.loc[
                    df.index.get_level_values(2) == "Demand", (s, y)
                ].sum()
                test_sum = (generated + imported + demand) * 1e-6
                print(
                    f"Test sum is {test_sum:.2f} TWh for {curr_carrier} "
                    f"in scenario {s} in {y}."
                )

            # Add data to dict
            df_hourly = df_hourly.mul(snapshots) * 1e-6
            hourly_data[y][s] = df_hourly
        cross_border_losses.update({y: cross_border_losses_year})

    return df * 1e-6, hourly_data, cross_border_losses, extra_comps


def estimate_backup_capacities(
    dict_hourly_dfs, result_dir, all_networks, my_name, list_loc
):
    """
    Calculates the capacity and costs that is needed to cover the
    maximum residual load with gas turbines.

    Parameters
    ----------
    dict_hourly_dfs : dict
        dict containing all timeseries {year: {scenario: pd.DataFrame}}
    result_dir : str or Path
        path of result directory
    all_networks : dict
        dict containing all orginal networks
        {year: {scenario: pypsa.Network}}
    my_name : str
        str of region
    list_loc : list of str
        list (str) with country abbreviations that will be summarized
        for calculation/excel sheet

    Returns
    -------
    None
    """
    # Get variables to loop over
    years = list(dict_hourly_dfs.keys())
    scenarios = list(dict_hourly_dfs[years[0]].keys())
    # Define carriers to be subtracted from load to get residual load
    carriers_renewables = [
        "Solar",
        "Solar Rooftop",
        "Onshore Wind",
        "Offshore Wind",
    ]
    carriers_exog_demand = [
        "Agriculture electricity",
        "Industry electricity",
        "Residential & services",
    ]
    # Initialize variables
    backup_capacities = {}
    costs_backup_capas = {}
    previous_year = 0

    # Perform calculation for each year and scenario
    for year in years:
        yearly_backup_capacities = {}
        yearly_backup_costs = {}
        for scenario in scenarios:

            # Extract costs and length of snapshots from current network
            this_network = all_networks[year][scenario]
            ocgt_links = this_network.links.query(
                f'index.str.contains("OCGT-{year}")'
            )
            if ocgt_links.empty:
                ocgt_costs = 0
            else:
                ocgt_costs = ocgt_links.capital_cost[0]
            snapshots = this_network.snapshot_weightings.generators

            # Calculate hourly load and renewable generation per country
            df_temp = dict_hourly_dfs[year][scenario]
            renewables = (
                df_temp[
                    df_temp.index.get_level_values(1).isin(carriers_renewables)
                    & df_temp.index.get_level_values(0).isin(list_loc)
                ]
                .groupby(level=0)
                .sum()
            )
            load = (
                df_temp[
                    df_temp.index.get_level_values(1).isin(
                        carriers_exog_demand
                    )
                    & df_temp.index.get_level_values(0).isin(list_loc)
                ]
                .groupby(level=0)
                .sum()
            )
            # Convert to power and get maximum residual load per country
            residual_load = (-load - renewables).div(snapshots) * 1e6
            max_residual_load = residual_load.max(axis=1).sum()
            if previous_year == 0:
                # In the first year, the maximum residual load has to be
                # covered with new gas turbines
                full_costs_backup = max_residual_load * ocgt_costs
            else:
                # For all following years, only backup capacities additional
                # to the previous year are added to the
                # previous costs.
                new_capas = (
                    max_residual_load
                    - backup_capacities[previous_year][scenario]
                )
                if new_capas < 0:
                    new_capas = 0
                full_costs_backup = (
                    costs_backup_capas[previous_year][scenario]
                    + new_capas * ocgt_costs
                )

            # Update DataFrames and dictionaries with new results
            yearly_backup_costs[scenario] = full_costs_backup
            yearly_backup_capacities[scenario] = max_residual_load
        backup_capacities.update({year: yearly_backup_capacities})
        costs_backup_capas.update(({year: yearly_backup_costs}))

        # Set current year to previous year for next loop
        previous_year = year

    # Export data to excel file.
    df_backup_capas = pd.DataFrame(backup_capacities)
    df_backup_costs = pd.DataFrame(costs_backup_capas)
    filename_capas = result_dir / "gas_turbine_backup_capacities.xlsx"
    filename_costs = result_dir / "gas_turbine_backup_costs.xlsx"
    if not os.path.exists(filename_capas):
        df_backup_capas.to_excel(filename_capas, my_name)
    else:
        with pd.ExcelWriter(
            filename_capas,
            mode="a",
            engine="openpyxl",
            if_sheet_exists="replace",
        ) as writer:
            df_backup_capas.to_excel(writer, my_name)

    if not os.path.exists(filename_costs):
        df_backup_costs.to_excel(filename_costs, my_name)
    else:
        with pd.ExcelWriter(
            filename_costs,
            mode="a",
            engine="openpyxl",
            if_sheet_exists="replace",
        ) as writer:
            df_backup_costs.to_excel(writer, my_name)


def create_local_balance_df(
    df,
    loc_str,
    extra_comps,
    cross_border_losses,
    add_sums=False,
    str_name=None,
):
    """
    Creating a balance for a specific cluster or country, or a set of
    countries/clusters.

    Parameters
    ----------
    df : pandas.DataFrame
        pd df with multiindex for every country
    loc_str : list of str
        list (str) with cluster of country abbreviations
    extra_comps : list of str
        list (str) with additional losses
    cross_border_losses : dict
        dict with cross border losses {year: {scen: list with
        cross border losses ((country1, country2), loss)
    add_sums : bool, optional
        boolean if compontent types are summed up, by default False
    str_name : str, optional
        str of cluster name, by default None

    Returns
    -------
    pandas.DataFrame
        pd df with balances
    """
    # Warning
    if type(loc_str) is not list:
        raise ValueError(
            f"Input to create_local_balance_df "
            f"loc_str={loc_str} is not a list."
        )

    # Differentiate one country vs. cluster
    if len(loc_str) == 1:
        loc_str_write = loc_str[0]
        local_balance_df = df[df.index.get_level_values(0) == loc_str_write]
    else:
        local_balance_df_temp = df[df.index.get_level_values(0).isin(loc_str)]
        if str_name is None:
            loc_str_write = ", ".join(loc_str)
        else:
            loc_str_write = str_name
        local_balance_df_temp = local_balance_df_temp.groupby(
            level=[1, 2]
        ).sum()
        local_balance_to_correct = pd.concat(
            [local_balance_df_temp], keys=[loc_str_write], names=["Level0"]
        )
        local_balance_df = get_relevant_cross_border_losses(
            cross_border_losses, local_balance_to_correct, loc_str, extra_comps
        )

    # Add sums for component types
    if add_sums:
        local_balance_df = add_sums_to_balance(local_balance_df, loc_str_write)

    return local_balance_df


def create_local_balance_df_hourly(
    df_dict, loc_str, add_sums=False, str_name=None
):
    """
    Creating a balance for a specific cluster or country, or a set of
    countries/clusters hourly.

    Parameters
    ----------
    df_dict : dict
        dict with hourly data {year: {scen: df with timestamps}}
    loc_str : list of str
        list (str) with cluster of country abbreviations
    add_sums : bool, optional
        boolean if compontent types are summed up, by default False
    str_name : str, optional
        str of cluster name, by default None

    Returns
    -------
    dict
        pd df with hourly balances
    """
    # Warning
    if type(loc_str) is not list:
        raise ValueError(
            f"Input to create_local_balance_df "
            f"loc_str={loc_str} is not a list."
        )

    # Calculate for every year and scenario
    country_dfs_hourly = dict()
    country_dfs_hourly[str_name] = {}
    for year in df_dict:
        country_dfs_hourly[str_name][year] = {}
        for scenario in df_dict[year]:
            df = df_dict[year][scenario]

            # Differentiate one country vs. cluster
            if len(loc_str) == 1:
                loc_str_write = loc_str[0]
                local_balance_df = df[
                    df.index.get_level_values(0) == loc_str_write
                ]
            else:
                local_balance_df_temp = df[
                    df.index.get_level_values(0).isin(loc_str)
                ]
                if str_name is None:
                    loc_str_write = ", ".join(loc_str)
                else:
                    loc_str_write = str_name
                local_balance_df_temp = local_balance_df_temp.groupby(
                    level=[1, 2]
                ).sum()
                local_balance_df = pd.concat(
                    [local_balance_df_temp],
                    keys=[loc_str_write],
                    names=["Level0"],
                )

            # Add sums for component types
            if add_sums:
                local_balance_df = add_sums_to_balance(
                    local_balance_df, loc_str_write
                )

            country_dfs_hourly[str_name][year][scenario] = local_balance_df

    return country_dfs_hourly


def add_to_local_df(val_series, new_row_idx, loc_df):
    """
    Write to the multi level indexed data frames in case of a local
    balance drawn from the main df.

    Parameters
    ----------
    val_series : pd.Series
        pd series with summed values per scenario and year
        ((scen, year), val)
    new_row_idx : tuple
        tuple with multiindex for new row (cluster, 'Sum',
        component type)
    loc_df : pd.DataFrame
        pd df with balances of loc_str

    Returns
    -------
    pd.DataFrame
        pd df with added row
    """
    temp_df = pd.DataFrame(val_series, columns=[new_row_idx]).transpose()
    new_row = pd.DataFrame(index=[new_row_idx], columns=loc_df.columns)
    loc_df = pd.concat([loc_df, new_row])
    loc_df.update(temp_df)
    return loc_df


def add_to_dataframe(
    string_name, y, s, input_series, out_df, type, df_columns, row_index_names
):
    """
    Write to the main multi level indexed data frames.

    Parameters
    ----------
    string_name : str
        str of component
    y : str
        str of year
    s : str
        str of scenario name
    input_series : pd.Series
        pd.series with component values
    out_df : pd.DataFrame
        pd df with multiindex
    type : str
        str of component type
    df_columns : pd.MultiIndex
        pd multiindex column
    row_index_names : list of str
        list (str) with index names for rows (['Country', 'Component',
        'Component_Type'])

    Returns
    -------
    pd.DataFrame
        updated pd df
    """
    temp_df = pd.DataFrame(index=input_series.index, columns=df_columns)
    temp_df.loc[:, (s, y)] = input_series
    temp_df = temp_df.set_index(
        [
            temp_df.index,
            pd.Index([string_name] * len(temp_df)),
            pd.Index([type] * len(temp_df)),
        ]
    )
    temp_df = temp_df.rename_axis(row_index_names)
    out_df = out_df.add(temp_df, fill_value=0).fillna(out_df).fillna(temp_df)
    return out_df


def add_to_dataframe_hourly(
    string_name, input_df, out_df, type, row_index_names
):
    """
    Write to the main multi level indexed data frames hourly.

    Parameters
    ----------
    string_name : str
        str of component
    input_df : pd.DataFrame
        pd df with timestamps
    out_df : pd.DataFrame
        pd df with timestamps + index
    type : str
        str of component type
    row_index_names : list of str
        list (str) with index names for rows (['Country', 'Component',
        'Component_Type'])

    Returns
    -------
    pd.DataFrame
        updated pd df
    """
    input_df = input_df.set_index(
        [
            input_df.index,
            pd.Index([string_name] * len(input_df)),
            pd.Index([type] * len(input_df)),
        ]
    )
    input_df = input_df.rename_axis(row_index_names)
    out_df = (
        out_df.add(input_df, fill_value=0).fillna(out_df).fillna(input_df)
    )  # try combine_first instead of update??
    return out_df


if __name__ == "__main__":
    # User configuration for input data:
    resolution = "2190SEG"  # either 'XXXh' for equal time steps
    # or 'XXXSEG' for time segmentation
    sector_opts = f"elec_s_62_lv99__{resolution}-T-H-B-I-A"
    years = ["2030", "2035", "2040", "2045", "2050"]
    all_years = ["2020", "2030", "2035", "2040", "2045", "2050"]
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

    compare_scenarios = [
        True,
        False,
    ]  # Flag to determine if scenarios are written to the same plot

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
                path_to_networks / f"{sector_opts}_{year}.nc"
            )
            curr_networks.update({scen: n})

        networks.update({year: curr_networks})

    # ENERGY BALANCES
    balance_resultdir = (
        resultdir / "Balances"
    )  # folder where Excel files and graphs are stored
    if not os.path.exists(balance_resultdir):
        os.makedirs(balance_resultdir)

    # extract balance for (groups of) clusters/countries
    country_to_plot = "DE"
    # see configurable_energy_balance.py
    carrier_for_balance = "electricity"
    get_standard_balances(
        networks,
        carrier_for_balance,
        years,
        scenarios,
        balance_resultdir,
        country_to_plot,
        compare_scenarios,
    )

    carrier_for_balance = "gas"
    get_standard_balances(
        networks,
        carrier_for_balance,
        years,
        scenarios,
        balance_resultdir,
        country_to_plot,
        compare_scenarios,
    )

    carrier_for_balance = "low voltage"
    get_standard_balances(
        networks,
        carrier_for_balance,
        years,
        scenarios,
        balance_resultdir,
        country_to_plot,
        compare_scenarios,
    )

    carrier_for_balance = "H2"
    get_standard_balances(
        networks,
        carrier_for_balance,
        years,
        scenarios,
        balance_resultdir,
        country_to_plot,
        compare_scenarios,
    )

    carrier_for_balance = "heat"
    get_standard_balances(
        networks,
        carrier_for_balance,
        years,
        scenarios,
        balance_resultdir,
        country_to_plot,
        compare_scenarios,
    )

    carrier_for_balance = "urban central heat"
    get_standard_balances(
        networks,
        carrier_for_balance,
        years,
        scenarios,
        balance_resultdir,
        country_to_plot,
        compare_scenarios,
    )
