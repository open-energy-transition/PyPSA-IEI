# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2017-2024 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT
"""
Solves optimal operation and capacity for a network with the option to
iteratively optimize while updating line reactances.

This script is used for optimizing the electrical network as well as the
sector coupled network.

Description
-----------

Total annual system costs are minimised with PyPSA. The full formulation of the
linear optimal power flow (plus investment planning
is provided in the
`documentation of PyPSA <https://pypsa.readthedocs.io/en/latest/optimal_power_flow.html#linear-optimal-power-flow>`_.

The optimization is based on the :func:`network.optimize` function.
Additionally, some extra constraints specified in :mod:`solve_network` are added.

.. note::

    The rules ``solve_elec_networks`` and ``solve_sector_networks`` run
    the workflow for all scenarios in the configuration file (``scenario:``)
    based on the rule :mod:`solve_network`.
"""
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import xarray as xr
from _benchmark import memory_logger
from _helpers import configure_logging, get_opt, update_config_with_sector_opts
from pypsa.descriptors import get_activity_mask
from pypsa.descriptors import get_switchable_as_dense as get_as_dense

logger = logging.getLogger(__name__)
pypsa.pf.logger.setLevel(logging.WARNING)


def add_land_use_constraint(n, planning_horizons, config):
    if "m" in snakemake.wildcards.clusters:
        _add_land_use_constraint_m(n, planning_horizons, config)
    else:
        _add_land_use_constraint(n)


def add_land_use_constraint_perfect(n):
    """
    Add global constraints for tech capacity limit.
    """
    logger.info("Add land-use constraint for perfect foresight")

    def compress_series(s):
        def process_group(group):
            if group.nunique() == 1:
                return pd.Series(group.iloc[0], index=[None])
            else:
                return group

        return s.groupby(level=[0, 1]).apply(process_group)

    def new_index_name(t):
        # Convert all elements to string and filter out None values
        parts = [str(x) for x in t if x is not None]
        # Join with space, but use a dash for the last item if not None
        return " ".join(parts[:2]) + (f"-{parts[-1]}" if len(parts) > 2 else "")

    def check_p_min_p_max(p_nom_max):
        p_nom_min = n.generators[ext_i].groupby(grouper).sum().p_nom_min
        p_nom_min = p_nom_min.reindex(p_nom_max.index)
        check = (
                p_nom_min.groupby(level=[0, 1]).sum()
                > p_nom_max.groupby(level=[0, 1]).min()
        )
        if check.sum():
            logger.warning(
                f"summed p_min_pu values at node larger than technical potential {check[check].index}"
            )

    grouper = [n.generators.carrier, n.generators.bus, n.generators.build_year]
    ext_i = n.generators.p_nom_extendable
    # get technical limit per node and investment period
    p_nom_max = n.generators[ext_i].groupby(grouper).min().p_nom_max
    # drop carriers without tech limit
    p_nom_max = p_nom_max[~p_nom_max.isin([np.inf, np.nan])]
    # carrier
    carriers = p_nom_max.index.get_level_values(0).unique()
    gen_i = n.generators[(n.generators.carrier.isin(carriers)) & (ext_i)].index
    n.generators.loc[gen_i, "p_nom_min"] = 0
    # check minimum capacities
    check_p_min_p_max(p_nom_max)
    # drop multi entries in case p_nom_max stays constant in different periods
    # p_nom_max = compress_series(p_nom_max)
    # adjust name to fit syntax of nominal constraint per bus
    df = p_nom_max.reset_index()
    df["name"] = df.apply(
        lambda row: f"nom_max_{row['carrier']}"
                    + (f"_{row['build_year']}" if row["build_year"] is not None else ""),
        axis=1,
    )

    for name in df.name.unique():
        df_carrier = df[df.name == name]
        bus = df_carrier.bus
        n.buses.loc[bus, name] = df_carrier.p_nom_max.values

    return n


def _add_land_use_constraint(n):
    # warning: this will miss existing offwind which is not classed AC-DC and has carrier 'offwind'

    for carrier in ["solar", "onwind", "offwind-ac", "offwind-dc"]:
        extendable_i = (n.generators.carrier == carrier) & n.generators.p_nom_extendable
        n.generators.loc[extendable_i, "p_nom_min"] = 0

        ext_i = (n.generators.carrier == carrier) & ~n.generators.p_nom_extendable
        existing = (
            n.generators.loc[ext_i, "p_nom"]
            .groupby(n.generators.bus.map(n.buses.location))
            .sum()
        )
        existing.index += " " + carrier + "-" + snakemake.wildcards.planning_horizons
        n.generators.loc[existing.index, "p_nom_max"] -= existing

    # check if existing capacities are larger than technical potential
    existing_large = n.generators[
        n.generators["p_nom_min"] > n.generators["p_nom_max"]
        ].index
    if len(existing_large):
        logger.warning(
            f"Existing capacities larger than technical potential for {existing_large},\
                        adjust technical potential to existing capacities"
        )
        n.generators.loc[existing_large, "p_nom_max"] = n.generators.loc[
            existing_large, "p_nom_min"
        ]

    n.generators.p_nom_max.clip(lower=0, inplace=True)


def _add_land_use_constraint_m(n, planning_horizons, config):
    # if generators clustering is lower than network clustering, land_use accounting is at generators clusters

    grouping_years = config["existing_capacities"]["grouping_years"]
    current_horizon = snakemake.wildcards.planning_horizons

    for carrier in ["solar", "onwind", "offwind-ac", "offwind-dc"]:
        existing = n.generators.loc[n.generators.carrier == carrier, "p_nom"]
        ind = list(
            {i.split(sep=" ")[0] + " " + i.split(sep=" ")[1] for i in existing.index}
        )

        previous_years = [
            str(y)
            for y in planning_horizons + grouping_years
            if y < int(snakemake.wildcards.planning_horizons)
        ]

        for p_year in previous_years:
            ind2 = [
                i for i in ind if i + " " + carrier + "-" + p_year in existing.index
            ]
            sel_current = [i + " " + carrier + "-" + current_horizon for i in ind2]
            sel_p_year = [i + " " + carrier + "-" + p_year for i in ind2]
            n.generators.loc[sel_current, "p_nom_max"] -= existing.loc[
                sel_p_year
            ].rename(lambda x: x[:-4] + current_horizon)

    n.generators.p_nom_max.clip(lower=0, inplace=True)


def add_co2_sequestration_limit(n, config, limit=200):
    """
    Add a global constraint on the amount of Mt CO2 that can be sequestered.
    """
    limit = limit * 1e6
    for o in opts:
        if "seq" not in o:
            continue
        limit = float(o[o.find("seq") + 3:]) * 1e6
        break

    if not n.investment_periods.empty:
        periods = n.investment_periods
        names = pd.Index([f"co2_sequestration_limit-{period}" for period in periods])
    else:
        periods = [np.nan]
        names = pd.Index(["co2_sequestration_limit"])

    n.madd(
        "GlobalConstraint",
        names,
        sense=">=",
        constant=-limit,
        type="operational_limit",
        carrier_attribute="co2 sequestered",
        investment_period=periods,
    )


def add_carbon_constraint(n, snapshots):
    glcs = n.global_constraints.query('type == "co2_atmosphere"')
    if glcs.empty:
        return
    for name, glc in glcs.iterrows():
        carattr = glc.carrier_attribute
        emissions = n.carriers.query(f"{carattr} != 0")[carattr]

        if emissions.empty:
            continue

        # stores
        n.stores["carrier"] = n.stores.bus.map(n.buses.carrier)
        stores = n.stores.query("carrier in @emissions.index and not e_cyclic")
        if not stores.empty:
            last = n.snapshot_weightings.reset_index().groupby("period").last()
            last_i = last.set_index([last.index, last.timestep]).index
            final_e = n.model["Store-e"].loc[last_i, stores.index]
            time_valid = int(glc.loc["investment_period"])
            time_i = pd.IndexSlice[time_valid, :]
            lhs = final_e.loc[time_i, :] - final_e.shift(snapshot=1).loc[time_i, :]

            rhs = glc.constant
            n.model.add_constraints(lhs <= rhs, name=f"GlobalConstraint-{name}")


def add_carbon_budget_constraint(n, snapshots):
    glcs = n.global_constraints.query('type == "Co2Budget"')
    if glcs.empty:
        return
    for name, glc in glcs.iterrows():
        carattr = glc.carrier_attribute
        emissions = n.carriers.query(f"{carattr} != 0")[carattr]

        if emissions.empty:
            continue

        # stores
        n.stores["carrier"] = n.stores.bus.map(n.buses.carrier)
        stores = n.stores.query("carrier in @emissions.index and not e_cyclic")
        if not stores.empty:
            last = n.snapshot_weightings.reset_index().groupby("period").last()
            last_i = last.set_index([last.index, last.timestep]).index
            final_e = n.model["Store-e"].loc[last_i, stores.index]
            time_valid = int(glc.loc["investment_period"])
            time_i = pd.IndexSlice[time_valid, :]
            weighting = n.investment_period_weightings.loc[time_valid, "years"]
            lhs = final_e.loc[time_i, :] * weighting

            rhs = glc.constant
            n.model.add_constraints(lhs <= rhs, name=f"GlobalConstraint-{name}")


def add_max_growth(n, config):
    """
    Add maximum growth rates for different carriers.
    """

    opts = snakemake.params["sector"]["limit_max_growth"]
    # take maximum yearly difference between investment periods since historic growth is per year
    factor = n.investment_period_weightings.years.max() * opts["factor"]
    for carrier in opts["max_growth"].keys():
        max_per_period = opts["max_growth"][carrier] * factor
        logger.info(
            f"set maximum growth rate per investment period of {carrier} to {max_per_period} GW."
        )
        n.carriers.loc[carrier, "max_growth"] = max_per_period * 1e3

    for carrier in opts["max_relative_growth"].keys():
        max_r_per_period = opts["max_relative_growth"][carrier]
        logger.info(
            f"set maximum relative growth per investment period of {carrier} to {max_r_per_period}."
        )
        n.carriers.loc[carrier, "max_relative_growth"] = max_r_per_period

    return n


def add_retrofit_gas_boiler_constraint(n, snapshots):
    """
    Allow retrofitting of existing gas boilers to H2 boilers.
    """
    c = "Link"
    logger.info("Add constraint for retrofitting gas boilers to H2 boilers.")
    # existing gas boilers
    mask = n.links.carrier.str.contains("gas boiler") & ~n.links.p_nom_extendable
    gas_i = n.links[mask].index
    mask = n.links.carrier.str.contains("retrofitted H2 boiler")
    h2_i = n.links[mask].index

    n.links.loc[gas_i, "p_nom_extendable"] = True
    p_nom = n.links.loc[gas_i, "p_nom"]
    n.links.loc[gas_i, "p_nom"] = 0

    # heat profile
    cols = n.loads_t.p_set.columns[
        n.loads_t.p_set.columns.str.contains("heat")
        & ~n.loads_t.p_set.columns.str.contains("industry")
        & ~n.loads_t.p_set.columns.str.contains("agriculture")
        ]
    profile = n.loads_t.p_set[cols].div(
        n.loads_t.p_set[cols].groupby(level=0).max(), level=0
    )
    # to deal if max value is zero
    profile.fillna(0, inplace=True)
    profile.rename(columns=n.loads.bus.to_dict(), inplace=True)
    profile = profile.reindex(columns=n.links.loc[gas_i, "bus1"])
    profile.columns = gas_i

    rhs = profile.mul(p_nom)

    dispatch = n.model["Link-p"]
    active = get_activity_mask(n, c, snapshots, gas_i)
    rhs = rhs[active]
    p_gas = dispatch.sel(Link=gas_i)
    p_h2 = dispatch.sel(Link=h2_i)

    lhs = p_gas + p_h2

    n.model.add_constraints(lhs == rhs, name="gas_retrofit")


def prepare_network(
        n,
        solve_opts=None,
        config=None,
        foresight=None,
        planning_horizons=None,
        co2_sequestration_potential=None,
):
    if "clip_p_max_pu" in solve_opts:
        for df in (
                n.generators_t.p_max_pu,
                n.generators_t.p_min_pu,
                n.links_t.p_max_pu,
                n.links_t.p_min_pu,
                n.storage_units_t.inflow,
        ):
            df.where(df > solve_opts["clip_p_max_pu"], other=0.0, inplace=True)

    if load_shedding := solve_opts.get("load_shedding"):
        # intersect between macroeconomic and surveybased willingness to pay
        # http://journal.frontiersin.org/article/10.3389/fenrg.2015.00055/full
        # TODO: retrieve color and nice name from config
        n.add("Carrier", "load", color="#dd2e23", nice_name="Load shedding")
        buses_i = n.buses.index
        if not np.isscalar(load_shedding):
            # TODO: do not scale via sign attribute (use Eur/MWh instead of Eur/kWh)
            load_shedding = 1e2  # Eur/kWh

        n.madd(
            "Generator",
            buses_i,
            " load",
            bus=buses_i,
            carrier="load",
            sign=1e-3,  # Adjust sign to measure p and p_nom in kW instead of MW
            marginal_cost=load_shedding,  # Eur/kWh
            p_nom=1e9,  # kW
        )

    if solve_opts.get("curtailment_mode"):
        n.add("Carrier", "curtailment", color="#fedfed", nice_name="Curtailment")
        n.generators_t.p_min_pu = n.generators_t.p_max_pu
        buses_i = n.buses.query("carrier == 'AC'").index
        n.madd(
            "Generator",
            buses_i,
            suffix=" curtailment",
            bus=buses_i,
            p_min_pu=-1,
            p_max_pu=0,
            marginal_cost=-0.1,
            carrier="curtailment",
            p_nom=1e6,
        )

    if solve_opts.get("noisy_costs"):
        for t in n.iterate_components():
            # if 'capital_cost' in t.df:
            #    t.df['capital_cost'] += 1e1 + 2.*(np.random.random(len(t.df)) - 0.5)
            if "marginal_cost" in t.df:
                t.df["marginal_cost"] += 1e-2 + 2e-3 * (
                        np.random.random(len(t.df)) - 0.5
                )

        for t in n.iterate_components(["Line", "Link"]):
            t.df["capital_cost"] += (
                                            1e-1 + 2e-2 * (np.random.random(len(t.df)) - 0.5)
                                    ) * t.df["length"]

    if solve_opts.get("nhours"):
        nhours = solve_opts["nhours"]
        n.set_snapshots(n.snapshots[:nhours])
        n.snapshot_weightings[:] = 8760.0 / nhours

    if foresight == "myopic":
        add_land_use_constraint(n, planning_horizons, config)

    if foresight == "perfect":
        n = add_land_use_constraint_perfect(n)
        if snakemake.params["sector"]["limit_max_growth"]["enable"]:
            n = add_max_growth(n, config)

    if n.stores.carrier.eq("co2 sequestered").any():
        limit = co2_sequestration_potential
        add_co2_sequestration_limit(n, config, limit=limit)

    return n


def add_country_carrier_limit_constraints(n, config):
    """
    Add country & carrier limit constraint to the network.

    Add minimum and maximum levels of generator nominal capacity per carrier
    for individual countries. Opts and path for agg_p_nom_minmax.csv must be defined
    in config.yaml. Default file is available at data/agg_p_nom_minmax.csv.

    Parameters
    ----------
    n : pypsa.Network
    config : dict

    """

    # load custom constraints
    agg_p_nom_minmax = pd.read_csv(
        config["policy_plans"]["agg_p_nom_limits"], index_col=[0, 1]
    )
    # filter out the current planning year
    current_year = snakemake.wildcards.planning_horizons
    agg_p_nom_minmax = agg_p_nom_minmax.query(f'year=={current_year}')
    logger.info("Adding generation capacity constraints per carrier and country")

    # all solar technologies should be grouped together, so the carrier needs to be changed. same for offwind.
    carrier_map = {'solar rooftop': 'solar',
                   'offwind-ac': 'offwind',
                   'offwind-dc': 'offwind',
                   'residential rural micro gas CHP': 'gas for electricity',
                   'services rural micro gas CHP': 'gas for electricity',
                   'residential urban decentral micro gas CHP': 'gas for electricity',
                   'services urban decentral micro gas CHP': 'gas for electricity',
                   'urban central gas CHP': 'gas for electricity',
                   'urban central gas CHP CC': 'gas for electricity',
                   'OCGT': 'gas for electricity',
                   'CCGT': 'gas for electricity',
                   'allam': 'gas for electricity'
                   }

    for cc, component in zip(n.iterate_components(['Store', 'Generator', 'Link']), ['Store', "Generator", 'Link']):
        # add a column containing the country to the component dataframe
        base_bus = pd.Series(cc.df.index.str[:5], index=cc.df.index, name='country')
        component_bus = base_bus.map(n.buses.country)
        cc = cc.df.drop('country', axis=1, errors='ignore').merge(component_bus, how='left', left_index=True,
                                                                  right_index=True)
        # rename the carrier for offind and solar technologies
        cc.carrier = cc.carrier.replace(carrier_map)

        if component == 'Store':
            # extract all extendable carriers
            e_nom = n.model[component + "-e_nom"]
            cc_ext = cc.query("e_nom_extendable").rename_axis(index=component + "-ext")

            # create a similar dataframe, where all components belong to the country 'Eur' to be able to group them
            # together.
            cc_ext_Eur = cc_ext.copy()
            cc_ext_Eur['country'] = 'Eur'

            # create left-hand side for the country-specific and European constraints
            lhs = (e_nom.groupby(cc_ext.loc[:, ['country', 'carrier']]).sum()
                   + e_nom.groupby(cc_ext_Eur.loc[:, ['country', 'carrier']]).sum())

            # filter for all the non-extendable carriers
            cc_old = cc.query("~e_nom_extendable").rename_axis(index=component + "-old")
            cc_old_Eur = cc_old.copy()
            cc_old_Eur['country'] = 'Eur'

            # sum up all the capacities that exist before the current planning year
            old_capas = pd.concat([cc_old.groupby(['country', 'carrier']).e_nom.sum(),
                                   cc_old_Eur.groupby(['country', 'carrier']).e_nom.sum()])
        else:
            # extract all extendable carriers
            p_nom = n.model[component + "-p_nom"]
            if component == "Link":
                # for links, multiply the efficiency to get the capacity of bus1, which is often the electricity bus
                p_nom = p_nom * n.links.query('p_nom_extendable').efficiency.rename_axis("Link-ext")
            cc_ext = cc.query("p_nom_extendable").rename_axis(index=component + "-ext")

            # create a similar dataframe, where all components belong to the country 'Eur' to be able to group them
            # together.
            cc_ext_Eur = cc_ext.copy()
            cc_ext_Eur['country'] = 'Eur'

            # create left-hand side for the country-specific and European constraints
            lhs = (p_nom.groupby(cc_ext.loc[:, ['country', 'carrier']]).sum()
                   + p_nom.groupby(cc_ext_Eur.loc[:, ['country', 'carrier']]).sum())

            # filter for all the non-extendable carriers
            cc_old = cc.query("~p_nom_extendable").rename_axis(index=component + "-old")
            cc_old_Eur = cc_old.copy()
            cc_old_Eur['country'] = 'Eur'

            # sum up all the capacities that exist before the current planning year
            old_capas = pd.concat([cc_old.groupby(['country', 'carrier']).p_nom.sum(),
                                   cc_old_Eur.groupby(['country', 'carrier']).p_nom.sum()])

        # filter the custom constraints for the current component
        agg_p_nom_minmax_for_component = agg_p_nom_minmax[agg_p_nom_minmax['component'] == component.lower()]
        minimum = xr.DataArray(agg_p_nom_minmax_for_component["min"].dropna()).rename(dim_0="group")

        # subtract old capacities from the custom constraint to get the minimum capacity expansion
        old_idx = minimum.indexes['group'].intersection(old_capas.index)
        minimum.loc[old_idx] = minimum.loc[old_idx] - old_capas.loc[old_idx]
        minimum = minimum.where(minimum >= 0, 0)

        # create the constraint for the countries and carriers that appear both in the input data and in the network
        index = minimum.indexes["group"].intersection(lhs.indexes["group"])
        if not index.empty:
            name = "agg_e_nom_min_" if component == 'Store' else 'agg_p_nom_min_'
            n.model.add_constraints(
                lhs.sel(group=index) >= minimum.loc[index], name=name + component
            )

        # filter the custom constraints for the current component
        maximum = xr.DataArray(agg_p_nom_minmax_for_component["max"].dropna()).rename(dim_0="group")

        # subtract old capacities from the custom constraint to get the maximum capacity expansion
        old_idx = maximum.indexes['group'].intersection(old_capas.index)
        maximum.loc[old_idx] = maximum.loc[old_idx] - old_capas.loc[old_idx]
        maximum = maximum.where(maximum >= 0, 0)

        # create the constraint for the countries and carriers that appear both in the input data and in the network
        index = maximum.indexes["group"].intersection(lhs.indexes["group"])
        if not index.empty:
            name = "agg_e_nom_max_" if component == 'Store' else 'agg_p_nom_max_'
            n.model.add_constraints(
                lhs.sel(group=index) <= maximum.loc[index], name=name + component
            )

def add_national_grid_plan_constraints(n, config):
    """
    Limit the expansion of the national electricity transmission lines to a factor compared to first year of the
    planning_horizons (e.g., 2020) given by the Ember study (https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fember-climate.org%2Fapp%2Fuploads%2F2024%2F03%2FEmber-Transmission-Grids-Data.xlsx&wdOrigin=BROWSELINK)


    Parameters
    ----------
    n : pypsa.Network
    config : dict
    """

    # filter the network for lines and links that connect clusters of the same country
    national_links = n.links[(n.links.carrier == "DC") & (n.links.bus0.str[:2] == n.links.bus1.str[:2])]
    national_lines = n.lines[(n.lines.bus0.str[:2] == n.lines.bus1.str[:2])]

    # load expansion factors given by custom input file
    national_grid_plans = pd.read_csv(config["policy_plans"]["include_national_grid_plans"]["national_grid_plan_data"], index_col=[0])

    ### extract most recent constraints for each country in the given year
    # extract the current and previous planning year
    current_year = int(snakemake.wildcards.planning_horizons)
    all_years = snakemake.params.planning_horizons
    previous_year = all_years[all_years.index(current_year) - 1]
    countries = []
    most_recent_factors = []
    # check input for each country separately
    for country, row in national_grid_plans.iterrows():
        # find years, for which an input value exists
        existing_years = row.dropna().index
        # extract years with input that lie within the timespan between the previous and the current optimization year
        years_in_timeframe = [int(x) for x in existing_years if (int(x) > previous_year) & (int(x) <= current_year)]
        # if there is no input data fulfilling this criterion, continue to the next row
        if len(years_in_timeframe) == 0:
            continue
        # find the most recent year with input data within the timespan of interest
        most_recent_year = max(years_in_timeframe)
        # add the factor from the input data to the list of factors and also add the corresponding country
        most_recent_factors = most_recent_factors + [row[str(most_recent_year)]]
        countries = countries + [country]

    # In the following, we will distinguish between cases depending on the most_recent_factors.
    # In case 1), most_recent_factors is empty, i.e.the file 'national_line_expansions.cvs' does not contain any
    # relevant specifications for the model configuration. This is the case, for example, if no specifications have been
    # made for the countries or for suitable years.
    # In case 1, we distinguish between 3 sub-cases:
    # 1A) The year is before the relevant data(e.g., 2023 if we have data only from 2026 and later),
    # then all (except for tyndp relevant components) are set expandable = false.
    # 1B) The year is the first of the planning_horizons (e.g., 2020): All is set to expandable = true.
    # 1C) The year is after the relevant data in most_recent_factors(e.g., 2060 if we have data until 2050): All is set
    # to expandable = open_for_optimization(true / false after certain year - as configured by user)
    # In case 2) there is relevant data and this is then used accordingly to build the constraints.

    # Case 1: handle all eventualities where there is no input data for the current optimization year
    if len(most_recent_factors) == 0:
        # extract the first year for which input data is given
        first_data_year = int(min(national_grid_plans.columns))
        # handle the case when this is not the first optimization year, but it is too early for any of the input data
        # from the csv file to apply to this year
        if (first_data_year > current_year) & (current_year != all_years[0]):
            # Case 1A: find all the lines and links that should not be extended in this year. This includes all the
            # national components that have not already been set by the TYNDP (those fulfill min=max)
            idx_links_not_extendable = national_links.query('p_nom_min!=p_nom_max').index
            idx_lines_not_extendable = national_lines.query('s_nom_min!=s_nom_max').index
            # set all links except just-built TYNDP links to not extendable
            n.links.loc[idx_links_not_extendable, 'p_nom_extendable'] = False
            n.links.loc[idx_links_not_extendable, 'p_nom'] = n.links.loc[idx_links_not_extendable, 'p_nom_min']
            # set all lines except just-built TYNDP lines to not extendable
            n.lines.loc[idx_lines_not_extendable, 's_nom_extendable'] = False
            n.lines.loc[idx_lines_not_extendable, 's_nom'] = n.lines.loc[idx_lines_not_extendable, 's_nom_min']
        elif current_year == all_years[0]:
            # Case 1B: handle the case where the current optimization year is the first one

            # allow extension of national lines and links by setting them to extendable
            n.links.loc[national_links.index, 'p_nom_extendable'] = True
            n.lines.loc[national_lines.index, 's_nom_extendable'] = True
        else:
            # Case 1C: possibly one of the later optimization years

            # open_for_optimization can be true or a year. In case of true, the following if clauses are skipped and all lines
            # and links are set as extendable later in the code. In case of a year, optimization of the lines and links is
            # allowed after this year.
            open_for_optimization = config['policy_plans']['include_national_grid_plans']['optimize_after']
            if (type(open_for_optimization) == int) & (current_year > open_for_optimization):
                open_for_optimization = True
            elif (type(open_for_optimization) == int) & (current_year <= open_for_optimization):
                open_for_optimization = False
            # find all components that were not already defined by TYNDP (those fulfill min=max)
            idx_links_not_extendable = national_links.query('p_nom_min!=p_nom_max').index
            idx_lines_not_extendable = national_lines.query('s_nom_min!=s_nom_max').index
            # set these lines and links to the choice from the config
            n.links.loc[idx_links_not_extendable, 'p_nom_extendable'] = open_for_optimization
            n.lines.loc[idx_lines_not_extendable, 's_nom_extendable'] = open_for_optimization
            if not open_for_optimization:
                # when they are not extended, p_nom needs to be set to consider any previously built capacity
                n.links.loc[idx_links_not_extendable, 'p_nom'] = n.links.loc[idx_links_not_extendable, 'p_nom_min']
                n.lines.loc[idx_lines_not_extendable, 's_nom'] = n.lines.loc[idx_lines_not_extendable, 's_nom_min']

    else:
        # Case 2: handle the case when there is input data for the current time window

        # put the factors for the current optimization year into pandas Series
        most_recent_grid_plan = pd.Series(most_recent_factors, index=countries)
        # load national transmission capacities from the first optimization year
        resultdir = Path(snakemake.input.network.split('prenetworks-final')[0])
        filename_base_year_capacities = (resultdir /
                                             f"base_year_capacities/elec_s{snakemake.wildcards.simpl}_"
                                             f"{snakemake.wildcards.clusters}_l{snakemake.wildcards.ll}_"
                                             f"{snakemake.wildcards.opts}_{snakemake.wildcards.sector_opts}_"
                                             f"{config['scenario']['planning_horizons'][0]}_base_year_capacities.csv")
        existing_capacities = pd.read_csv(filename_base_year_capacities, index_col=[0])
        # remove all reveresed links to avoid the links counting double
        national_links = national_links[~(national_links.index.str.contains('reversed'))]
        # devide the lines and links into extendable and non-extendable components
        national_links_ext = national_links.query('p_nom_extendable')
        national_links_fix = national_links.query('~p_nom_extendable')
        national_lines_ext = national_lines.query('s_nom_extendable')
        national_lines_fix = national_lines.query('~s_nom_extendable')

        ### find the expansion factor that is already given by the min values prior to this constraint
        # calculate the p_nom_min per country
        grouper_links = national_links.bus0.map(n.buses.country)
        minimum_links = national_links.groupby(grouper_links).p_nom_min.sum()
        # calculate the s_nom_min that is actually usable
        s_nom_min_real = national_lines.s_nom_min * national_lines.s_max_pu
        # calculate the s_nom_min per country
        grouper_lines = national_lines.bus0.map(n.buses.country)
        minimum_lines = s_nom_min_real.groupby(grouper_lines).sum()
        # calculate the minimum capacity expansion compared to the base year
        minimum_capacity = minimum_lines.add(minimum_links, fill_value=0)
        minimum_factor = minimum_capacity / existing_capacities.loc[:, 'capacity']
        # find countries, where the minimum expansion exceeds the exogenously given factor and replace it with the
        # minimum factors
        index = minimum_factor.index.intersection(most_recent_grid_plan.index)
        to_change = most_recent_grid_plan.loc[index][minimum_factor.loc[index] > most_recent_grid_plan.loc[index]].index
        most_recent_grid_plan[to_change] = minimum_factor.loc[to_change]
        # find countries that are not defined in exogenous input and set them to minimum value
        to_set = minimum_factor.index.difference(index)
        most_recent_grid_plan = pd.concat([most_recent_grid_plan,minimum_factor[to_set]])

        ### define left-hand side of constraint
        # extract variables from model
        p_nom_per_cluster_ext = n.model['Link-p_nom'].sel({'Link-ext': national_links_ext.index})
        s_nom_per_cluster_ext = n.model['Line-s_nom'].sel({'Line-ext': national_lines_ext.index})
        # calculate s_nom that can be actually used
        s_nom_real_per_cluster_ext = s_nom_per_cluster_ext * national_lines_ext.s_max_pu.rename_axis(index='Line-ext')
        # sum up all p_nom for each country
        grouper_links_ext = national_links_ext.bus0.map(n.buses.country).rename_axis(index='Link-ext')
        p_nom_per_country_ext = p_nom_per_cluster_ext.groupby(grouper_links_ext).sum()
        # sum up all s_nom for each country
        grouper_lines_ext = national_lines_ext.bus0.map(n.buses.country).rename_axis(index='Line-ext')
        s_nom_real_per_country_ext = s_nom_real_per_cluster_ext.groupby(grouper_lines_ext).sum()
        # sum up capacities for lines and links
        capacity_per_country_ext = (s_nom_real_per_country_ext + p_nom_per_country_ext).rename(bus0='country')

        ### define right-hand side
        if national_lines_fix.empty & national_links_fix.empty:
            # if all national lines and links are extendable, find countries that occur both in the input data and in
            # the network
            idx_countries = (most_recent_grid_plan.index.intersection(existing_capacities.index)
                             .intersection(capacity_per_country_ext.indexes['country']))
            if not idx_countries.empty:
                # define right-hand side as the capacity that should exist according to the input data
                rhs = most_recent_grid_plan[idx_countries] * existing_capacities.loc[idx_countries, 'capacity']
        else:
            # if some lines and/or links not extendable, these need to be subtracted from the capacity given by the
            # input data
            # sum up the capacities that are not extendable
            grouper_links_fix = national_links_fix.bus0.map(n.buses.country)
            p_nom_per_country_fix = national_links_fix.groupby(grouper_links_fix).p_nom.sum()
            grouper_lines_fix = national_lines_fix.bus0.map(n.buses.country)
            s_nom_real_per_cluster_fix = national_lines_fix.s_nom * national_lines_fix.s_max_pu
            s_nom_real_per_country_fix = s_nom_real_per_cluster_fix.groupby(grouper_lines_fix).sum()
            capacity_per_country_fix = s_nom_real_per_country_fix.add(p_nom_per_country_fix, fill_value=0)

            # find the countries that exist in all objects relevant for right-hand side
            idx_countries = (most_recent_grid_plan.index.intersection(existing_capacities.index)
                             .intersection(capacity_per_country_fix.index)
                             .intersection(capacity_per_country_ext.indexes['country']))

            if not idx_countries.empty:
                # define right-hand side as the difference between the total capacity defined by the grid plans and the
                # non-extendable capacities
                rhs = (most_recent_grid_plan.loc[idx_countries] * existing_capacities.loc[idx_countries, 'capacity']
                       - capacity_per_country_fix[idx_countries])

        ### define constraint
        if not idx_countries.empty:
            # extract condition for constraint from config option
            national_expansion_condition = config["policy_plans"]['include_national_grid_plans']['national_expansion_condition']
            # set constraint according to config option
            if national_expansion_condition == 'min':
                n.model.add_constraints(capacity_per_country_ext.sel(country=idx_countries) >= rhs,
                                        name='national-grid-plans-min')
            if national_expansion_condition == 'max':
                n.model.add_constraints(capacity_per_country_ext.sel(country=idx_countries) <= rhs,
                                        name='national-grid-plans-max')
            if national_expansion_condition == 'equal':
                n.model.add_constraints(capacity_per_country_ext.sel(country=idx_countries) == rhs,
                                        name='national-grid-plans-equal')

def add_self_sufficiency_constraints(n, config):
    """
    Implements a degree of self-sufficiency for hydrogen and/or electricity. The self-sufficiency can be defined
    for specific countries, per cluster and on the EU level. The degree of self-sufficiency is given by
    local_generation/(local_generation+import).

    Parameters
    ----------
    n : pypsa.Network
    config : dict

    """

    def group(df, b="bus", eu=None):
        """
        Group given dataframe df by bus location or country.
        The optional argument `b` allows clustering by bus0 or bus1 for
        lines and links. If a list of EU countries is given as 'eu', all
        these countries will receive 'EU' as loaction.
        """
        if per_country:
            if eu is None:
                return df[b].map(location).map(n.buses.country).to_xarray()
            else:
                group_country = df[b].map(location).map(n.buses.country).to_xarray()
                group_eu_index = group_country.isin(eu)
                group_country[group_eu_index] = 'EU'
                return group_country
        else:
            return df[b].map(location).to_xarray()

    eu_countries = ["FR",
                    "DE",
                    "GB",
                    "IT",
                    "ES",
                    "PL",
                    "SE",
                    "NL",
                    "BE",
                    "FI",
                    "DK",
                    "PT",
                    "RO",
                    "AT",
                    "BG",
                    "EE",
                    "GR",
                    "LV",
                    "CZ",
                    "HU",
                    "IE",
                    "SK",
                    "LT",
                    "HR",
                    "LU",
                    "SI"]

    # assign the basic bus (e.g. AL0 1) to each bus as a location
    location = (
        n.buses.location
        if "location" in n.buses.columns
        else pd.Series(n.buses.index, index=n.buses.index)
    )

    # load custom constraints
    self_sufficiency_limits_full = pd.read_csv(
        config["policy_plans"]["self_sufficiency_limits"], index_col=[0]
    )
    # filter out the current planning year
    current_year = snakemake.wildcards.planning_horizons
    self_sufficiency_limits_full = self_sufficiency_limits_full.query(f'year=={current_year}')

    logger.info("Adding self-sufficiency constraints per carrier and country")

    # extract variables for each component type from model
    p_links = n.model["Link-p"]
    p_generators = n.model["Generator-p"]
    p_storage = n.model["StorageUnit-p_dispatch"]
    s_line = n.model["Line-s"]

    for per_country in [True, False]:
        if per_country:
            self_sufficiency_limits = self_sufficiency_limits_full[self_sufficiency_limits_full.index.str.len() == 2]
            per_country_name = 'country'
        else:
            self_sufficiency_limits = self_sufficiency_limits_full[self_sufficiency_limits_full.index.str.len() == 5]
            per_country_name = 'cluster'

        ### create constraint for hydrogen
        # calculate the energy of the hydrogen generation
        h2_generation_carrier = ['H2 Electrolysis',
                                 'SMR CC',
                                 'SMR']
        idx_gen_h2 = n.links[(n.links.carrier.isin(h2_generation_carrier))].index
        efficiencies = n.links.loc[idx_gen_h2, 'efficiency']
        generation_p_at_h2bus = p_links.loc[:, idx_gen_h2] * efficiencies
        generation_p_per_country_h2 = generation_p_at_h2bus.groupby(group(n.links.loc[idx_gen_h2], b="bus1")).sum()
        generation_e_h2 = ((generation_p_per_country_h2 * n.snapshot_weightings.generators)
                           .rename({"bus1": "bus"}).sum("snapshot"))
        if per_country:
            # add sum for EU
            generation_p_eu_h2 = (generation_p_at_h2bus
                                  .groupby(group(n.links.loc[idx_gen_h2], b="bus1", eu=eu_countries)).sum())
            generation_e_eu_h2 = ((generation_p_eu_h2 * n.snapshot_weightings.generators)
                                  .rename({"bus1": "bus"}).sum("snapshot"))
            # combine with country-specific expressions for EU countries
            generation_e_h2 = generation_e_h2.sel(bus=eu_countries) + generation_e_eu_h2

        # calculate energy of cross-border hydrogen transport
        h2_pipe_carrier = ['H2 pipeline retrofitted',
                           'H2 pipeline',
                           'H2 pipeline (Kernnetz)']
        if per_country:
            idx_cross_border_pipes_h2 = n.links[(n.links.carrier.isin(h2_pipe_carrier))
                                                & (n.links.bus0.str[:2] != n.links.bus1.str[:2])].index
        else:
            idx_cross_border_pipes_h2 = n.links[(n.links.carrier.isin(h2_pipe_carrier))].index
        p_pipes_out_per_country = (p_links.loc[:, idx_cross_border_pipes_h2]
                                   .groupby(group(n.links.loc[idx_cross_border_pipes_h2], b="bus0")).sum())
        e_pipes_out = ((p_pipes_out_per_country * n.snapshot_weightings.generators)
                       .rename({"bus0": "bus"}).sum("snapshot"))
        p_pipes_in_per_country = (p_links.loc[:, idx_cross_border_pipes_h2]
                                  .groupby(group(n.links.loc[idx_cross_border_pipes_h2], b="bus1")).sum())
        e_pipes_in = ((p_pipes_in_per_country * n.snapshot_weightings.generators)
                      .rename({"bus1": "bus"}).sum("snapshot"))

        if per_country:
            # add pipes out of EU
            idx_pipes_eu_h2 = n.links[(n.links.carrier.isin(h2_pipe_carrier))
                                      & ~(n.links.bus0.str[:2].isin(eu_countries) & n.links.bus1.str[:2].isin(eu_countries))
                                      & (n.links.bus0.str[:2]!=n.links.bus1.str[:2])].index
            p_pipes_out_eu = (p_links.loc[:, idx_pipes_eu_h2]
                              .groupby(group(n.links.loc[idx_pipes_eu_h2], b="bus0", eu=eu_countries)).sum())
            e_pipes_out_eu = ((p_pipes_out_eu * n.snapshot_weightings.generators)
                              .rename({"bus0": "bus"}).sum("snapshot"))
            e_pipes_out = e_pipes_out.sel(bus=eu_countries) + e_pipes_out_eu
            # add pipes into EU
            p_pipes_in_eu = (p_links.loc[:, idx_pipes_eu_h2]
                             .groupby(group(n.links.loc[idx_pipes_eu_h2], b="bus1", eu=eu_countries)).sum())
            e_pipes_in_eu = ((p_pipes_in_eu * n.snapshot_weightings.generators)
                             .rename({"bus1": "bus"}).sum("snapshot"))
            e_pipes_in = e_pipes_in.sel(bus=eu_countries) + e_pipes_in_eu

        # calculate the energy imported from outside of Europe
        h2_import_gen_carrier = ['import pipeline-H2',
                                 'import shipping-H2']
        idx_h2_import = n.generators[(n.generators.carrier.isin(h2_import_gen_carrier))].index
        if not idx_h2_import.empty:  # some years have no import generators
            p_h2_import_per_country = (p_generators.loc[:, idx_h2_import]
                                       .groupby(group(n.generators.loc[idx_h2_import])).sum())
            e_h2_import = (p_h2_import_per_country * n.snapshot_weightings.generators).sum("snapshot")

            if per_country:
                # add external imports to EU
                p_h2_import_eu = (p_generators.loc[:, idx_h2_import]
                                  .groupby(group(n.generators.loc[idx_h2_import], eu=eu_countries)).sum())
                e_h2_import_eu = (p_h2_import_eu * n.snapshot_weightings.generators).sum("snapshot")
                eu_import_countries = e_h2_import.indexes['bus'].intersection(eu_countries)
                e_h2_import = e_h2_import.sel(bus=eu_import_countries) + e_h2_import_eu
            # calculate import balances for countries/clusters
            local_import_h2 = e_h2_import + e_pipes_in - e_pipes_out
        else:
            # calculate import balances for countries/clusters
            local_import_h2 = e_pipes_in - e_pipes_out

        # calculate the demand for H2 as energy carrier
        demand_h2 = local_import_h2 + generation_e_h2
        # reduce custom limits to those applying to hydrogen and minimum values
        self_sufficiency_h2_min = (xr.DataArray(self_sufficiency_limits.query(f'carrier=="H2"')['min']
                                            .dropna()).rename(country="bus"))

        # find countries / clusters that appear both in the custom limit and in the network data
        index = self_sufficiency_h2_min.indexes["bus"].intersection(generation_e_h2.indexes["bus"])
        # define constraint: local generation should cover the local demand by the degree of self sufficiency. The local
        # demand is given by the sum of imports and generation.
        if not index.empty:
            name = f"self-sufficiency-H2-min-{per_country_name}"
            n.model.add_constraints(generation_e_h2.sel(bus=index)
                                    - demand_h2.sel(bus=index) * (self_sufficiency_h2_min.loc[index]) >= 0, name=name)

        # reduce custom limits to those applying to hydrogen and maximum values
        self_sufficiency_h2_max = (xr.DataArray(self_sufficiency_limits.query(f'carrier=="H2"')['max']
                                            .dropna()).rename(country="bus"))

        # find countries / clusters that appear both in the custom limit and in the network data
        index = self_sufficiency_h2_max.indexes["bus"].intersection(generation_e_h2.indexes["bus"])
        # define constraint: local generation should cover the local demand by the degree of self sufficiency. The local
        # demand is given by the sum of imports and generation.
        if not index.empty:
            name = f"self-sufficiency-H2-max-{per_country_name}"
            n.model.add_constraints(generation_e_h2.sel(bus=index)
                                    - demand_h2.sel(bus=index) * (self_sufficiency_h2_max.loc[index]) <= 0, name=name)
        ### create electricity constraint
        # calculate electric energy generated in each country/cluster
        gen_carrier_elec = ['offwind-ac',
                            'onwind',
                            'ror',
                            'solar',
                            'offwind-dc',
                            'solar rooftop']
        idx_gens_elec = n.generators[(n.generators.carrier.isin(gen_carrier_elec))].index
        p_generation_per_country_elec = (p_generators.loc[:, idx_gens_elec]
                                         .groupby(group(n.generators.loc[idx_gens_elec])).sum())
        e_generation_elec = (p_generation_per_country_elec * n.snapshot_weightings.generators).sum("snapshot")
        if per_country:
            # calculate electricity generation via generators inside the EU
            p_generation_eu_elec = (p_generators.loc[:, idx_gens_elec]
                                    .groupby(group(n.generators.loc[idx_gens_elec], eu=eu_countries)).sum())
            e_generation_eu_elec = (p_generation_eu_elec * n.snapshot_weightings.generators).sum("snapshot")
            e_generation_elec = e_generation_elec.sel(bus=eu_countries) + e_generation_eu_elec

        # calculate electrical energy generated via storage units in each cluster/country
        storage_unit_carrier = ["hydro"]
        idx_storage_units = n.storage_units[(n.storage_units.carrier.isin(storage_unit_carrier))].index
        p_storage_units_per_country = (p_storage.loc[:, idx_storage_units]
                                       .groupby(group(n.storage_units.loc[idx_storage_units])).sum())
        e_storage_units = (p_storage_units_per_country * n.snapshot_weightings.generators).sum("snapshot")
        if per_country:
            # sum up all storage units in the EU
            p_storage_units_eu = (p_storage.loc[:, idx_storage_units]
                                  .groupby(group(n.storage_units.loc[idx_storage_units], eu=eu_countries)).sum())
            e_storage_units_eu = (p_storage_units_eu * n.snapshot_weightings.generators).sum("snapshot")
            eu_storage_units = e_storage_units.indexes['bus'].intersection(eu_countries)
            e_storage_units = e_storage_units.sel(bus=eu_storage_units) + e_storage_units_eu

        # calculate electrical energy generated via links in each cluster/country
        link_carrier_elec = [  # hydrogen to electricity
            'H2 Fuel Cell',
            'H2 turbine',
            # combined heat and power
            'residential rural micro gas CHP',
            'services rural micro gas CHP',
            'residential urban decentral micro gas CHP',
            'services urban decentral micro gas CHP',
            'urban central gas CHP',
            'urban central gas CHP CC',
            'urban central solid biomass CHP',
            'urban central solid biomass CHP CC',
            # conventional carriers
            'coal',
            'OCGT',
            'CCGT',
            'lignite',
            'nuclear',
            'oil',
            'allam']
        idx_links_elec = n.links[(n.links.carrier.isin(link_carrier_elec))].index
        efficiencies = n.links.loc[idx_links_elec, 'efficiency']
        p_links_at_ac_bus = p_links.loc[:, idx_links_elec] * efficiencies
        p_links_per_country_elec = p_links_at_ac_bus.groupby(group(n.links.loc[idx_links_elec], b="bus1")).sum()
        e_links_elec = ((p_links_per_country_elec.rename({"bus1": "bus"}) * n.snapshot_weightings.generators)
                        .sum("snapshot"))

        if per_country:
            # sum up all electrical energy generated via links
            p_links_eu_elec = p_links_at_ac_bus.groupby(
                group(n.links.loc[idx_links_elec], b="bus1", eu=eu_countries)).sum()
            e_links_eu_elec = (p_links_eu_elec.rename({"bus1": "bus"}) * n.snapshot_weightings.generators).sum(
                "snapshot")
            e_links_elec = e_links_elec.sel(bus=eu_countries) + e_links_eu_elec

        # calculate total electricity generated in each country/cluster
        generation_elec = e_generation_elec + e_storage_units + e_links_elec

        # calculate the cross-border electricity import via DC links per country/cluster
        if per_country:
            idx_dc = n.links[(n.links.carrier == "DC") & (n.links.bus0.str[:2] != n.links.bus1.str[:2])].index
        else:
            idx_dc = n.links[(n.links.carrier == "DC")].index
        p_dc_out = p_links.loc[:, idx_dc].groupby(group(n.links.loc[idx_dc], b="bus0")).sum()
        e_dc_out = ((p_dc_out * n.snapshot_weightings.generators)
                    .rename({"bus0": "bus"}).sum("snapshot"))
        p_dc_in = p_links.loc[:, idx_dc].groupby(group(n.links.loc[idx_dc], b="bus1")).sum()
        e_dc_in = ((p_dc_in * n.snapshot_weightings.generators)
                   .rename({"bus1": "bus"}).sum("snapshot"))
        if per_country:
            # calculate electricity exported from the EU to the rest of Europe via DC links
            idx_dc_eu = n.links[(n.links.carrier == "DC")
                                & ~(n.links.bus0.str[:2].isin(eu_countries)
                                   & n.links.bus1.str[:2].isin(eu_countries))
                                & (n.links.bus0.str[:2]!=n.links.bus1.str[:2])].index
            p_dc_out_eu = (p_links.loc[:, idx_dc_eu]
                           .groupby(group(n.links.loc[idx_dc_eu], b="bus0", eu=eu_countries)).sum())
            e_dc_out_eu = ((p_dc_out_eu * n.snapshot_weightings.generators)
                           .rename({"bus0": "bus"}).sum("snapshot"))
            eu_dc_out_countries = e_dc_out.indexes['bus'].intersection(eu_countries)
            e_dc_out = e_dc_out.sel(bus=eu_dc_out_countries) + e_dc_out_eu
            # sum up the electrical energy imported to the EU from the rest of Europe via DC links
            p_dc_in_eu = (p_links.loc[:, idx_dc_eu]
                          .groupby(group(n.links.loc[idx_dc_eu], b="bus1", eu=eu_countries)).sum())
            e_dc_in_eu = ((p_dc_in_eu * n.snapshot_weightings.generators)
                          .rename({"bus1": "bus"}).sum("snapshot"))
            eu_dc_in_countries = e_dc_in.indexes['bus'].intersection(eu_countries)
            e_dc_in = e_dc_in.sel(bus=eu_dc_in_countries) + e_dc_in_eu

        # calculate the cross-border electricity import via AC lines per country/cluster
        if per_country:
            idx_lines = n.lines[(n.lines.bus0.str[:2] != n.lines.bus1.str[:2])].index
        else:
            idx_lines = n.lines.index
        s_ac_in = s_line.loc[:, idx_lines].groupby(group(n.lines.loc[idx_lines], b="bus1")).sum()
        e_ac_in = (s_ac_in * n.snapshot_weightings.generators).rename({"bus1": "bus"}).sum("snapshot")
        s_ac_out = s_line.loc[:, idx_lines].groupby(group(n.lines.loc[idx_lines], b="bus0")).sum()
        e_ac_out = (s_ac_out * n.snapshot_weightings.generators).rename({"bus0": "bus"}).sum("snapshot")

        if per_country:
            # sum up the electrical energy imported to the EU from the rest of Europe via AC lines
            idx_lines_eu = n.lines[~(
                n.lines.bus0.str[:2].isin(eu_countries) & n.lines.bus1.str[:2].isin(eu_countries))
                                   & (n.lines.bus0.str[:2]!=n.lines.bus1.str[:2])].index
            s_ac_in_eu = s_line.loc[:, idx_lines_eu].groupby(
                group(n.lines.loc[idx_lines_eu], b="bus1", eu=eu_countries)).sum()
            e_ac_in_eu = (s_ac_in_eu * n.snapshot_weightings.generators).rename({"bus1": "bus"}).sum("snapshot")
            eu_ac_in_countries = e_ac_in.indexes['bus'].intersection(eu_countries)
            e_ac_in = e_ac_in.sel(bus=eu_ac_in_countries) + e_ac_in_eu
            # calculate electricity exported from the EU to the rest of Europe via AC lines
            s_ac_out_eu = s_line.loc[:, idx_lines_eu].groupby(
                group(n.lines.loc[idx_lines_eu], b="bus0", eu=eu_countries)).sum()
            e_ac_out_eu = (s_ac_out_eu * n.snapshot_weightings.generators).rename({"bus0": "bus"}).sum("snapshot")
            eu_ac_out_countries = e_ac_out.indexes['bus'].intersection(eu_countries)
            e_ac_out = e_ac_out.sel(bus=eu_ac_out_countries) + e_ac_out_eu

        # calculate the net electricity imported per country/cluster
        local_import_elec = e_dc_in - e_dc_out + e_ac_in - e_ac_out

        # calculate total demand for electricity
        demand_elec = local_import_elec + generation_elec
        # filter the custom limits for electricity and minimum values
        self_sufficiency_elec_min = (xr.DataArray(self_sufficiency_limits.query(f'carrier=="AC"')['min']
                                              .dropna()).rename(country="bus"))

        # find countries / clusters that appear both in the custom limit and in the network data
        index = self_sufficiency_elec_min.indexes["bus"].intersection(generation_elec.indexes["bus"])

        # define constraint: local generation should cover the local demand by the degree of self-sufficiency. The local
        # demand is given by the sum of imports and generation.
        if not index.empty:
            name = f"self-sufficiency-elec-min-{per_country_name}"
            n.model.add_constraints(generation_elec.sel(bus=index)
                                    - demand_elec.sel(bus=index) * (self_sufficiency_elec_min.loc[index]) >= 0, name=name)

        # filter the custom limits for electricity and maximum values
        self_sufficiency_elec_max = (xr.DataArray(self_sufficiency_limits.query(f'carrier=="AC"')['max']
                                              .dropna()).rename(country="bus"))

        # find countries / clusters that appear both in the custom limit and in the network data
        index = self_sufficiency_elec_max.indexes["bus"].intersection(generation_elec.indexes["bus"])

        # define constraint: local generation should cover the local demand by the degree of self-sufficiency. The local
        # demand is given by the sum of imports and generation.
        if not index.empty:
            name = f"self-sufficiency-elec-max-{per_country_name}"
            n.model.add_constraints(generation_elec.sel(bus=index)
                                    - demand_elec.sel(bus=index) * (self_sufficiency_elec_max.loc[index]) <= 0, name=name)

        ### create constraint for liquid hydrocarbons
        # calculate the energy of the synfuel generation
        synfuel_generation_carrier = ['biomass to liquid', 'Fischer-Tropsch']
        idx_gen_synfuel = n.links[(n.links.carrier.isin(synfuel_generation_carrier))].index
        efficiencies = n.links.loc[idx_gen_synfuel, 'efficiency']
        generation_p_at_synfuelbus = p_links.loc[:, idx_gen_synfuel] * efficiencies
        generation_p_per_country_synfuel = generation_p_at_synfuelbus.groupby(group(n.links.loc[idx_gen_synfuel], b="bus0")).sum()
        generation_e_synfuel = ((generation_p_per_country_synfuel * n.snapshot_weightings.generators)
                               .rename({"bus0": "bus"}).sum("snapshot"))
        if per_country:
            # calculate electricity generation via generators inside the EU
            generation_p_eu_synfuel = (generation_p_at_synfuelbus
                                    .groupby(group(n.links.loc[idx_gen_synfuel], b="bus0", eu=eu_countries)).sum())
            generation_e_eu_synfuel = ((generation_p_eu_synfuel * n.snapshot_weightings.generators)
                                       .rename({"bus0": "bus"}).sum("snapshot"))
            generation_e_synfuel = generation_e_synfuel.sel(bus=eu_countries) + generation_e_eu_synfuel

        oil_demand_carrier = ['land transport oil', 'shipping oil','residential rural oil boiler',
                                  'services rural oil boiler', 'residential urban decentral oil boiler',
                                  'services urban decentral oil boiler', 'naphtha for industry',
                                  'kerosene for aviation', 'agriculture machinery oil', 'oil']

        idx_demand_oil = n.links[(n.links.carrier.isin(oil_demand_carrier))].index
        demand_p_per_country_oil = (p_links.loc[:, idx_demand_oil]
                                        .groupby(group(n.links.loc[idx_demand_oil], b="bus1")).sum())
        demand_e_oil = ((demand_p_per_country_oil * n.snapshot_weightings.generators)
                               .rename({"bus1": "bus"}).sum("snapshot"))
        if per_country:
            # calculate electricity generation via generators inside the EU
            demand_p_eu_oil = (p_links.loc[:, idx_demand_oil]
                                    .groupby(group(n.links.loc[idx_demand_oil], b="bus1", eu=eu_countries)).sum())
            demand_e_eu_oil = ((demand_p_eu_oil * n.snapshot_weightings.generators)
                                   .rename({"bus1": "bus"}).sum("snapshot"))
            demand_e_oil = demand_e_oil.sel(bus=eu_countries) + demand_e_eu_oil
        # reduce custom limits to those applying to synfuel and minimum values
        self_sufficiency_synfuel_min = (xr.DataArray(self_sufficiency_limits.query(f'carrier=="synfuel"')['min']
                                                .dropna()).rename(country="bus"))

        # find countries / clusters that appear both in the custom limit and in the network data
        index = self_sufficiency_synfuel_min.indexes["bus"].intersection(generation_e_synfuel.indexes["bus"])
        # define constraint: local generation should cover the local demand by the degree of self-sufficiency.
        if not index.empty:
            name = f"self-sufficiency-synfuel-min-{per_country_name}"
            n.model.add_constraints(generation_e_synfuel.sel(bus=index)
                                    - demand_e_oil.sel(bus=index) * (self_sufficiency_synfuel_min.loc[index]) >= 0, name=name)

        # reduce custom limits to those applying to synfuel and maximum values
        self_sufficiency_synfuel_max = (xr.DataArray(self_sufficiency_limits.query(f'carrier=="synfuel"')['max']
                                                .dropna()).rename(country="bus"))

        # find countries / clusters that appear both in the custom limit and in the network data
        index = self_sufficiency_synfuel_max.indexes["bus"].intersection(generation_e_synfuel.indexes["bus"])
        # define constraint: local generation should cover the local demand by the degree of self-sufficiency
        if not index.empty:
            name = f"self-sufficiency-synfuel-max-{per_country_name}"
            n.model.add_constraints(generation_e_synfuel.sel(bus=index)
                                    - demand_e_oil.sel(bus=index) * (self_sufficiency_synfuel_max.loc[index]) <= 0, name=name)


def add_overall_min_capacities_constraints(n, config):
    """
    Add a per-carrier minimal overall capacity.

    BAU_mincapacities and opts must be adjusted in the config.yaml.

    Parameters
    ----------
    n : pypsa.Network
    config : dict

    Example
    -------
    scenario:
        opts: [Co2L-overall_min_capacities-24h]
    electricity:
        BAU_mincapacities:
            solar: 0
            onwind: 0
            OCGT: 100000
            offwind-ac: 0
            offwind-dc: 0
    Which sets minimum expansion across all nodes e.g. in Europe to 100GW.
    OCGT bus 1 + OCGT bus 2 + ... > 100000
    """
    mincaps = pd.Series(config["electricity"]["BAU_mincapacities"])
    p_nom = n.model["Generator-p_nom"]
    ext_i = n.generators.query("p_nom_extendable")
    ext_carrier_i = xr.DataArray(ext_i.carrier.rename_axis("Generator-ext"))
    lhs = p_nom.groupby(ext_carrier_i).sum()
    index = mincaps.index.intersection(lhs.indexes["carrier"])
    rhs = mincaps[index].rename_axis("carrier")
    n.model.add_constraints(lhs >= rhs, name="bau_mincaps")


# TODO: think about removing or make per country
def add_capacity_reserve_constraints(n, config):
    """
    Add a capacity reserve margin of a certain fraction above the peak demand.
    Renewable generators and storage do not contribute. Ignores network.

    Parameters
    ----------
        n : pypsa.Network
        config : dict

    Example
    -------
    config.yaml requires to specify opts:

    scenario:
        opts: [Co2L-capacity_reserve-24h]
    electricity:
        capacity_reserve_margin: 0.1
    Which sets a reserve margin of 10% above the peak demand.
    """
    peakdemand = n.loads_t.p_set.sum(axis=1).max()
    margin = 1.0 + config["electricity"]["capacity_reserve_margin"]
    reserve_margin = peakdemand * margin
    conventional_carriers = config["electricity"]["conventional_carriers"]  # noqa: F841
    ext_gens_i = n.generators.query(
        "carrier in @conventional_carriers & p_nom_extendable"
    ).index
    p_nom = n.model["Generator-p_nom"].loc[ext_gens_i]
    lhs = p_nom.sum()
    exist_conv_caps = n.generators.query(
        "~p_nom_extendable & carrier in @conventional_carriers"
    ).p_nom.sum()
    rhs = reserve_margin - exist_conv_caps
    n.model.add_constraints(lhs >= rhs, name="reserve_mintotalcap")


def add_operational_reserve_margin(n, sns, config):
    """
    Build reserve margin constraints based on the formulation given in
    https://genxproject.github.io/GenX/dev/core/#Reserves.

    Parameters
    ----------
        n : pypsa.Network
        sns: pd.DatetimeIndex
        config : dict

    Example:
    --------
    config.yaml requires to specify operational_reserve:
    operational_reserve: # like https://genxproject.github.io/GenX/dev/core/#Reserves
        activate: true
        epsilon_load: 0.02 # percentage of load at each snapshot
        epsilon_vres: 0.02 # percentage of VRES at each snapshot
        contingency: 400000 # MW
    """
    reserve_config = config["electricity"]["operational_reserve"]
    EPSILON_LOAD = reserve_config["epsilon_load"]
    EPSILON_VRES = reserve_config["epsilon_vres"]
    CONTINGENCY = reserve_config["contingency"]

    # Reserve Variables
    n.model.add_variables(
        0, np.inf, coords=[sns, n.generators.index], name="Generator-r"
    )
    reserve = n.model["Generator-r"]
    summed_reserve = reserve.sum("Generator")

    # Share of extendable renewable capacities
    ext_i = n.generators.query("p_nom_extendable").index
    vres_i = n.generators_t.p_max_pu.columns
    if not ext_i.empty and not vres_i.empty:
        capacity_factor = n.generators_t.p_max_pu[vres_i.intersection(ext_i)]
        p_nom_vres = (
            n.model["Generator-p_nom"]
            .loc[vres_i.intersection(ext_i)]
            .rename({"Generator-ext": "Generator"})
        )
        lhs = summed_reserve + (p_nom_vres * (-EPSILON_VRES * capacity_factor)).sum(
            "Generator"
        )

    # Total demand per t
    demand = get_as_dense(n, "Load", "p_set").sum(axis=1)

    # VRES potential of non extendable generators
    capacity_factor = n.generators_t.p_max_pu[vres_i.difference(ext_i)]
    renewable_capacity = n.generators.p_nom[vres_i.difference(ext_i)]
    potential = (capacity_factor * renewable_capacity).sum(axis=1)

    # Right-hand-side
    rhs = EPSILON_LOAD * demand + EPSILON_VRES * potential + CONTINGENCY

    n.model.add_constraints(lhs >= rhs, name="reserve_margin")

    # additional constraint that capacity is not exceeded
    gen_i = n.generators.index
    ext_i = n.generators.query("p_nom_extendable").index
    fix_i = n.generators.query("not p_nom_extendable").index

    dispatch = n.model["Generator-p"]
    reserve = n.model["Generator-r"]

    capacity_variable = n.model["Generator-p_nom"].rename(
        {"Generator-ext": "Generator"}
    )
    capacity_fixed = n.generators.p_nom[fix_i]

    p_max_pu = get_as_dense(n, "Generator", "p_max_pu")

    lhs = dispatch + reserve - capacity_variable * p_max_pu[ext_i]

    rhs = (p_max_pu[fix_i] * capacity_fixed).reindex(columns=gen_i, fill_value=0)

    n.model.add_constraints(lhs <= rhs, name="Generator-p-reserve-upper")


def add_battery_constraints(n):
    """
    Add constraint ensuring that charger = discharger, i.e.
    1 * charger_size - efficiency * discharger_size = 0
    """
    if not n.links.p_nom_extendable.any():
        return

    discharger_bool = n.links.index.str.contains("battery discharger")
    charger_bool = n.links.index.str.contains("battery charger")

    dischargers_ext = n.links[discharger_bool].query("p_nom_extendable").index
    chargers_ext = n.links[charger_bool].query("p_nom_extendable").index

    eff = n.links.efficiency[dischargers_ext].values
    lhs = (
            n.model["Link-p_nom"].loc[chargers_ext]
            - n.model["Link-p_nom"].loc[dischargers_ext] * eff
    )

    n.model.add_constraints(lhs == 0, name="Link-charger_ratio")


def add_lossy_bidirectional_link_constraints(n):
    if not n.links.p_nom_extendable.any() or "reversed" not in n.links.columns:
        return

    n.links["reversed"] = n.links.reversed.fillna(0).astype(bool)
    carriers = n.links.loc[n.links.reversed, "carrier"].unique()  # noqa: F841

    forward_i = n.links.query(
        "carrier in @carriers and ~reversed and p_nom_extendable"
    ).index

    def get_backward_i(forward_i):
        return pd.Index(
            [
                (
                    re.sub(r"-(\d{4})$", r"-reversed-\1", s)
                    if re.search(r"-\d{4}$", s)
                    else s + "-reversed"
                )
                for s in forward_i
            ]
        )

    backward_i = get_backward_i(forward_i)

    lhs = n.model["Link-p_nom"].loc[backward_i]
    rhs = n.model["Link-p_nom"].loc[forward_i]

    n.model.add_constraints(lhs == rhs, name="Link-bidirectional_sync")


def add_chp_constraints(n):
    electric = (
            n.links.index.str.contains("urban central")
            & n.links.index.str.contains("CHP")
            & n.links.index.str.contains("electric")
    )
    heat = (
            n.links.index.str.contains("urban central")
            & n.links.index.str.contains("CHP")
            & n.links.index.str.contains("heat")
    )

    electric_ext = n.links[electric].query("p_nom_extendable").index
    heat_ext = n.links[heat].query("p_nom_extendable").index

    electric_fix = n.links[electric].query("~p_nom_extendable").index
    heat_fix = n.links[heat].query("~p_nom_extendable").index

    p = n.model["Link-p"]  # dimension: [time, link]

    # output ratio between heat and electricity and top_iso_fuel_line for extendable
    if not electric_ext.empty:
        p_nom = n.model["Link-p_nom"]

        lhs = (
                p_nom.loc[electric_ext]
                * (n.links.p_nom_ratio * n.links.efficiency)[electric_ext].values
                - p_nom.loc[heat_ext] * n.links.efficiency[heat_ext].values
        )
        n.model.add_constraints(lhs == 0, name="chplink-fix_p_nom_ratio")

        rename = {"Link-ext": "Link"}
        lhs = (
                p.loc[:, electric_ext]
                + p.loc[:, heat_ext]
                - p_nom.rename(rename).loc[electric_ext]
        )
        n.model.add_constraints(lhs <= 0, name="chplink-top_iso_fuel_line_ext")

    # top_iso_fuel_line for fixed
    if not electric_fix.empty:
        lhs = p.loc[:, electric_fix] + p.loc[:, heat_fix]
        rhs = n.links.p_nom[electric_fix]
        n.model.add_constraints(lhs <= rhs, name="chplink-top_iso_fuel_line_fix")

    # back-pressure
    if not electric.empty:
        lhs = (
                p.loc[:, heat] * (n.links.efficiency[heat] * n.links.c_b[electric].values)
                - p.loc[:, electric] * n.links.efficiency[electric]
        )
        n.model.add_constraints(lhs <= rhs, name="chplink-backpressure")


def add_pipe_retrofit_constraint(n):
    """
    Add constraint for retrofitting existing CH4 pipelines to H2 pipelines.
    """

    def remove_prefix(pipe_index):
        new_index = pipe_index.str.split(' ').str[-5:].str.join(' ')
        return new_index

    if "reversed" not in n.links.columns:
        n.links["reversed"] = False
    gas_pipes_i = n.links.query(
        "carrier == 'gas pipeline' and p_nom_extendable and ~reversed"
    ).index
    h2_retrofitted_i = n.links.query(
        "carrier == 'H2 pipeline retrofitted' and p_nom_extendable and ~reversed"
    ).index

    if h2_retrofitted_i.empty or gas_pipes_i.empty:
        return

    p_nom = n.model["Link-p_nom"]

    CH4_per_H2 = 1 / n.config["sector"]["H2_retrofit_capacity_per_CH4"]
    lhs = p_nom.loc[gas_pipes_i] + CH4_per_H2 * p_nom.loc[h2_retrofitted_i]
    rhs = n.links.p_nom[gas_pipes_i].rename_axis("Link-ext")
    if lhs.sizes['Link-ext'] > len(rhs):
        lhs = lhs.assign_coords({'Link-ext': remove_prefix(lhs.indexes['Link-ext'])}).groupby('Link-ext').sum()
    n.model.add_constraints(lhs == rhs, name="Link-pipe_retrofit")


def add_co2_atmosphere_constraint(n, snapshots):
    glcs = n.global_constraints[n.global_constraints.type == "co2_atmosphere"]

    if glcs.empty:
        return
    for name, glc in glcs.iterrows():
        carattr = glc.carrier_attribute
        emissions = n.carriers.query(f"{carattr} != 0")[carattr]

        if emissions.empty:
            continue

        # stores
        n.stores["carrier"] = n.stores.bus.map(n.buses.carrier)
        stores = n.stores.query("carrier in @emissions.index and not e_cyclic")
        if not stores.empty:
            last_i = snapshots[-1]
            lhs = n.model["Store-e"].loc[last_i, stores.index]
            rhs = glc.constant

            n.model.add_constraints(lhs <= rhs, name=f"GlobalConstraint-{name}")

def add_import_retrofit_constraint(n):
    """
    Add constraint for retrofitting existing import infrastructure for CH4 to H2. Additionally, allow usage of natural
    gas infrastructure by syngas.

    Parameters
    ----------
    n : pypsa.Network
        Network containing n.model for adding the constraint
    """

    def shorten_index(old_p, tech):
        new_index = old_p.indexes['Generator'].str[:5] + ' import ' + tech + ' gas'
        new_p = old_p.assign_coords({'Generator': new_index})
        return new_p

    # extract variable for installed capacity
    p_nom = n.model["Generator-p_nom"]
    # extract variable for dispatch
    p_t = n.model["Generator-p"]

    # get indexes for components contributing to pipeline imports
    natural_gas_pipes_i = n.generators.query(
        "carrier == 'import pipeline gas' & p_nom_extendable"
    ).index
    syngas_pipes_i = n.generators.query(
        "carrier == 'import pipeline-syngas' & p_nom_extendable"
    ).index
    h2_pipes_i = n.generators.query(
        "carrier == 'import pipeline-H2' & p_nom_extendable"
    ).index

    # find locations where import gas pipelines can be retrofitted to H2 pipelines
    clusters_for_retrofit = natural_gas_pipes_i.str[:5].intersection(h2_pipes_i.str[:5])
    # filter indixes of pipelines for locations where retrofitting can take place
    filtered_natural_gas_pipes_i = pd.Index([x for x in natural_gas_pipes_i if x[:5] in clusters_for_retrofit])
    filtered_h2_pipes_i = pd.Index([x for x in h2_pipes_i if x[:5] in clusters_for_retrofit])

    ### enable retrofitting of import CH4 pipelines
    if not filtered_h2_pipes_i.empty and not filtered_natural_gas_pipes_i.empty:
        # extract from config, how much CH4 capacity needs to be retrofitted per MW H2 capacity
        CH4_per_H2 = 1 / n.config["sector"]["H2_retrofit_capacity_per_CH4"]
        # calculate the left-hand side as the total installed import pipeline capacity per location
        lhs = p_nom.loc[filtered_natural_gas_pipes_i] + CH4_per_H2 * p_nom.loc[filtered_h2_pipes_i]
        # set the right to old natural gas pipeline capacity
        rhs = n.generators.p_nom_max[filtered_natural_gas_pipes_i].rename_axis("Generator-ext")
        n.model.add_constraints(lhs == rhs, name="Generator-pipe_retrofit")


    clusters_for_dual_use = natural_gas_pipes_i.str[:5].intersection(syngas_pipes_i.str[:5])
    filtered_natural_gas_pipes_i = pd.Index([x for x in natural_gas_pipes_i if x[:5] in clusters_for_dual_use])
    filtered_syngas_pipes_i = pd.Index([x for x in syngas_pipes_i if x[:5] in clusters_for_dual_use])
    ### enable usage of natural gas pipelines by syngas
    if not syngas_pipes_i.empty and not filtered_natural_gas_pipes_i.empty:
        # filter and rename dispatch of syngas pipeline generator
        p_t_syngas_pipeline = shorten_index(p_t.sel(Generator=filtered_syngas_pipes_i), 'pipeline')
        # filter dispatch of natural gas pipeline generator
        p_t_natural_gas_pipeline = p_t.sel(Generator=filtered_natural_gas_pipes_i)
        # get installed capacity of the natural gas pipeline as upper limit for the total dispatch
        p_nom_natural_gas = p_nom.loc[filtered_natural_gas_pipes_i].rename({'Generator-ext': 'Generator'})
        # define constraint according to the assumption that the sum of the gas pipeline dispatch must be at maximum
        # the installed capacity of the natural gas pipeline
        lhs = p_nom_natural_gas - p_t_syngas_pipeline - p_t_natural_gas_pipeline
        n.model.add_constraints(lhs >= 0, name="Generator-import-pipe-usage")
        # get installed capacity of syngas pipeline to set it to natural gas pipeline
        p_nom_syngas_pipe = p_nom.loc[filtered_syngas_pipes_i].rename({'Generator-ext': 'Generator'})
        # for the pipelines to be equally useable with syngas, its p_nom_opt must be the same as for the natural gas
        # pipeline
        lhs = p_nom_syngas_pipe - p_nom_natural_gas
        n.model.add_constraints(lhs == 0, name='Generator-import-pipe-equality')

    # get indexes of generators contributing to shipping imports
    natural_gas_terminal_i = n.generators.query(
        "carrier == 'import lng gas' & p_nom_extendable"
    ).index
    h2_terminal_i = n.generators.query(
        "index.str.contains('shipping-H2 \(retrofitted\)') & p_nom_extendable"
    ).index
    syngas_terminal_i = n.generators.query(
        "carrier == 'import shipping-syngas' & p_nom_extendable"
    ).index
    # filter for the clusters that have both a natural gas and a retrofitted generator
    clusters_for_retrofit = natural_gas_terminal_i.str[:5].intersection(h2_terminal_i.str[:5])
    filtered_natural_gas_terminal_i = pd.Index([x for x in natural_gas_terminal_i if x[:5] in clusters_for_retrofit])
    filtered_h2_terminal_i = pd.Index([x for x in h2_terminal_i if x[:5] in clusters_for_retrofit])
    ### enable retrofitting of LNG terminals
    if not filtered_h2_terminal_i.empty and not filtered_natural_gas_terminal_i.empty:
        # calculate the left-hand side as the total installed import terminal capacity per location
        lhs = p_nom.loc[filtered_natural_gas_terminal_i] + p_nom.loc[filtered_h2_terminal_i]
        # set right-hand side to initial capacity of the lng terminals
        rhs = n.generators.p_nom_max[filtered_natural_gas_terminal_i].rename_axis("Generator-ext")
        # set lng terminal retrofitting constraint
        n.model.add_constraints(lhs == rhs, name="Generator-lng-retrofit")

    # filter for terminals that can be used by natural and syngas
    clusters_for_dual_use = natural_gas_terminal_i.str[:5].intersection(syngas_terminal_i.str[:5])
    filtered_natural_gas_terminal_i = pd.Index([x for x in natural_gas_terminal_i if x[:5] in clusters_for_dual_use])
    filtered_syngas_terminal_i = pd.Index([x for x in syngas_terminal_i if x[:5] in clusters_for_dual_use])
    # enable usage of LNG terminals with syngas
    if not filtered_syngas_terminal_i.empty and not filtered_natural_gas_terminal_i.empty:
        # filter and rename dispatch of syngas lng generator
        p_t_syngas_terminal = shorten_index(p_t.sel(Generator=filtered_syngas_terminal_i), 'lng')
        # filter dispatch of natural gas pipeline generator
        p_t_natural_gas_terminal = p_t.sel(Generator=filtered_natural_gas_terminal_i)
        # get installed capacity of the natural gas terminal as upper limit for the total dispatch
        p_nom_natural_gas_terminal = p_nom.loc[filtered_natural_gas_terminal_i].rename({'Generator-ext': 'Generator'})
        # define constraint according to the assumption that the sum of the gas pipeline dispatch must be at maximum
        # the installed capacity of the natural gas pipeline
        lhs = p_nom_natural_gas_terminal - p_t_syngas_terminal - p_t_natural_gas_terminal
        n.model.add_constraints(lhs >= 0, name="Generator-import-lng-usage")
        # get installed capacity of syngas terminal to set to LNG capacity
        p_nom_syngas_terminal = p_nom.loc[filtered_syngas_terminal_i].rename({'Generator-ext': 'Generator'})
        # define contraint that sets the capacity of the generator of syngas to the lng terminal capacity, so dual usage
        # is possible.
        lhs = p_nom_syngas_terminal - p_nom_natural_gas_terminal
        n.model.add_constraints(lhs == 0, name='Generator-import-terminal-equality')

def extra_functionality(n, snapshots):
    """
    Collects supplementary constraints which will be passed to
    ``pypsa.optimization.optimize``.

    If you want to enforce additional custom constraints, this is a good
    location to add them. The arguments ``opts`` and
    ``snakemake.config`` are expected to be attached to the network.
    """
    opts = n.opts
    config = n.config
    constraints = config["solving"].get("constraints", {})
    if (
            "overall_min_capacities" in opts or constraints.get("overall_min_capacities", False)
    ) and n.generators.p_nom_extendable.any():
        add_overall_min_capacities_constraints(n, config)
    if (
            "capacity_reserve" in opts or constraints.get("capacity_reserve", False)
    ) and n.generators.p_nom_extendable.any():
        add_capacity_reserve_constraints(n, config)
    if (
            "country_carrier_limit" in opts or constraints.get("country_carrier_limit", False)
    ) and n.generators.p_nom_extendable.any():
        add_country_carrier_limit_constraints(n, config)
    if (
            "self_sufficiency" in opts or constraints.get("self_sufficiency", False)
    ) and n.generators.p_nom_extendable.any():
        add_self_sufficiency_constraints(n, config)
    if (
            "national_grid_plans" in opts or constraints.get("national_grid_plans", False)
    ) and n.generators.p_nom_extendable.any():
        add_national_grid_plan_constraints(n, config)
    reserve = config["electricity"].get("operational_reserve", {})
    if reserve.get("activate"):
        add_operational_reserve_margin(n, snapshots, config)

    add_battery_constraints(n)
    add_lossy_bidirectional_link_constraints(n)
    add_pipe_retrofit_constraint(n)
    add_import_retrofit_constraint(n)
    if n._multi_invest:
        add_carbon_constraint(n, snapshots)
        add_carbon_budget_constraint(n, snapshots)
        add_retrofit_gas_boiler_constraint(n, snapshots)
    else:
        add_co2_atmosphere_constraint(n, snapshots)

    if snakemake.params.custom_extra_functionality:
        source_path = snakemake.params.custom_extra_functionality
        assert os.path.exists(source_path), f"{source_path} does not exist"
        sys.path.append(os.path.dirname(source_path))
        module_name = os.path.splitext(os.path.basename(source_path))[0]
        module = importlib.import_module(module_name)
        custom_extra_functionality = getattr(module, module_name)
        custom_extra_functionality(n, snapshots, snakemake)


def solve_network(n, config, solving, opts="", **kwargs):
    set_of_options = solving["solver"]["options"]
    cf_solving = solving["options"]

    kwargs["multi_investment_periods"] = config["foresight"] == "perfect"
    kwargs["solver_options"] = (
        solving["solver_options"][set_of_options] if set_of_options else {}
    )
    kwargs["solver_name"] = solving["solver"]["name"]
    kwargs["extra_functionality"] = extra_functionality
    kwargs["transmission_losses"] = cf_solving.get("transmission_losses", False)
    kwargs["linearized_unit_commitment"] = cf_solving.get(
        "linearized_unit_commitment", False
    )
    kwargs["assign_all_duals"] = cf_solving.get("assign_all_duals", False)
    kwargs["io_api"] = cf_solving.get("io_api", None)

    if kwargs["solver_name"] == "gurobi":
        logging.getLogger("gurobipy").setLevel(logging.CRITICAL)

    if kwargs["solver_name"] == "xpress":
        if 'name' in kwargs["solver_options"]:
            # xpress 9.2.5 can not deal with the solver option 'name':'xpress'
            del kwargs["solver_options"]['name']

    rolling_horizon = cf_solving.pop("rolling_horizon", False)
    skip_iterations = cf_solving.pop("skip_iterations", False)
    if not n.lines.s_nom_extendable.any():
        skip_iterations = True
        logger.info("No expandable lines found. Skipping iterative solving.")

    # add to network for extra_functionality
    n.config = config
    n.opts = opts

    if rolling_horizon:
        kwargs["horizon"] = cf_solving.get("horizon", 365)
        kwargs["overlap"] = cf_solving.get("overlap", 0)
        n.optimize.optimize_with_rolling_horizon(**kwargs)
        status, condition = "", ""
    elif skip_iterations:
        status, condition = n.optimize(**kwargs)
    else:
        kwargs["track_iterations"] = (cf_solving.get("track_iterations", False),)
        kwargs["min_iterations"] = (cf_solving.get("min_iterations", 4),)
        kwargs["max_iterations"] = (cf_solving.get("max_iterations", 6),)
        status, condition = n.optimize.optimize_transmission_expansion_iteratively(
            **kwargs
        )

    if status != "ok" and not rolling_horizon:
        logger.warning(
            f"Solving status '{status}' with termination condition '{condition}'"
        )
    if "infeasible" in condition:
        labels = n.model.compute_infeasibilities()
        logger.info(f"Labels:\n{labels}")
        n.model.print_infeasibilities()
        raise RuntimeError("Solving status 'infeasible'")

    return n


if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake(
            "solve_sector_network_myopic",
            configfile=r"...",  # add the path to the config file with which you want to debug
            planning_horizons=2040,
        )
        script_dir = Path(__file__).parent.resolve()
        root_dir = script_dir.parent
        user_in_script_dir = Path.cwd().resolve() == script_dir
        if user_in_script_dir:
            os.chdir(root_dir)
        elif Path.cwd().resolve() != root_dir:
            raise RuntimeError(
                "mock_snakemake has to be run from the repository root"
                f" {root_dir} or scripts directory {script_dir}"
            )

    configure_logging(snakemake)
    if "sector_opts" in snakemake.wildcards.keys():
        update_config_with_sector_opts(
            snakemake.config, snakemake.wildcards.sector_opts
        )

    opts = snakemake.wildcards.opts
    if "sector_opts" in snakemake.wildcards.keys():
        opts += "-" + snakemake.wildcards.sector_opts
    opts = [o for o in opts.split("-") if o != ""]
    solve_opts = snakemake.params.solving["options"]

    np.random.seed(solve_opts.get("seed", 123))

    n = pypsa.Network(snakemake.input.network)

    n = prepare_network(
        n,
        solve_opts,
        config=snakemake.config,
        foresight=snakemake.params.foresight,
        planning_horizons=snakemake.params.planning_horizons,
        co2_sequestration_potential=snakemake.params["co2_sequestration_potential"],
    )

    with memory_logger(
            filename=getattr(snakemake.log, "memory", None), interval=30.0  # interval is in seconds
    ) as mem:
        n = solve_network(
            n,
            config=snakemake.config,
            solving=snakemake.params.solving,
            opts=opts,
            log_fn=snakemake.log.solver,
        )

    logger.info(f"Maximum memory usage: {mem.mem_usage}")

    n.meta = dict(snakemake.config, **dict(wildcards=dict(snakemake.wildcards)))
    n.export_to_netcdf(snakemake.output[0])
