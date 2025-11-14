# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2020-2024 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT
"""
Build industrial energy demand per model region.
"""

import pandas as pd
import matplotlib.pyplot as plt


def preprocess_demand_data():
    """
    Preprocess TransHyDE data by parsing, renaming columns, and mapping carriers.

    Returns:
        pd.DataFrame: Preprocessed TransHyDE data.
    """

    # parse TransHyDE data
    demand_th = pd.read_csv(snakemake.input.transhyde_demand_csv)
    demand_th = demand_th.loc[demand_th["Sector"] == "Industry"]

    # rename for easier access
    rename_cols = {
        "NUTS 0": "country",
        "Energy carrier": "carrier",
        "Application or Process": "app",
        "Usage": "use",
    }
    demand_th.rename(rename_cols, axis=1, inplace=True)

    # map carriers from TransHyDE to PyPSA, to be completed after exchange with Tobias
    map_carriers = {
        "biomass": "solid biomass",
        "district heating": "low-temperature heat",
        "fossil fuel": "naphtha",
        "natural gas": "methane",
        "renewable methane": "methane",
        "solar energy": "low-temperature heat",
        "other fossil": "methane",  # contains coke oven gas, mine gas among others
        #'Other RES', # Can mostly be neglected
        #'Waste non-RES' # Substitute fuel for provision of high-temperature heat
    }
    demand_th["carrier"] = demand_th["carrier"].str.lower().replace(map_carriers)

    # TH country code lookup-table
    th_coco = (
        demand_th[["Country", "country"]]
        .set_index("Country")
        .drop_duplicates()
        .squeeze()
        .to_dict()
    )

    # group by country and carrier
    demand_th = demand_th.groupby(["country", "carrier"], as_index=True).sum(
        numeric_only=True
    )
    # clip negative methane demand in Bulgaria due to negative value of other fossil
    demand_th = demand_th.clip(lower=0.0).reset_index()

    # parse TransHyDE process emissions and append to df with industry demands
    emissions_th = pd.read_csv(snakemake.input.transhyde_emissions_csv)
    emissions_th = emissions_th.query(
        "Source == 'Process emissions' | (Source == 'Fuel oil' & Level_2 == 'Steam and hot water emissions by technology')"
    )

    emissions_th.rename(
        {"Country": "country", "Source": "carrier"}, axis=1, inplace=True
    )
    emissions_th["country"] = emissions_th["country"].map(th_coco)
    rename_carriers = {
        "Process emissions": "process emission",
        "Fuel oil": "process emission",
    }
    emissions_th["carrier"] = emissions_th["carrier"].replace(rename_carriers)
    emissions_th = (
        emissions_th.groupby(["country", "carrier"])
        .sum(numeric_only=True)
        .div(1e6)
        .reset_index()
    )
    demand_th = pd.concat([demand_th, emissions_th])

    # drop entries with irrelevant carriers
    to_drop = ["ambient heat", "other res", "waste non-res"]  # TODO: 'other fossil'
    demand_th = demand_th.loc[~demand_th["carrier"].isin(to_drop)]
    demand_th_p = demand_th.pivot(
        index="country", columns="carrier", values=snakemake.wildcards.planning_horizons
    )

    # change country codes for UK and Greece
    rename_countries = {"UK": "GB", "EL": "GR"}
    demand_th_p.rename(index=rename_countries, inplace=True)
    return demand_th_p


def scale_demand(nodal_df, demand_th_p, export_data=True):
    """
    Scale the nationally aggregated PyPSA demand based on TransHyDE demand
    keeping the intra-national distribution key.

    Parameters
    ----------
    nodal_df : pd.DataFrame
        pd.DataFrame containing PyPSA demand.
    demand_th_p : pd.DataFrame
        pd.DataFrame containing TransHyDE demand.
    export_data : bool (optional)
        Whether to export data prior to application of scaling.


    Returns
    ----------
    pd.DataFrame: pd.DataFrame containing the scaled PyPSA demand.
    """
    nodal_df["country"] = nodal_df.index.str[:2]
    nodal_df_grp = nodal_df.groupby("country").sum()

    # drop non-matchable countries
    to_drop = set(demand_th_p.index) - set(nodal_df_grp.index)
    print(
        f"Following country codes could not be matched and are thusly dropped: {to_drop}"
    )
    demand_th_p = demand_th_p.loc[~demand_th_p.index.isin(to_drop)]

    # Sum coal and coke for scaling according to TransHyDE coal demand
    nodal_df_grp_m = nodal_df_grp
    nodal_df_grp_m["coal"] += nodal_df_grp_m["coke"]

    # Sum process emissions and process emissions from feedstock for scaling according to TransHyDE process emissions
    nodal_df_grp_m["process emission"] += nodal_df_grp_m[
        "process emission from feedstock"
    ]

    # calculate scaling matrix with correction for coke and process emissions from feedstock
    factor = (demand_th_p / nodal_df_grp_m).fillna(1.0)
    factor["coke"] = factor["coal"]
    factor["process emission from feedstock"] = factor["process emission"]

    if export_data == True:
        fn = snakemake.output.nodal_pre
        nodal_df.to_csv(fn, index=True)

        fn = snakemake.output.factor
        factor.to_csv(fn, index=True)

    # apply scaling factor
    nodal_df = nodal_df.reset_index().set_index("country")
    nodal_df[
        nodal_df.drop(nodal_df.filter(like="TWh/a").columns, axis=1).columns
    ] *= factor
    nodal_df.reset_index(inplace=True)

    return nodal_df


def replace_zero_values(nodal_df, demand_th_p, nodal_df_check, export_data=True):
    """
    Replace zero values in PyPSA demand with values from TransHyDE demand, using weights of existing demands.

    Parameters
    ----------
    nodal_df : pd.DataFrame
        pd.DataFrame containing PyPSA demand.
    demand_th_p : pd.DataFrame
        pd.DataFrame containing TransHyDE demand.
    nodal_df_check : pd.DataFrame
        pd.DataFrame containing original nodal PyPSA demand.
    export_data : bool (optional)
        Whether to export data and create a plot after scaling. Defaults to True.

    Returns
    ----------
    pd.DataFrame: pd.DataFrame with zero values replaced.
    """

    nodal_df["weight"] = nodal_df.apply(
        lambda c: c.iloc[2:].sum()
        / nodal_df.loc[nodal_df["country"] == c["country"]].iloc[:, 2:].sum().sum(),
        axis=1,
    )
    for i, c in nodal_df.iterrows():
        nans = c[c.isna()]
        nans.drop(set(nans.index) - set(demand_th_p.columns), inplace=True)
        if c["country"] in demand_th_p.index:
            th_values = demand_th_p.loc[c["country"], nans.index]
            nodal_df.loc[i, nans.index] = th_values * c["weight"]
    nodal_df.set_index("TWh/a (MtCO2/a)", inplace=True)
    nodal_df.drop(["country", "weight"], axis=1, inplace=True)

    if export_data == True:
        # export demand dataframes as control

        fn = snakemake.output.demand_th
        demand_th_p.to_csv(fn, index=True)

        fn = snakemake.output.nodal_post
        nodal_df.to_csv(fn, index=True)

        # create and export plot for overriding process
        fig, ax = plt.subplots(1, 1)
        fig.set_size_inches(12, 5)
        pd.concat([nodal_df.sum(), nodal_df_check.sum()], axis=1).rename(
            columns={0: "post", 1: "pre"}
        )[["pre", "post"]].plot.bar(ax=ax, cmap="tab20")
        ax.set_xlabel("Energy carrier")
        ax.set_ylabel("Demand [TWh/a]")

        fn = snakemake.output.demand_plot
        fig.savefig(fn, bbox_inches="tight")

    return nodal_df


def process_data(nodal_df, export_data=True):
    """
    Process PyPSA demand data by scaling existing values and replacing zero values with TransHyDE data.

    Parameters
    ----------
    nodal_df : pd.DataFrame
        pd.DataFrame containing the PyPSA demand data.
    export_data : bool (optional)
        Whether to export data and create plots. Defaults to True.

    Returns:
    ----------
    pd.DataFrame: pd.DataFrame containing the processed PyPSA demand data.
    """
    nodal_df_check = nodal_df.copy()
    demand_th_p = preprocess_demand_data()
    nodal_df = scale_demand(nodal_df, demand_th_p, export_data=export_data)
    nodal_df = replace_zero_values(
        nodal_df, demand_th_p, nodal_df_check, export_data=export_data
    )
    return nodal_df


def remove_import_ammonia_demand(nodal_df):
    """
    Reduces the demand for energy carriers that are necessary to produce ammonia in case of ammonia imports

    Parameters
    ----------
    nodal_df : pd.DataFrame
        pd.DataFrame containing the PyPSA demand data.

    Returns:
    ----------
    pd.DataFrame: pd.DataFrame containing the processed PyPSA demand data.
    """
    ammonia_import_share = snakemake.config["sector"]["ammonia_import_share"] / 100
    MWh_NH3_per_tNH3 = snakemake.config["industry"]["MWh_NH3_per_tNH3"]
    industrial_energy_demand = pd.read_csv(
        snakemake.input.industrial_energy_demand, index_col=0
    )

    # if all countries use the same input ratios for ammonia in "industrial_energy_demand"
    MWh_H2_per_tNH3 = float(sector_ratios.loc["hydrogen", ("AL", "Ammonia")])
    MWh_elec_per_tNH3 = float(sector_ratios.loc["elec", ("AL", "Ammonia")])
    MWh_methane_per_tNH3 = float(sector_ratios.loc["methane", ("AL", "Ammonia")])
    import_tNH3 = (
        industrial_energy_demand["ammonia"]
        * 1e6
        * ammonia_import_share
        / MWh_NH3_per_tNH3
    )

    industrial_energy_demand["saved_MWh_H2_a"] = import_tNH3 * MWh_H2_per_tNH3
    industrial_energy_demand["saved_MWh_elec_a"] = import_tNH3 * MWh_elec_per_tNH3
    industrial_energy_demand["saved_MWh_methane_a"] = import_tNH3 * MWh_methane_per_tNH3

    # only reduce hydrogen demand, if the reduced demand is positive. If not, set demand to zero
    mask_ah = nodal_df["hydrogen"] > (industrial_energy_demand["saved_MWh_H2_a"] / 1e6)
    nodal_df.loc[mask_ah, "hydrogen"] -= (
        industrial_energy_demand["saved_MWh_H2_a"] / 1e6
    )
    nodal_df.loc[~mask_ah, "hydrogen"] = 0

    # only reduce electricity demand, if the reduced demand is positive. If not, set demand to zero
    mask_ae = nodal_df["electricity"] > (
        industrial_energy_demand["saved_MWh_elec_a"] / 1e6
    )
    nodal_df.loc[mask_ae, "electricity"] -= (
        industrial_energy_demand["saved_MWh_elec_a"] / 1e6
    )
    nodal_df.loc[~mask_ae, "electricity"] = 0

    # only reduce methane demand, if the reduced demand is positive. If not, set demand to zero
    mask_am = nodal_df["methane"] > (
        industrial_energy_demand["saved_MWh_methane_a"] / 1e6
    )
    nodal_df.loc[mask_am, "methane"] -= (
        industrial_energy_demand["saved_MWh_methane_a"] / 1e6
    )
    nodal_df.loc[~mask_am, "methane"] = 0

    return nodal_df


def remove_import_methanol_demand(nodal_df):
    """
    Reduces the demand for energy carriers that are necessary to produce methanol in case of methanol imports

    Parameters
    ----------
    nodal_df : pd.DataFrame
        pd.DataFrame containing the PyPSA demand data.

    Returns:
    ----------
    pd.DataFrame: pd.DataFrame containing the processed PyPSA demand data.
    """
    methanol_import_share = snakemake.config["sector"]["methanol_import_share"] / 100
    MWh_MeOH_per_tMeOH = snakemake.config["industry"]["MWh_MeOH_per_tMeOH"]
    industrial_energy_demand = pd.read_csv(
        snakemake.input.industrial_energy_demand, index_col=0
    )

    # if all countries use the same input ratios for methanol in "industrial_energy_demand"
    MWh_elec_per_tMeOH = float(sector_ratios.loc["elec", ("AL", "Methanol")])
    MWh_CH4_per_tMeOH = float(sector_ratios.loc["methane", ("AL", "Methanol")])
    import_tMeOH = (
        industrial_energy_demand["methanol"]
        * 1e6
        * methanol_import_share
        / MWh_MeOH_per_tMeOH
    )

    industrial_energy_demand["saved_MWh_elec_m"] = import_tMeOH * MWh_elec_per_tMeOH
    industrial_energy_demand["saved_MWh_methane_m"] = import_tMeOH * MWh_CH4_per_tMeOH

    # only reduce electricity demand, if the reduced demand is positive. If not, set demand to zero
    mask_me = nodal_df["electricity"] > (
        industrial_energy_demand["saved_MWh_elec_m"] / 1e6
    )
    nodal_df.loc[mask_me, "electricity"] -= (
        industrial_energy_demand["saved_MWh_elec_m"] / 1e6
    )
    nodal_df.loc[~mask_me, "electricity"] = 0

    # only reduce methane demand, if the reduced demand is positive. If not, set demand to zero
    mask_mm = nodal_df["methane"] > (
        industrial_energy_demand["saved_MWh_methane_m"] / 1e6
    )
    nodal_df.loc[mask_mm, "methane"] -= (
        industrial_energy_demand["saved_MWh_methane_m"] / 1e6
    )
    nodal_df.loc[~mask_mm, "methane"] = 0

    return nodal_df


if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        import os

        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        snakemake = mock_snakemake(
            "build_industrial_energy_demand_per_node",
            # simpl="",
            # clusters=48,
            planning_horizons=2030,
            configfile="...",  # INSERT PATH TO CONFIG FILE FOR DEBUGGING
        )
        os.chdir("..")

    # import ratios
    fn = snakemake.input.industry_sector_ratios
    sector_ratios = pd.read_csv(fn, header=[0, 1], index_col=0)

    # material demand per node and industry (Mton/a)
    fn = snakemake.input.industrial_production_per_node
    nodal_production = pd.read_csv(fn, index_col=0) / 1e3

    # energy demand today to get current electricity
    fn = snakemake.input.industrial_energy_demand_per_node_today
    nodal_today = pd.read_csv(fn, index_col=0)

    nodal_sector_ratios = pd.concat(
        {node: sector_ratios[node[:2]] for node in nodal_production.index}, axis=1
    )

    nodal_production_stacked = nodal_production.stack()
    nodal_production_stacked.index.names = [None, None]

    # final energy consumption per node and industry (TWh/a)
    nodal_df = (
        (nodal_sector_ratios.multiply(nodal_production_stacked))
        .T.groupby(level=0)
        .sum()
    )

    rename_sectors = {
        "elec": "electricity",
        "biomass": "solid biomass",
        "heat": "low-temperature heat",
    }
    nodal_df.rename(columns=rename_sectors, inplace=True)

    nodal_df["current electricity"] = nodal_today["electricity"]

    nodal_df.index.name = "TWh/a (MtCO2/a)"

    if snakemake.params.transhyde_data:
        transhyde_plot = snakemake.params.transhyde_plot
        nodal_df = process_data(nodal_df, export_data=transhyde_plot)
        if snakemake.config["sector"]["ammonia_import"]:
            nodal_df = remove_import_ammonia_demand(nodal_df)
        if snakemake.config["sector"]["methanol_import"]:
            nodal_df = remove_import_methanol_demand(nodal_df)
    fn = snakemake.output.industrial_energy_demand_per_node
    nodal_df.to_csv(fn, float_format="%.2f")
