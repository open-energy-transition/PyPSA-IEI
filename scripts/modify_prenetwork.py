# Adapted from
# Michael Lindner, Toni Seibold, Julian Geis, Tom Brown (2025).
# Kopernikus-Projekt Ariadne - Gesamtsystemmodell PyPSA-DE.
# https://github.com/PyPSA/pypsa-de

import logging

import pandas as pd

import pypsa

logger = logging.getLogger(__name__)

from prepare_sector_network import (
    prepare_costs,
    lossy_bidirectional_links,
)

def add_reversed_pipes(df):
    df_rev = df.copy().rename({"bus0": "bus1", "bus1": "bus0"}, axis=1)
    df_rev.index = df_rev.index + "-reversed"
    return pd.concat([df, df_rev], sort=False)


def reduce_capacity(targets, origins, carrier, origin_attr="removed_gas_cap", target_attr="p_nom", conversion_rate=1):
    """
    Reduce the capacity of pipes in a dataframe based on specified criteria.

    Parameters
    ----------
    target : pd.DataFrame
        The dataframe containing pipelines from which to reduce capacitiy.
    origin : pd.DataFrame
        The dataframe containing data about added pipelines.
    carrier : str
        The carrier of the pipelines.
    origin_attr : str (optional)
        The column name in `origin` representing the original capacity of the pipelines. Defaults to "removed_gas_cap".
    target_attr : str (optional)
        The column name in `target` representing the target capacity to be modified. Defaults to "p_nom".
    conversion_rate : float (optional)
        The conversion rate to reduce the capacity. Defaults to 1.

    Returns
    ----------
        pd.DataFrame: The modified dataframe with reduced pipe capacities.
    """

    targets = targets.copy()

    def apply_cut(row):
        match = targets[
            (targets.bus0 == row.bus0 + " " + carrier) & 
            (targets.bus1 == row.bus1 + " " + carrier)
        ].sort_index()
        cut = row[origin_attr] * conversion_rate
        for idx, target_row in match.iterrows():
            if cut <= 0:
                break
            target_value = target_row[target_attr]
            reduction = min(target_value, cut)
            targets.at[idx, target_attr] -= reduction
            cut -= reduction

    origins.apply(apply_cut, axis=1)
    return targets


def add_wasserstoff_kernnetz(n, wkn, costs):
    """
    Add links for the hydrogen core network.

    Parameters
    ----------
    n : pypsa.Network
        A prenetwork after the brownfield stage for adding the hydrogen pipelines from grid plans.
    wkn : pd.DataFrame
        Dataframe containing planned pipelines from the German hydrogen core network (Wasserstoffkernnetz) and the
        H2-Infrastructure Map.
    costs : pd.DataFrame
        Dataframe with PyPSA cost parameter collection
    """
    logger.info("adding wasserstoff kernnetz")

    investment_year = int(snakemake.wildcards.planning_horizons)

    # get previous planning horizon
    planning_horizons = snakemake.config["scenario"]["planning_horizons"]
    i = planning_horizons.index(int(snakemake.wildcards.planning_horizons))
    previous_investment_year = int(planning_horizons[i - 1]) if i != 0 else 2015

    # use only pipes added since the previous investment period
    wkn_new = wkn.query("build_year > @previous_investment_year & build_year <= @investment_year")
    strategies = {
        "bus0": "first",
        "bus1": "first",
        "build_year":"mean",
        "p_nom": "sum",
        "p_nom_diameter": "sum",
        "max_pressure_bar": "mean",
        "diameter_mm": "mean",
        "length": "mean",
        "name": " ".join,
        "p_min_pu": "min",
        "removed_gas_cap": "sum",
    }
    wkn_new = wkn_new.groupby(wkn_new.index).agg(strategies)
    # reduce the gas network capacity of retrofitted lines from kernnetz
    # which is build up to the current period
    wkn_to_date = wkn.query("build_year <= @investment_year")
    wkn_to_date = wkn_to_date.groupby(wkn_to_date.index).agg(strategies)
    gas_pipes = n.links.query("carrier == 'gas pipeline'")
    if not gas_pipes.empty:
        res_gas_pipes = reduce_capacity(
            gas_pipes,
            add_reversed_pipes(wkn_to_date),
            carrier="gas",
        )
        n.links.loc[n.links.carrier == "gas pipeline", "p_nom"] = res_gas_pipes["p_nom"]
    if not wkn_new.empty:

        names = wkn_new.index + f"-kernnetz-{investment_year}"

        # add kernnetz to network
        n.madd(
            "Link",
            names,
            bus0=wkn_new.bus0.values + " H2",
            bus1=wkn_new.bus1.values + " H2",
            p_min_pu=-0.8,
            p_max_pu=0.8,
            p_nom_extendable=False,
            p_nom=wkn_new.p_nom.values,
            build_year=wkn_new.build_year.values,
            length=wkn_new.length.values,
            capital_cost=costs.at["H2 (g) pipeline", "fixed"] * wkn_new.length.values,
            carrier="H2 pipeline (Kernnetz)",
            lifetime=costs.at["H2 (g) pipeline", "lifetime"],
        )

        # add reversed pipes and losses
        losses = snakemake.config["sector"]["transmission_efficiency"]["H2 pipeline"]
        lossy_bidirectional_links(n, "H2 pipeline (Kernnetz)", losses, subset=names)

        n.links['reversed'] = n.links['reversed'].replace({0: False, 1: True})

    # reduce H2 retrofitting potential from gas network for all kernnetz
    # pipelines which are being build in total (more conservative approach)
    if not wkn.empty and snakemake.config["sector"]["H2_retrofit"]:

        conversion_rate = snakemake.config["sector"]["H2_retrofit_capacity_per_CH4"]

        retrofitted_b = (
            n.links.carrier == "H2 pipeline retrofitted"
        ) & n.links.index.str.contains(str(investment_year))
        h2_pipes_retrofitted = n.links.loc[retrofitted_b]

        if not h2_pipes_retrofitted.empty:
            res_h2_pipes_retrofitted = reduce_capacity(
                h2_pipes_retrofitted,
                add_reversed_pipes(wkn),
                carrier="H2",
                target_attr="p_nom_max",
                conversion_rate=conversion_rate,
            )
            n.links.loc[retrofitted_b, "p_nom_max"] = res_h2_pipes_retrofitted["p_nom_max"]

    extend_after_year = snakemake.params.optimize_after

    # open_for_optimization can be true or a year. In case of true, the following if clauses are skipped and all
    # pipelines remain extendable. In case of a year, optimization of the lines and links is only allowed after this
    # year.
    if (type(extend_after_year) == int) & (investment_year <= extend_after_year):
        idx_pipes = n.links.query('carrier.str.contains("H2 pipeline") & p_nom_extendable').index
        n.links.loc[idx_pipes, 'p_nom_extendable'] = False
        n.links.loc[idx_pipes, 'p_nom'] = n.links.loc[idx_pipes, 'p_nom_min']



if __name__ == "__main__":
    if "snakemake" not in globals():
        import os
        import sys

        path = "../submodules/pypsa-eur/scripts"
        sys.path.insert(0, os.path.abspath(path))
        from _helpers import mock_snakemake
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        snakemake = mock_snakemake(
            "modify_prenetwork",
            configfile=r'...',      # add the path to the config file with which you want to debug
            planning_horizons = '2030'
        )



    n = pypsa.Network(snakemake.input.network)
    nhours = n.snapshot_weightings.generators.sum()
    nyears = nhours / 8760

    costs = prepare_costs(
        snakemake.input.costs,
        snakemake.params.costs,
        nyears,
    )

    if snakemake.config["policy_plans"]["wasserstoff_kernnetz"]["enable"]:
        fn = snakemake.input.wkn
        wkn = pd.read_csv(fn, index_col=0)
        add_wasserstoff_kernnetz(n, wkn, costs)
        logger.info("Adding Ariadne-specific functionality")

    if snakemake.config["sensitivities"]["no_gas_no_oil"]:
        fossil_carriers = ['residential rural gas boiler', 'services rural gas boiler',
                            'residential urban decentral gas boiler',
                            'services urban decentral gas boiler', 'urban central gas boiler',
                            'residential rural oil boiler', 'services rural oil boiler',
                            'residential urban decentral oil boiler',
                            'services urban decentral oil boiler'
                            'residential rural micro gas CHP',
                            'services rural micro gas CHP',
                            'residential urban decentral micro gas CHP',
                            'services urban decentral micro gas CHP',
                            'urban central gas CHP',
                            'urban central gas CHP CC',
                            'OCGT',
                            'CCGT',
                            'allam',
                            'residential rural oil boiler', 'services rural oil boiler',
                            'residential urban decentral oil boiler',
                            'services urban decentral oil boiler'
                            ]
        n.mremove("Link", n.links.query('carrier.isin(@fossil_carriers) & (build_year>=2020)').index)
        if int(snakemake.wildcards.planning_horizons) == 2050:
            n.remove("Generator", "EU oil")

    if snakemake.config["sensitivities"]["expensive_compensation"]:
        co2_carriers = ['DAC', 'solid biomass for industry CC', 'biogas to gas CC',
                        'urban central solid biomass CHP CC', 'BioSNG', 'biomass to liquid', 'biogas to gas']
        co2_idx = n.links.query('carrier.isin(@co2_carriers)').index
        n.links.loc[co2_idx, 'capital_cost'] = n.links.loc[co2_idx, 'capital_cost'] * 1.5

    n.export_to_netcdf(snakemake.output.network)
