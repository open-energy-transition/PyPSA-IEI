# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2020-2024 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT
"""
Prepares brownfield data from previous planning horizon.
"""

import logging
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import xarray as xr
from _helpers import update_config_with_sector_opts
from add_existing_baseyear import add_build_year_to_new_assets
from pypsa.clustering.spatial import normed_or_uniform

logger = logging.getLogger(__name__)
idx = pd.IndexSlice


def add_brownfield(n, n_p, year):
    logger.info(f"Preparing brownfield for the year {year}")

    # electric transmission grid set optimised capacities of previous as minimum
    ac_newmin_i = n.lines.s_nom_min < n_p.lines.s_nom_opt
    n.lines.loc[ac_newmin_i, 's_nom_min'] = n_p.lines.loc[ac_newmin_i, 's_nom_opt']
    dc_i = n.links[(n.links.carrier == "DC")].index
    links_dc = n.links.loc[dc_i, :]
    dc_newmin_i = links_dc[links_dc.loc[dc_i, "p_nom_min"]<n_p.links.loc[dc_i, "p_nom_opt"]].index
    n.links.loc[dc_newmin_i, "p_nom_min"] = n_p.links.loc[dc_newmin_i, "p_nom_opt"]

    for c in n_p.iterate_components(["Link", "Generator", "Store"]):
        attr = "e" if c.name == "Store" else "p"

        # first, remove generators, links and stores that track
        # CO2 or global EU values since these are already in n
        n_p.mremove(c.name, c.df.index[c.df.lifetime == np.inf])

        # remove assets whose build_year + lifetime < year
        n_p.mremove(c.name, c.df.index[c.df.build_year + c.df.lifetime < year])

        # remove assets if their optimized nominal capacity is lower than a threshold
        # since CHP heat Link is proportional to CHP electric Link, make sure threshold is compatible
        chp_heat = c.df.index[
            (c.df[f"{attr}_nom_extendable"] & c.df.index.str.contains("urban central"))
            & c.df.index.str.contains("CHP")
            & c.df.index.str.contains("heat")
        ]

        threshold = snakemake.params.threshold_capacity

        if not chp_heat.empty:
            threshold_chp_heat = (
                threshold
                * c.df.efficiency[chp_heat.str.replace("heat", "electric")].values
                * c.df.p_nom_ratio[chp_heat.str.replace("heat", "electric")].values
                / c.df.efficiency[chp_heat].values
            )
            n_p.mremove(
                c.name,
                chp_heat[c.df.loc[chp_heat, f"{attr}_nom_opt"] < threshold_chp_heat],
            )

        n_p.mremove(
            c.name,
            c.df.index[
                (c.df[f"{attr}_nom_extendable"] & ~c.df.index.isin(chp_heat))
                & (c.df[f"{attr}_nom_opt"] < threshold)
            ],
        )

        # copy over assets but fix their capacity
        c.df[f"{attr}_nom"] = c.df[f"{attr}_nom_opt"]
        c.df[f"{attr}_nom_extendable"] = False

        n.import_components_from_dataframe(c.df, c.name)

        # copy time-dependent
        selection = n.component_attrs[c.name].type.str.contains(
            "series"
        ) & n.component_attrs[c.name].status.str.contains("Input")
        for tattr in n.component_attrs[c.name].index[selection]:
            n.import_series_from_dataframe(c.pnl[tattr], c.name, tattr)

    # deal with gas network
    pipe_carrier = ["gas pipeline"]
    if snakemake.params.H2_retrofit:
        # drop capacities of previous year to avoid duplicating
        to_drop = n.links.carrier.isin(pipe_carrier) & (n.links.build_year != year)
        n.mremove("Link", n.links.loc[to_drop].index)

        # subtract the already retrofitted from today's gas grid capacity
        h2_retrofitted_fixed_i = n.links[
            (n.links.carrier == "H2 pipeline retrofitted")
            & (n.links.build_year != year)
        ].index
        gas_pipes_i = n.links[n.links.carrier.isin(pipe_carrier)].index
        CH4_per_H2 = 1 / snakemake.params.H2_retrofit_capacity_per_CH4
        fr = "H2 pipeline retrofitted"
        to = "gas pipeline"
        # today's pipe capacity
        pipe_capacity = n.links.loc[gas_pipes_i, "p_nom"]
        # already retrofitted capacity from gas -> H2
        already_retrofitted = (
            n.links.loc[h2_retrofitted_fixed_i, "p_nom"]
            .rename(lambda x: x.split("-2")[0].replace(fr, to) + f"-{year}")
            .groupby(level=0)
            .sum()
        )
        remaining_capacity = (
            pipe_capacity
            - CH4_per_H2
            * already_retrofitted.reindex(index=pipe_capacity.index).fillna(0)
        )
        n.links.loc[gas_pipes_i, "p_nom"] = remaining_capacity
        n.links.loc[gas_pipes_i, "p_nom_max"] = remaining_capacity
    else:
        new_pipes = n.links.carrier.isin(pipe_carrier) & (
            n.links.build_year == year
        )
        n.links.loc[new_pipes, "p_nom"] = 0.0
        n.links.loc[new_pipes, "p_nom_min"] = 0.0

    # update with new powerplants
    n_ppl = pypsa.Network(snakemake.input.base_powerplants)
    all_years = snakemake.config["scenario"]["planning_horizons"]
    previous_year = str(all_years[all_years.index(year) - 1])

    for ppl_component in n_ppl.iterate_components(["Link", "Generator"]):
        idx_ppl = ppl_component.df.index[ppl_component.df.index.to_series().apply(ends_with_year)
                                         & (ppl_component.df.index.str[-4:] > previous_year)
                                         & (ppl_component.df.index.str[-4:] <= str(year))]
        if ppl_component.name == "Generator":
            n.generators.loc[idx_ppl, 'p_nom'] = ppl_component.df.loc[idx_ppl, 'p_nom']
        if ppl_component.name == "Link":
            n.links.loc[idx_ppl, 'p_nom'] = ppl_component.df.loc[idx_ppl, 'p_nom']


    ### retrofitting of import gas generators

    # find indexes for all pipelines contributing to non-European imports
    natural_gas_pipes_i = n.generators.query(
        "carrier == 'import pipeline gas' & p_nom_extendable"
    ).index
    h2_pipes_ext_i = n.generators.query(
        "carrier == 'import pipeline-H2' & p_nom_extendable"
    ).index
    h2_pipes_fix_i = n.generators.query(
            "carrier == 'import pipeline-H2' & ~p_nom_extendable"
        ).index
    # find locations where import gas pipelines can be retrofitted to H2 pipelines
    clusters_for_retrofit = (natural_gas_pipes_i.str[:5].intersection(h2_pipes_ext_i.str[:5])
                             .intersection(h2_pipes_fix_i.str[:5]))
    # filter indixes of pipelines for locations where retrofitting can take place
    filtered_natural_gas_pipes_i = pd.Index([x for x in natural_gas_pipes_i if x[:5] in clusters_for_retrofit])
    filtered_h2_pipes_ext_i = pd.Index([x for x in h2_pipes_ext_i if x[:5] in clusters_for_retrofit])
    filtered_h2_pipes_fix_i = pd.Index([x for x in h2_pipes_fix_i if x[:5] in clusters_for_retrofit])

    # extract the capacity that the natural gas pipeline had before the last retrofitting step
    full_capacity_pipes = n.generators.loc[filtered_natural_gas_pipes_i, 'p_nom_max']
    # extract the capacity of the pipes that where retrofitted in the previous planning year
    retrofitted_capacity_pipes = n.generators.loc[filtered_h2_pipes_fix_i, 'p_nom']
    # get the capacity that the pipeline can have when it is fully used
    max_capacity_retrofit_pipes = n.generators.loc[filtered_h2_pipes_ext_i, 'p_nom_max']
    # calculate what is left as gas pipeline after the previous retrofitting step
    remaining_capacity_pipes = (full_capacity_pipes - CH4_per_H2 * retrofitted_capacity_pipes
                                .rename(lambda x: x[:5] + ' import pipeline gas').groupby(level=0).sum())
    # set the maximum capacity of the gas pipelines to what is left after retrofitting
    n.generators.loc[filtered_natural_gas_pipes_i, 'p_nom_max'] = remaining_capacity_pipes
    # calculate the capacity that is still left for retrofitting
    remaining_capacity_pipes_retro = (max_capacity_retrofit_pipes
                                      - retrofitted_capacity_pipes.rename(lambda x: x[:-4] + str(year))
                                      .groupby(level=0).sum())
    # set the capacity for optional retrofitting left from the previous year as the new maximum
    n.generators.loc[filtered_h2_pipes_ext_i, 'p_nom_max'] = remaining_capacity_pipes_retro

    # get the indexes of the generators that serve as import terminals
    natural_gas_terminal_i = n.generators.query(
        "carrier == 'import lng gas' & p_nom_extendable"
    ).index
    h2_terminal_retro_ext_i = n.generators.query(
        "index.str.contains('shipping-H2 \(retrofitted\)') & p_nom_extendable"
    ).index
    h2_terminal_retro_fix_i = n.generators.query(
            "index.str.contains('shipping-H2 \(retrofitted\)') & ~p_nom_extendable"
        ).index
    # find locations where import gas terminals can be retrofitted to H2 pipelines
    clusters_for_retrofit = (natural_gas_terminal_i.str[:5].intersection(h2_terminal_retro_ext_i.str[:5])
                             .intersection(h2_terminal_retro_fix_i.str[:5]))
    # filter indexes of terminals for locations where retrofitting can take place
    filtered_natural_gas_terminal_i = pd.Index([x for x in natural_gas_terminal_i if x[:5] in clusters_for_retrofit])
    filtered_h2_terminal_retro_ext_i = pd.Index([x for x in h2_terminal_retro_ext_i if x[:5] in clusters_for_retrofit])
    filtered_h2_terminal_retro_fix_i = pd.Index([x for x in h2_terminal_retro_fix_i if x[:5] in clusters_for_retrofit])

    # extract the capacity that the lng terminals had before the last retrofitting step
    full_capacity_terminals = n.generators.loc[filtered_natural_gas_terminal_i, 'p_nom_max']
    # extract the capacity of the terminals that where retrofitted in the previous planning year
    retrofitted_capacity_terminal = n.generators.loc[filtered_h2_terminal_retro_fix_i, 'p_nom']
    # get the capacity that the terminals can have when it is fully used
    max_capacity_retrofit_terminal = n.generators.loc[filtered_h2_terminal_retro_ext_i, 'p_nom_max']
    # calculate what is left as lng terminal after the previous retrofitting step
    remaining_capacity_terminal = (full_capacity_terminals - retrofitted_capacity_terminal
                                   .rename(lambda x: x[:5] + ' import lng gas').groupby(level=0).sum())
    # set the maximum capacity of the gas terminals to what is left after retrofitting
    n.generators.loc[filtered_natural_gas_terminal_i, 'p_nom_max'] = remaining_capacity_terminal
    # calculate the capacity that is still left for retrofitting
    remaining_capacity_terminal_retro = (max_capacity_retrofit_terminal
                                         - retrofitted_capacity_terminal.rename(lambda x: x[:-4] + str(year))
                                         .groupby(level=0).sum())
    # set the capacity for optional retrofitting left from the previous year as the new maximum
    n.generators.loc[filtered_h2_terminal_retro_ext_i, 'p_nom_max'] = remaining_capacity_terminal_retro

    # lower capacity built out potential if new H2 terminal have been built in previous year
    h2_terminal_new_ext_i = n.generators.query(
        "index.str.contains('shipping-H2 \(new\)') & p_nom_extendable"
    ).index
    h2_terminal_new_fix_i = n.generators.query(
        "index.str.contains('shipping-H2 \(new\)') & ~p_nom_extendable"
    ).index
    if not h2_terminal_new_fix_i.empty:
        # find the exogenous maximum capacity for newly built H2 terminals
        full_capacity_new_terminals = n.generators.loc[h2_terminal_new_ext_i, 'p_nom_max']
        # sum up all capacities of the terminals that where already built in previous years
        existing_capacity_new_terminals = (n.generators.loc[h2_terminal_new_fix_i, 'p_nom']
                                           .rename(lambda x: x[:-4] + str(year)).groupby(level=0).sum())
        # define remaining capacity potential as new maximum for the extendable H2 terminals
        maximum_capacity_new_terminals = full_capacity_new_terminals.sub(existing_capacity_new_terminals, fill_value=0)
        n.generators.loc[h2_terminal_new_ext_i, 'p_nom_max'] = maximum_capacity_new_terminals

    # clean up all components that now have a maximum capacity of zero and therefore cannot be extended
    to_remove = n.generators.query('p_nom_extendable & p_nom_max<1e-3').index
    n.mremove("Generator", to_remove)
def ends_with_year(s):
    return bool(re.search('-\d{4}$', s))
def disable_grid_expansion_if_LV_limit_hit(n):
    if "lv_limit" not in n.global_constraints.index:
        return

    total_expansion = (
        n.lines.eval("s_nom_min * length").sum()
        + n.links.query("carrier == 'DC'").eval("p_nom_min * length").sum()
    ).sum()

    lv_limit = n.global_constraints.at["lv_limit", "constant"]

    # allow small numerical differences
    if lv_limit - total_expansion < 1:
        logger.info("LV is already reached, disabling expansion and LV limit")
        extendable_acs = n.lines.query("s_nom_extendable").index
        n.lines.loc[extendable_acs, "s_nom_extendable"] = False
        n.lines.loc[extendable_acs, "s_nom"] = n.lines.loc[extendable_acs, "s_nom_min"]

        extendable_dcs = n.links.query("carrier == 'DC' and p_nom_extendable").index
        n.links.loc[extendable_dcs, "p_nom_extendable"] = False
        n.links.loc[extendable_dcs, "p_nom"] = n.links.loc[extendable_dcs, "p_nom_min"]

        n.global_constraints.drop("lv_limit", inplace=True)


def adjust_renewable_profiles(n, input_profiles, params, year):
    """
    Adjusts renewable profiles according to the renewable technology specified,
    using the latest year below or equal to the selected year.
    """

    # spatial clustering
    cluster_busmap = pd.read_csv(snakemake.input.cluster_busmap, index_col=0).squeeze()
    simplify_busmap = pd.read_csv(
        snakemake.input.simplify_busmap, index_col=0
    ).squeeze()
    clustermaps = simplify_busmap.map(cluster_busmap)
    clustermaps.index = clustermaps.index.astype(str)

    # temporal clustering
    dr = pd.date_range(**params["snapshots"], freq="h")
    snapshotmaps = (
        pd.Series(dr, index=dr).where(lambda x: x.isin(n.snapshots), pd.NA).ffill()
    )

    for carrier in params["carriers"]:
        if carrier == "hydro":
            continue
        with xr.open_dataset(getattr(input_profiles, "profile_" + carrier)) as ds:
            if ds.indexes["bus"].empty or "year" not in ds.indexes:
                continue

            closest_year = max(
                (y for y in ds.year.values if y <= year), default=min(ds.year.values)
            )

            p_max_pu = (
                ds["profile"]
                .sel(year=closest_year)
                .transpose("time", "bus")
                .to_pandas()
            )

            # spatial clustering
            weight = ds["weight"].sel(year=closest_year).to_pandas()
            weight = weight.groupby(clustermaps).transform(normed_or_uniform)
            p_max_pu = (p_max_pu * weight).T.groupby(clustermaps).sum().T
            p_max_pu.columns = p_max_pu.columns + f" {carrier}"

            # temporal_clustering
            p_max_pu = p_max_pu.groupby(snapshotmaps).mean()

            # replace renewable time series
            n.generators_t.p_max_pu.loc[:, p_max_pu.columns] = p_max_pu


def extract_base_year_capacities(n_old):
    """
    For the expansion of the national electricity grids relative to the base year (i.e. 2020), the knowledge of the
    capacities in this base year is needed. Here, national lines and links are summed up and written into csv file for
    later use.
    Parameters
    ----------
    n_old : pypsa.Network
        optimized network from the first optimization year
    """
    # filter for the lines and links that do not cross a border
    national_links = n_old.links[(n_old.links.carrier == "DC")
                                 & (n_old.links.bus0.str[:2] == n_old.links.bus1.str[:2])
                                 & ~(n_old.links.index.str.contains('reversed'))]
    national_lines = n_old.lines[(n_old.lines.bus0.str[:2] == n_old.lines.bus1.str[:2])]
    # sum up the nominal link capacities by country
    grouper_links = national_links.bus0.map(n_old.buses.country)
    p_nom_per_country = national_links.groupby(grouper_links).p_nom_opt.sum()
    # calculate the line capacity that can be actually used
    s_nom_real_per_cluster = national_lines.s_nom_opt * national_lines.s_max_pu
    # group the line capacities by country
    grouper_lines = national_lines.bus0.map(n_old.buses.country)
    s_nom_real_per_country = s_nom_real_per_cluster.groupby(grouper_lines).sum()
    # calculate total installed capacity
    capacity_per_country = s_nom_real_per_country.add(p_nom_per_country, fill_value=0).rename_axis(index='country')
    # save national transmission capacities from the base year to csv file in the results folder
    resultdir = Path(snakemake.input.network_p.split('postnetworks')[0]) / 'base_year_capacities'
    if not os.path.exists(resultdir):
        os.mkdir(resultdir)
    filename_base_year_capacities = resultdir / f"elec_s{snakemake.wildcards.simpl}_{snakemake.wildcards.clusters}_l{snakemake.wildcards.ll}_{snakemake.wildcards.opts}_{snakemake.wildcards.sector_opts}_{snakemake.config['scenario']['planning_horizons'][0]}_base_year_capacities.csv"
    capacity_per_country.to_csv(filename_base_year_capacities, header=['capacity'])

if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake(
            "add_brownfield",
            configfile=r"...",    # add path to custom config
            planning_horizons=2030,
        )

    logging.basicConfig(level=snakemake.config["logging"]["level"])

    update_config_with_sector_opts(snakemake.config, snakemake.wildcards.sector_opts)

    logger.info(f"Preparing brownfield from the file {snakemake.input.network_p}")

    year = int(snakemake.wildcards.planning_horizons)

    n = pypsa.Network(snakemake.input.network)

    adjust_renewable_profiles(n, snakemake.input, snakemake.params, year)

    add_build_year_to_new_assets(n, year)

    n_p = pypsa.Network(snakemake.input.network_p)

    # if the calculation involves the second year in the planning horizons, the national transmission capacities can be
    # evaluated for the base year
    if year == snakemake.config["scenario"]["planning_horizons"][1]:
        extract_base_year_capacities(n_p)

    add_brownfield(n, n_p, year)

    disable_grid_expansion_if_LV_limit_hit(n)


    n.meta = dict(snakemake.config, **dict(wildcards=dict(snakemake.wildcards)))
    n.export_to_netcdf(snakemake.output[0])
