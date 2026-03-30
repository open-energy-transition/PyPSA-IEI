import os
from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import log

# Stylesheet for colors
plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")


def analyze_system_cost(
    main_dir,
    runs,
    resultdir,
    sel_scen,
    color_scheme,
    years,
    backup_capas=False,
):
    """
    Creates plots with capital, operational and total costs for
    components of european energy system
        - for comparison of scenarios every relevant year
        - for selected scenario residual to capital, operational or
          total costs of other scenarios
    Creates Excel with total costs over whole period of time

    Parameters
    ----------
    main_dir : str
        path of main directory
    runs : dict
        dict folders of scenarios
    resultdir : str
        path of resultdirectory
    sel_scen : str
        string of selected scenario
    color_scheme : dict
        dictionary mapping scenario names to color codes
        used for plotting
    years : list
        list of relevant years
    backup_capas : bool, optional
        boolean that adds national backup capacities to
        total_overinvest.png, by default False

    Returns
    -------
    None
    """
    log("Starting: analyze_system_cost")

    # Initial variables
    reference_year = "2050"
    # Set colors
    COLORS = mpl.rcParams["axes.prop_cycle"].by_key()["color"]
    # Set path
    directory_paths = {
        key: main_dir / "results" / item for key, item in runs.items()
    }
    mapping_path = main_dir / "scripts_analysis" / "Mapping_system_costs.csv"
    # Set reference scenario
    difference_paths = directory_paths.copy()
    del difference_paths[sel_scen]

    # Load the data
    column_names = ["carrier type", "cost type", "carrier"] + years
    df_data = {}  # Empty dictionary to store the transformed dataframes
    for scenario, path in directory_paths.items():
        # Read csv
        df = pd.read_csv(path / "csvs" / "costs.csv")
        # Transform dataframe
        full_years = df.iloc[2, 3:]
        drop_years_idx = [
            idx for idx, value in full_years.items() if value not in years
        ]
        df.drop(columns=drop_years_idx, inplace=True)
        df.drop(index=range(0, 3), inplace=True)
        df.columns = column_names
        df.iloc[:, 3:] = df.iloc[:, 3:].astype(float)
        df = df.melt(
            id_vars=["carrier type", "cost type", "carrier"],
            var_name="year",
            value_name="value",
        )
        df.sort_values("year", inplace=True)
        df.reset_index(drop=True, inplace=True)
        df_data[scenario] = df

    # Get scenario list
    scenarios = list(df_data.keys())
    # Read mapping and join it to the data
    df_mapping = pd.read_csv(mapping_path, delimiter=";")
    for scenario, df in df_data.items():
        df_data[scenario] = df_data[scenario].merge(
            df_mapping, how="left", on=["carrier type", "carrier"]
        )

    # Filter data by capex
    plot_data = df_data[sel_scen][df_data[sel_scen]["cost type"] == "capital"]
    summed_data = (
        plot_data.groupby(["capex", "year"])["value"].sum().reset_index()
    )
    sorted_data = summed_data[
        summed_data["year"] == reference_year
    ].sort_values(by="value", ascending=False)
    capex_list = sorted_data["capex"].tolist()

    ## 1. Plot infrastructure costs
    # Stylesheet for infrastructure costs
    plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
    # Initial plot settings and variables
    fig0, ax0 = plt.subplots(figsize=(4, 4))
    r_cap = {}
    # Position of bars for dict_df[first_scenario] on x axis
    first_scenario, first_value = next(iter(df_data.items()))
    # Bar width
    barWidth_cap = 0.8 / len(df_data)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in df_data.items():
        r_cap[scenario] = [x + i * barWidth_cap + 0.3 for x in r0]
        i = i + 1
    labels_scen = []
    for scenario_use in scenarios:
        labels_scen.append(scenario_use)
    # Create and fill array with labels for bar charts on x axis
    scenarios_use = []
    for j in range(len(years)):
        for k in labels_scen:
            scenarios_use.append(k)
    x_ticks = []

    # Plot
    pivot_data = {}
    for scenario, path in directory_paths.items():
        # Filter data
        pivot_data[scenario] = process_data_infrastructure_cost(
            scenario, df_data
        )

        # Create the stacked bar chart
        for j in range(0, len(r_cap[scenario])):
            r_cap[scenario][j] = np.round(r_cap[scenario][j], 1)
        keys_cap = pivot_data[scenario].keys()

        diff = 0.0115
        bottoms_cap = np.zeros(len(pivot_data[scenario]))
        for i in range(0, len(keys_cap)):
            arr_cap = np.array(pivot_data[scenario].loc[:, keys_cap[i]])
            if i > 0:
                if scenario == first_scenario:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        bottom=bottoms_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                        label=keys_cap[i],
                    )
                else:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        bottom=bottoms_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                    )
                bottoms_cap = np.add(bottoms_cap, arr_cap)
            else:
                if scenario == first_scenario:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                        label=keys_cap[i],
                    )
                else:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                    )
                bottoms_cap = np.add(bottoms_cap, arr_cap)

        for j in range(0, len(r_cap[scenario])):
            if r_cap[scenario][j] not in x_ticks:
                x_ticks.append(r_cap[scenario][j])

        # Plot settings
        ax0.set_ylabel(
            "Annualised infra. invest. (bn EUR/yr.)"
        )  # Set the label for the y-axis
        handles, labels = (
            ax0.get_legend_handles_labels()
        )
        ax0.legend(
            reversed(handles),
            reversed(labels),
            bbox_to_anchor=(0.5, 1.1),
            ncol=2,
        )
    x_lab_years = [
        r_cap[scenario][i] - (len(labels_scen) - 1) * (barWidth_cap - diff) / 2
        for i in range(0, len(r_cap[scenario]))
    ]
    ax0.set_xticks(x_lab_years, years)
    ax0.xaxis.set_ticks_position("top")
    # Second x-axis
    x_ticks.sort()
    secax0 = ax0.secondary_xaxis("bottom")
    secax0.set_xticks(
        x_ticks,
        scenarios_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    plt.tight_layout()
    plt.savefig(
        resultdir / "infrastructure_capital_cost.png"
    )  # Display the chart
    plt.close()

    ## 2. Plot absolute capital costs
    # Stylesheet for absolute capital costs
    plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
    # Initial plot settings and variables
    fig0, ax0 = plt.subplots(figsize=(6.2, 4.33))
    r_cap = {}
    # Position of bars for dict_df[first_scenario] on x axis
    first_scenario, first_value = next(iter(df_data.items()))
    # Bar width
    barWidth_cap = 0.8 / len(df_data)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in df_data.items():
        r_cap[scenario] = [x + i * barWidth_cap + 0.3 for x in r0]
        i = i + 1
    labels_scen = []
    for scenario_use in scenarios:
        labels_scen.append(scenario_use)
    # Create and fill array with labels for bar charts on x axis
    scenarios_use = []
    for j in range(len(years)):
        for k in labels_scen:
            scenarios_use.append(k)
    x_ticks_cap = []
    x_ticks_op = []
    x_ticks = []

    # Plot
    pivot_ordered = {}
    for scenario, path in directory_paths.items():
        # Filter data
        pivot_data = process_data_capital_cost(scenario, df_data)

        # Create the stacked bar chart
        pivot_ordered[scenario] = pivot_data[capex_list]
        for j in range(0, len(r_cap[scenario])):
            r_cap[scenario][j] = np.round(r_cap[scenario][j], 1)
        keys_cap = pivot_ordered[scenario].keys()

        diff = 0.0115
        bottoms_cap = np.zeros(len(pivot_ordered[scenario]["import"]))
        for i in range(0, len(keys_cap)):
            arr_cap = np.array(pivot_ordered[scenario][keys_cap[i]])
            if i > 0:
                if scenario == first_scenario:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        bottom=bottoms_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                        label=keys_cap[i],
                    )
                else:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        bottom=bottoms_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                    )
                bottoms_cap = np.add(bottoms_cap, arr_cap)
            else:
                if scenario == first_scenario:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                        label=keys_cap[i],
                    )
                else:
                    ax0.bar(
                        r_cap[scenario],
                        arr_cap,
                        width=barWidth_cap - diff,
                        color=COLORS[i],
                    )
                bottoms_cap = np.add(bottoms_cap, arr_cap)

        for j in range(0, len(r_cap[scenario])):
            if r_cap[scenario][j] not in x_ticks_cap:
                x_ticks_cap.append(r_cap[scenario][j])

        # Plot settings
        ax0.set_ylabel(
            "Annualised capital cost (bn EUR)"
        )  # Set the label for the y-axis
        handles, labels = (
            ax0.get_legend_handles_labels()
        )
        ax0.legend(
            reversed(handles),
            reversed(labels),
            bbox_to_anchor=(0.5, 1.1),
            ncol=2,
        )
    x_lab_years = [
        r_cap[scenario][i] - (len(labels_scen) - 1) * (barWidth_cap - diff) / 2
        for i in range(0, len(r_cap[scenario]))
    ]
    ax0.set_xticks(x_lab_years, years)
    ax0.xaxis.set_ticks_position("top")
    # Second x-axis
    x_ticks_cap.sort()
    secax0 = ax0.secondary_xaxis("bottom")
    secax0.set_xticks(
        x_ticks_cap,
        scenarios_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    plt.tight_layout()
    plt.savefig(resultdir / "absolute_capital_cost.png")  # Display the chart
    plt.close()

    # Residual capital costs | operational costs plot
    residual = {}
    for scenario, path in difference_paths.items():

        ## 3. Plot residual capital cost
        # Updated stylesheet for residual capital costs
        plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
        # Data
        residual[scenario] = pivot_ordered[scenario] - pivot_ordered[sel_scen]
        # Plot
        residual[scenario].plot(kind="bar", stacked=True)
        plt.xlabel("")  # Set the label for the x-axis
        plt.ylabel(
            "Residual capital costs (bn EUR)"
        )  # Set the label for the y-axis
        plt.xticks(rotation=0)
        plt.axhline(y=0, color="black", linewidth=1)
        handles, labels = (
            plt.gca().get_legend_handles_labels()
        )
        plt.legend(
            reversed(handles),
            reversed(labels),
            bbox_to_anchor=(0.5, 1),
            ncol=2,
        )  # Add a legend
        plt.tight_layout()
        plt.savefig(
            resultdir / f"residual_capital_cost_{sel_scen}_{scenario}.png"
        )  # Display the chart
        plt.close()

        ## 4. Plot operational costs
        # Updated stylesheet for operational costs
        plt.style.use("./plot_stylesheets/style_rectanglecharts.mplstyle")
        # Initial plot settings and variables
        fig2, ax2 = plt.subplots()
        r_op = {}
        # Position of bars for dict_df[first_scenario] on x axis
        first_scenario, first_value = next(iter(df_data.items()))
        # Bar width
        barWidth_op = 0.8 / len(df_data)
        r0 = np.arange(len(years))
        i = 0
        # Position of bars for df2 on x axis
        for scenario, df in df_data.items():
            r_op[scenario] = [x + i * barWidth_op + 0.3 for x in r0]
            i = i + 1

        # Plot
        pivot_data_op = {}
        for scenario, path in directory_paths.items():
            # Filter the data
            plot_data = df_data[scenario][
                df_data[scenario]["cost type"] == "marginal"
            ]
            # Group by "opex" and "year" and sum the values
            summed_data = (
                plot_data.groupby(["opex", "year"])["value"]
                .sum()
                .reset_index()
            )
            # Pivot the dataframe to prepare for plotting
            pivot_data_op[scenario] = (
                summed_data.pivot(index="year", columns="opex", values="value")
                * 1e-09
            )

            # Create the stacked bar chart
            for j in range(0, len(r_op[scenario])):
                r_op[scenario][j] = np.round(r_op[scenario][j], 1)
            keys_op = pivot_data_op[scenario].keys()

            diff_op = 0.0115
            bottoms_op = np.zeros(len(pivot_data_op[scenario]["import"]))
            for i in range(0, len(keys_op)):
                arr_op = np.array(pivot_data_op[scenario][keys_op[i]])
                if i > 0:
                    if scenario == first_scenario:
                        ax2.bar(
                            r_op[scenario],
                            arr_op,
                            bottom=bottoms_op,
                            width=barWidth_op - diff_op,
                            color=COLORS[i],
                            label=keys_op[i],
                        )
                    else:
                        ax2.bar(
                            r_op[scenario],
                            arr_op,
                            bottom=bottoms_op,
                            width=barWidth_op - diff_op,
                            color=COLORS[i],
                        )
                    bottoms_op = np.add(bottoms_op, arr_op)
                else:
                    if scenario == first_scenario:
                        ax2.bar(
                            r_op[scenario],
                            arr_op,
                            width=barWidth_op - diff_op,
                            color=COLORS[i],
                            label=keys_op[i],
                        )
                    else:
                        ax2.bar(
                            r_op[scenario],
                            arr_op,
                            width=barWidth_op - diff_op,
                            color=COLORS[i],
                        )
                    bottoms_op = np.add(bottoms_op, arr_op)

            for j in range(0, len(r_op[scenario])):
                if r_op[scenario][j] not in x_ticks_op:
                    x_ticks_op.append(r_op[scenario][j])

            # Plot settings
            ax2.set_ylabel(
                "Operational costs (bn EUR)"
            )  # Set the label for the y-axis
            handles, labels = (
                ax2.get_legend_handles_labels()
            )  # Flip the order of the legend
            ax2.legend(
                reversed(handles),
                reversed(labels),
                bbox_to_anchor=(0.5, 1.1),
                ncol=3,
            )
        x_lab_op = [
            r_op[scenario][i]
            - (len(labels_scen) - 1) * (barWidth_op - diff_op) / 2
            for i in range(0, len(r_op[scenario]))
        ]
        ax2.set_xticks(x_lab_op, years)
        ax2.xaxis.set_ticks_position("top")
        # Second x-axis
        x_ticks_op.sort()
        secax1 = ax2.secondary_xaxis("bottom")
        secax1.set_xticks(
            x_ticks_op,
            scenarios_use,
            rotation=90,
            fontproperties={"weight": "normal", "style": "normal"},
        )
        y_min, y_max = plt.ylim()
        plt.ylim(y_min, y_max * 1.05)
        plt.tight_layout()
        plt.savefig(resultdir / "operational_costs.png")  # Display the chart
        plt.close()

    ## 5. Plot residual operational costs
    # Updated stylesheet for residual capital costs
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    residual_op = {}
    for scenario, path in difference_paths.items():
        # Data
        residual_op[scenario] = (
            pivot_data_op[scenario] - pivot_data_op[sel_scen]
        )
        # Plot
        residual_op[scenario].plot.bar(stacked=True)
        plt.xlabel("")  # Set the label for the x-axis
        plt.ylabel(
            "Residual operational costs (bn EUR)"
        )  # Set the label for the y-axis
        plt.xticks(rotation=0)
        plt.axhline(y=0, color="black", linewidth=1)
        handles, labels = (
            plt.gca().get_legend_handles_labels()
        )
        plt.legend(
            reversed(handles),
            reversed(labels),
            bbox_to_anchor=(0.5, 1),
            ncol=3,
        )  # Add a legend
        y_min, y_max = plt.ylim()
        plt.ylim(y_min * 1.05, y_max * 1.05)
        plt.tight_layout()
        plt.savefig(
            resultdir / f"residual_operational_costs_{sel_scen}_{scenario}.png"
        )  # Display the chart
        plt.close()

    # Merge Data
    pivot_data_merged = {}
    for scenario, path in directory_paths.items():
        pivot_data_op[scenario] = pivot_data_op[scenario].rename(
            columns={"others": "others (opex)", "import": "import (opex)"}
        )
        pivot_ordered[scenario] = pivot_ordered[scenario].rename(
            columns={"others": "others (capex)", "import": "import (capex)"}
        )
        pivot_data_merged[scenario] = pd.merge(
            pivot_data_op[scenario], pivot_ordered[scenario], on="year"
        )

    ## 6. Plot total costs
    # Updated stylesheet for total costs
    plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
    # Initial plot settings and variables
    fig, ax1 = plt.subplots()
    r = {}
    # Position of bars for dict_df[first_scenario] on x axis
    first_scenario, first_value = next(iter(df_data.items()))
    # Bar width
    barWidth = 0.8 / len(df_data)
    r0 = np.arange(len(years))
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in df_data.items():
        r[scenario] = [x + i * barWidth + 0.3 for x in r0]
        i = i + 1

    # Plot
    for scenario, path in directory_paths.items():
        # Create the stacked bar chart
        for j in range(0, len(r[scenario])):
            r[scenario][j] = np.round(r[scenario][j], 1)
        keys = pivot_data_merged[scenario].keys()

        diff = 0.0115
        bottoms = np.zeros(len(pivot_data_merged[scenario]["transformation"]))
        for i in range(0, len(keys)):
            arr = np.array(pivot_data_merged[scenario][keys[i]])
            if i > 0:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        arr,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[i],
                        label=keys[i],
                    )  # , edgecolor='black',index_mapping[scenario]
                else:
                    ax1.bar(
                        r[scenario],
                        arr,
                        bottom=bottoms,
                        width=barWidth - diff,
                        color=COLORS[i],
                    )
                bottoms = np.add(bottoms, arr)
            else:
                if scenario == first_scenario:
                    ax1.bar(
                        r[scenario],
                        arr,
                        width=barWidth - diff,
                        color=COLORS[i],
                        label=keys[i],
                    )
                else:
                    ax1.bar(
                        r[scenario],
                        arr,
                        width=barWidth - diff,
                        color=COLORS[i],
                    )
                bottoms = np.add(bottoms, arr)

        for j in range(0, len(r[scenario])):
            if r[scenario][j] not in x_ticks:
                x_ticks.append(r[scenario][j])

        # Plot settings
        ax1.set_ylabel("Total costs (bn EUR)")  # Set the label for the y-axis
        handles, labels = (
            ax1.get_legend_handles_labels()
        )
        ax1.legend(
            reversed(handles), reversed(labels), bbox_to_anchor=(1, 0.5)
        )
    x_lab = [
        r[scenario][i] - (len(labels_scen) - 1) * (barWidth - diff) / 2
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
    plt.tight_layout()
    plt.savefig(resultdir / "total_costs.png")  # Display the chart
    plt.close()

    ## 7. Plot residual total costs
    # Updated stylesheet for residual total costs
    plt.style.use("./plot_stylesheets/style_squarecharts_r.mplstyle")
    residual = {}
    for scenario, path in difference_paths.items():
        # Data
        residual[scenario] = (
            pivot_data_merged[scenario] - pivot_data_merged[sel_scen]
        )
        # Plot
        residual[scenario].plot.bar(stacked=True)
        plt.xlabel("")  # Set the label for the x-axis
        plt.ylabel(
            "Residual total costs (bn EUR)"
        )  # Set the label for the y-axis
        plt.xticks(rotation=0)
        plt.axhline(y=0, color="black", linewidth=1)
        handles, labels = (
            plt.gca().get_legend_handles_labels()
        )  # Flip the order of the legend
        plt.legend(
            reversed(handles), reversed(labels), bbox_to_anchor=(1, 0.5)
        )  # Add a legend
        plt.tight_layout()
        plt.savefig(
            resultdir / f"residual_total_costs_{sel_scen}_{scenario}.png"
        )  # Display the chart
        plt.close()

    # Load additional gas data
    backup_capas_path = (
        resultdir.parent / "Balances" / "gas_turbine_backup_costs.xlsx"
    )
    if not os.path.exists(backup_capas_path):
        backup_capas = False
    if backup_capas:
        gas_cost = (
            pd.read_excel(backup_capas_path, sheet_name="All", index_col=0)
            * 1e-09
        )

    ## 8. Plot total overinvestment
    # Stylesheet for plot_TWkm
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    # Initial plot settings and variables
    fig, ax = plt.subplots()
    r = {}
    # Get dict + df for scenarios except from sel_scen
    all_scen = list(pivot_data_merged.keys())
    diff_scen = [item for item in all_scen if item != sel_scen]
    diff_dict = {key: pivot_data_merged[key] for key in diff_scen}
    # Position of bars for dict_df[first_scenario] on x axis
    num_scenario = len(diff_dict)
    # Bar width
    barWidth = 0.8 / num_scenario
    r0 = np.arange(len(years))
    x_ticks_cap = []
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in diff_dict.items():
        r[scenario] = [x + i * barWidth for x in r0]
        i = i + 1
        x_ticks_cap = x_ticks_cap + r[scenario]

    # Create barplot
    for scenario, df in diff_dict.items():
        for year in years:
            # Calculate data
            # Overinvestment
            cost_sel = pivot_data_merged[sel_scen].sum(axis=1)
            cost_scen = diff_dict[scenario].sum(axis=1)
            overinvest = cost_scen.loc[year] - cost_sel.loc[year]

            # Addidtional gas overinvestment
            overinvest_gas = 0
            gas_color = "darkgrey"
            if backup_capas:
                national = ["CN", "SN"]
                if sel_scen == "CE" and scenario in national:
                    overinvest_gas = gas_cost.loc[scenario, year]

            # Plot
            index = years.index(year)
            ax.bar(
                r[scenario][index],
                overinvest,
                color=color_scheme[scenario],
                width=barWidth,
                label=scenario,
            )
            ax.bar(
                r[scenario][index],
                overinvest_gas,
                bottom=overinvest,
                color=gas_color,
                width=barWidth,
                label="gas",
            )

    # Plot settings
    ax.set_ylabel("System cost difference (bn EUR/yr.)")
    ax.set_xticks(
        [r + (num_scenario - 1) / 2 * barWidth for r in range(len(years))],
        years,
    )
    scenario_use = [
        scen for scen in diff_dict.keys() for _ in range(len(years))
    ]
    ax.xaxis.set_ticks_position("top")
    # Second x-axis
    sec_ax = ax.secondary_xaxis("bottom")
    sec_ax.set_xticks(
        x_ticks_cap,
        scenario_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    y_min, y_max = plt.ylim()
    plt.ylim(y_min * 1.05, y_max * 1.05)
    if backup_capas:
        ax.text(
            2.1, y_max - 1, "national backup capacities$^{1}$", color=gas_color
        )
        ax.text(
            -0.5,
            -6.5,
            f"$^{1}$Post-optimisation estimate",
            fontsize=7,
            verticalalignment="bottom",
        )
    plt.tight_layout()
    fig.savefig(resultdir / "total_overinvestment.png")
    plt.close()

    # Calculate integrated total costs
    dict_int_costs = calculate_integrated_total_costs(
        directory_paths, years, pivot_data_merged
    )
    # For gas (code artificially adjusted for function)
    gas_dict = {
        index: pd.DataFrame(gas_cost.loc[index]) for index in gas_cost.index
    }
    gas_int_costs = calculate_integrated_total_costs(
        directory_paths, years, gas_dict
    )

    ## 9. Plot integrated total costs
    # Stylesheet for plot_TWkm
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    # Initial plot settings and variables
    fig, ax = plt.subplots()
    r = {}
    # Position of bars for dict_df[first_scenario] on x axis
    num_scenario = len(dict_int_costs)
    # Bar width
    barWidth = 0.8 / num_scenario
    r0 = np.arange(len(years))
    x_ticks_cap = []
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in dict_int_costs.items():
        r[scenario] = [x + i * barWidth for x in r0]
        i = i + 1
        x_ticks_cap = x_ticks_cap + r[scenario]

    # Create barplot
    for scenario, df in dict_int_costs.items():
        for year in years:
            # Calculate data
            cost_scen = dict_int_costs[scenario].loc[year]
            # Plot
            index = years.index(year)
            ax.bar(
                r[scenario][index],
                cost_scen,
                color=color_scheme[scenario],
                width=barWidth,
                label=scenario,
            )

    # Plot settings
    ax.set_ylabel("Integrated total costs (bn EUR)")
    ax.set_xticks(
        [r + (num_scenario - 1) / 2 * barWidth for r in range(len(years))],
        years,
    )
    scenario_use = [
        scen for scen in dict_int_costs.keys() for _ in range(len(years))
    ]
    ax.xaxis.set_ticks_position("top")
    # Second x-axis
    sec_ax = ax.secondary_xaxis("bottom")
    sec_ax.set_xticks(
        x_ticks_cap,
        scenario_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    y_min, y_max = plt.ylim()
    plt.ylim(y_min, y_max * 1.05)
    plt.tight_layout()
    fig.savefig(resultdir / "integrated_total_costs.png")
    plt.close()

    ## 10. Plot integrated difference costs
    # Stylesheet for plot_TWkm
    plt.style.use("./plot_stylesheets/style_squarecharts.mplstyle")
    # Initial plot settings and variables
    fig, ax = plt.subplots()
    r = {}
    # Get dict + df for scenarios except from sel_scen
    all_scen = list(dict_int_costs.keys())
    diff_scen = [item for item in all_scen if item != sel_scen]
    diff_dict = {key: dict_int_costs[key] for key in diff_scen}
    diff_gas_dict = {key: gas_int_costs[key] for key in diff_scen}
    # Position of bars for dict_df[first_scenario] on x axis
    num_scenario = len(diff_dict)
    # Bar width
    barWidth = 0.8 / num_scenario
    r0 = np.arange(len(years))
    x_ticks_cap = []
    i = 0
    # Position of bars for df2 on x axis
    for scenario, df in diff_dict.items():
        r[scenario] = [x + i * barWidth for x in r0]
        i = i + 1
        x_ticks_cap = x_ticks_cap + r[scenario]

    # Create barplot
    for scenario, df in diff_dict.items():
        for year in years:
            # Calculate data
            # Overinvestment
            cost_sel = dict_int_costs[sel_scen].loc[year]
            cost_scen = diff_dict[scenario].loc[year]
            overinvest = cost_scen - cost_sel

            # Additional gas overinvestment
            overinvest_gas = 0
            gas_color = "darkgrey"
            if backup_capas:
                national = ["CN", "SN"]
                if sel_scen == "CE" and scenario in national:
                    gas_cost_sel = 0
                    gas_cost_scen = diff_gas_dict[scenario].loc[year]
                    overinvest_gas = gas_cost_scen - gas_cost_sel

            # Plot
            index = years.index(year)
            ax.bar(
                r[scenario][index],
                overinvest,
                color=color_scheme[scenario],
                width=barWidth,
                label=scenario,
            )
            ax.bar(
                r[scenario][index],
                overinvest_gas,
                bottom=overinvest,
                color=gas_color,
                width=barWidth,
                label="gas",
            )

    # Plot settings
    ax.set_ylabel("Cumulated system cost difference (bn EUR)")
    ax.set_xticks(
        [r + (num_scenario - 1) / 2 * barWidth for r in range(len(years))],
        years,
    )
    scenario_use = [
        scen for scen in diff_dict.keys() for _ in range(len(years))
    ]
    ax.xaxis.set_ticks_position("top")
    # Second x-axis
    sec_ax = ax.secondary_xaxis("bottom")
    sec_ax.set_xticks(
        x_ticks_cap,
        scenario_use,
        rotation=90,
        fontproperties={"weight": "normal", "style": "normal"},
    )
    y_min, y_max = plt.ylim()
    plt.ylim(y_min * 1.05, y_max * 1.05)
    if backup_capas:
        ax.text(
            1.6,
            y_max - 100,
            "national backup capacities$^{1}$",
            color=gas_color,
        )
        ax.text(
            -0.5,
            -120,
            f"$^{1}$Post-optimisation estimate",
            fontsize=7,
            verticalalignment="bottom",
        )
    plt.tight_layout()
    fig.savefig(resultdir / "integrated_difference_costs.png")
    plt.close()

    ## 11. Save cost data in excel format
    simple_mapping = {
        "Total": [
            "import (opex)",
            "operational costs",
            "others (opex)",
            "power generation",
            "heat generation",
            "infrastructure",
            "others (capex)",
            "transformation",
            "import (capex)",
        ],
        "Infrastructure Invest.": ["infrastructure", "import (capex)"],
        "Technology Invest.": [
            "power generation",
            "heat generation",
            "transformation",
            "others (capex)",
        ],
        "Operational & Fuel Costs": [
            "import (opex)",
            "operational costs",
            "others (opex)",
        ],
    }
    column_names = ["Category", "Subcategory", "Name", "Unit"] + [
        f"{year} {scen}" for year in years for scen in scenarios
    ]
    int_cost_mapped = pd.DataFrame(columns=column_names)
    annual_cost_mapped = pd.DataFrame(columns=column_names)
    for mapping in simple_mapping.items():
        # Calculate integrated total costs
        temp_costs = calculate_integrated_total_costs(
            directory_paths, years, pivot_data_merged, mapping
        )
        for year in years:
            for scen in scenarios:
                int_cost_mapped.loc[mapping[0], f"{year} {scen}"] = round(
                    temp_costs[scen][year]
                )
                annual_cost_mapped.loc[mapping[0], f"{year} {scen}"] = round(
                    pivot_data_merged[scen].loc[year, mapping[1]].sum()
                )
    # Prepare dataframe for integrated data
    int_cost_mapped.loc[:, "Category"] = "Costs"
    int_cost_mapped.loc[:, "Name"] = "Integrated costs (2030-year)"
    int_cost_mapped.loc[:, "Unit"] = "[Billion €]"
    int_cost_mapped.loc[:, "Subcategory"] = int_cost_mapped.index

    # Prepare annualised dataframe
    annual_cost_mapped.loc[:, "Category"] = "Costs"
    annual_cost_mapped.loc[:, "Name"] = "Annualised"
    annual_cost_mapped.loc[:, "Unit"] = "[Billion €/yr.]"
    annual_cost_mapped.loc[:, "Subcategory"] = int_cost_mapped.index

    costs_for_excel = pd.concat([annual_cost_mapped, int_cost_mapped])
    # Save integrated total costs as excel
    # Write excel
    writer = pd.ExcelWriter(f"{resultdir}/total_costs.xlsx", engine="openpyxl")
    costs_for_excel.to_excel(writer, index=False)
    writer.close()
    # Save into KPI table
    kpi_path = resultdir.parent / "KPIs" / "Summary-Results-KPIs.xlsx"
    if os.path.exists(kpi_path):
        # Open the Excel file with `openpyxl` engine
        with pd.ExcelWriter(
            kpi_path, engine="openpyxl", mode="a", if_sheet_exists="overlay"
        ) as writer:
            # Append the new DataFrame to the existing sheet 'All_Countries'
            costs_for_excel.to_excel(
                writer,
                sheet_name="All_Countries",
                startrow=77,
                index=False,
                header=False,
            )

    log("Done: analyze_system_cost")


def process_data_infrastructure_cost(scenario, dict_data):
    """
    Filters and calculates infrastructure groups of european energy
    system from df_data dict per scenario

    Parameters
    ----------
    scenario : str
        current scenario
    dict_data : dict
        dict of components

    Returns
    -------
    DataFrame
        df filtered
    """
    df_scen = dict_data[scenario]
    # Transform dataframe
    df_inf = df_scen.query(
        '`cost type` == "capital" & capex == "infrastructure"'
    )
    df_inf["carrier"] = (
        df_inf["carrier"]
        .str.replace(r"H2 .*", "Hydrogen", regex=True)
        .str.replace(r"gas .*", "Methane", regex=True)
        .str.replace(r"CO2 .*", "CO$_2$", regex=True)
        .str.replace(r"AC", "Electricity", regex=True)
        .str.replace(r"DC", "Electricity", regex=True)
    )
    df_inf = df_inf.query(
        'carrier != "solid biomass transport" & '
        'carrier != "electricity distribution grid"'
    )
    df_inf = df_inf.groupby(["carrier", "year"])["value"].sum().reset_index()
    pivot_data = (
        df_inf.pivot(index="year", columns="carrier", values="value") * 1e-09
    )
    return pivot_data


def process_data_capital_cost(scenario, df_data):
    """
    Filters components of european energy system from df_data
    dictionary per scenario

    Parameters
    ----------
    scenario : str
        current scenario
    df_data : dict
        dict of components

    Returns
    -------
    DataFrame
        df filtered
    """
    # Filter the data
    plot_data = df_data[scenario].query('`cost type` == "capital"')

    # Group by "capex" and "year" and sum the values
    summed_data = (
        plot_data.groupby(["capex", "year"])["value"].sum().reset_index()
    )

    # Pivot the dataframe to prepare for plotting
    pivot_data = (
        summed_data.pivot(index="year", columns="capex", values="value")
        * 1e-09
    )

    return pivot_data


def calculate_integrated_total_costs(
    dir_paths, times, dict_all_costs, mapping=("Total", [])
):
    """
    Calculates integrated total costs for each year related
    to start-year.

    Parameters
    ----------
    dir_paths : dict
        dict paths to scenario folders
    times : list
        list of relevant years
    dict_all_costs : dict
        dict of components
    mapping : tuple, optional
        tuple with list of all columns that should be integrated,
        by default ("Total", [])

    Returns
    -------
    dict
        dict with integrated total costs per scenario
    """
    # Inital dict
    total_costs = {}

    # Calculate integrated total costs per scenario (aggregate years)
    for scenario, path in dir_paths.items():
        costs_year = pd.Series()
        for idx, year in enumerate(times):
            # Get data
            costs = dict_all_costs[scenario]
            # Calculate data with trapez-rule
            if mapping[0] == "Total":
                total_costs_pa = costs.sum(axis=1).to_numpy()
            else:
                total_costs_pa = costs[mapping[1]].sum(axis=1).to_numpy()
            current_years = np.array(times[: idx + 1]).astype(int)
            area = np.trapz(total_costs_pa[: idx + 1], current_years)
            if area == 0:
                area = total_costs_pa[idx]
            costs_year[year] = area
        total_costs[scenario] = costs_year

    return total_costs


def export_integrated_total_costs(res_dir, prim_scen, dict_all_costs):
    """
    Exports excel file with integrated total costs per scenario and the
    difference with selected scenario.

    Parameters
    ----------
    res_dir : str
        path of resultdirectory
    prim_scen : str
        string of selected scenario
    dict_all_costs : dict
        dict with integrated total costs per scenario

    Returns
    -------
    None
    """
    # Transform into dataframe
    df = pd.DataFrame(columns=["total_costs"])
    for scen in dict_all_costs.keys():
        df.loc[scen] = dict_all_costs[scen].loc["2050"]
    df.reset_index(inplace=True)
    df.rename(columns={"index": "scenario"}, inplace=True)

    # Difference with prim_scen
    index = df.index[df["scenario"] == prim_scen].tolist()
    df[f"diff_{prim_scen}"] = (
        df["total_costs"] - df.iloc[index[0]]["total_costs"]
    )

    # Write excel
    writer = pd.ExcelWriter(f"{res_dir}/total_costs.xlsx", engine="openpyxl")
    df.to_excel(writer, index=False)
    writer.close()


if __name__ == "__main__":
    # User configuration for input data
    years = ["2030", "2035", "2040", "2045", "2050"]
    sel_scen = "scenario_1"
    # insert run names for scenarios here:
    # Analysis on back up capacities are only available for the scenario names of national scenarios "CN" and "SN" and
    # in relation to the "CE" scenario.
    runs = {
        "scenario_1": "run_name_1",
        "scenario_2": "run_name_2",
        "scenario_3": "run_name_3",
        "scenario_4": "run_name_4",
    }
    scenario_colors = {
        "scenario_1": "#39C1CD",
        "scenario_2": "#F58220",
        "scenario_3": "#179C7D",
        "scenario_4": "#854006",
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

    costs_dir = resultdir / "costs"
    if not os.path.exists(costs_dir):
        os.mkdir(costs_dir)

    backup_caps = True
    analyze_system_cost(
        main_dir,
        runs,
        costs_dir,
        sel_scen,
        scenario_colors,
        years,
        backup_caps,
    )
