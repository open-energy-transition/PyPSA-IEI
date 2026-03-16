import itertools

import pandas as pd

from energy_balance_dictionaries import get_components_for_carrier



def calculate_internal_transmission_losses(n, countries):
    """
    Calculates internal AC- and DC-transmission-losses for every
    country in given cluster.

    Parameters
    ----------
    n : pypsa.Network
        pypsa network
    countries : list of str
        list (str) of cluster regions

    Returns
    -------
    pd.Series
        pd.series with AC-transmission-losses
    pd.Series
        pd.series with DC-transmission-losses
    """
    # Initialize pd.series + get snapshot
    ac_transmission_losses = pd.Series(index=countries)
    dc_transmission_losses = pd.Series(index=countries)
    snapshots = n.snapshot_weightings.generators

    # Calculate AC- + DC-transmission losses for every country
    for country in countries:
        # DC
        idx_DC_internal = n.links[
            (n.links.carrier == "DC")
            & (n.links.bus0.str[:2] == country)
            & (n.links.bus1.str[:2] == country)
        ].index
        e_DC_out = (
            n.links_t.p0[idx_DC_internal].mul(snapshots, axis=0).sum().sum()
        )
        e_DC_in = (
            n.links_t.p1[idx_DC_internal].mul(snapshots, axis=0).sum().sum()
        )
        # AC
        idx_AC_internal = n.lines[
            (n.lines.bus0.str[:2] == country)
            & (n.lines.bus1.str[:2] == country)
        ].index
        e_AC_out = (
            n.lines_t.p0[idx_AC_internal].mul(snapshots, axis=0).sum().sum()
        )
        e_AC_in = (
            n.lines_t.p1[idx_AC_internal].mul(snapshots, axis=0).sum().sum()
        )
        # Fill series
        ac_transmission_losses[country] = -(e_AC_in + e_AC_out)
        dc_transmission_losses[country] = -(e_DC_in + e_DC_out)

    return ac_transmission_losses, dc_transmission_losses


def calculate_crossborder_transmission_losses(n, loc_list, geo_resolution):
    """
    Calculates cross border AC- and DC-transmission-losses for every
    country in given cluster or country. (geo_resolution).


    Parameters
    ----------
    n : pypsa.Network
        pypsa network
    loc_list : list of str
        list (str) of country or cluster
    geo_resolution : str
        str of georesolution ('national', 'cluster')

    Returns
    -------
    list of pd.Series
        List containing AC transmission losses and DC transmission
        losses per country/cluster.
    """
    # When aggregating data from several countries/clusters store this in a
    # dataframe and use it when creating local
    # balances
    if geo_resolution == "national":
        nchar = 2
    else:
        nchar = 5
    # Initialize pd.series
    row_index_names = ["p0_location", "p1_location"]
    indices = [(c, comp) for c, comp in itertools.product(loc_list, loc_list)]
    series_index = pd.MultiIndex.from_tuples(indices, names=row_index_names)
    ac_transmission_losses = pd.Series(index=series_index)
    dc_transmission_losses = pd.Series(index=series_index)

    for element in loc_list:
        shortlist = loc_list[:]
        # for each country only consider all lines and links
        # leaving the country (to avoid double counting)
        # (inner country links are considered only once too)

        # Calculation for DC
        idx_DC_out_of = n.links[
            (n.links.carrier == "DC")
            & (n.links.bus0.str[:nchar] == element)
            & (n.links.bus1.str[:nchar].isin(shortlist))
        ].index
        snapshots = n.snapshot_weightings.generators
        e_DC_out = n.links_t.p0[idx_DC_out_of].mul(snapshots, axis=0).sum()
        e_DC_in = n.links_t.p1[idx_DC_out_of].mul(snapshots, axis=0).sum()
        DC_losses_vals = -(e_DC_in + e_DC_out)
        DC_idx_names = n.links.bus1[idx_DC_out_of]
        DC_losses = pd.DataFrame(
            {
                "outgoing": element,
                "location": DC_idx_names,
                "values": DC_losses_vals,
            }
        )
        DC_losses = DC_losses.set_index(["outgoing", "location"], append=True)
        if not DC_losses.empty:
            DC_losses = DC_losses.groupby(
                [
                    DC_losses.index.get_level_values(1),
                    DC_losses.index.get_level_values(2).str[:nchar],
                ]
            ).sum()
            dc_transmission_losses.update(DC_losses["values"])

        # Calculation for AC
        idx_AC_out_of = n.lines[
            (n.lines.bus0.str[:nchar] == element)
            & (n.lines.bus1.str[:nchar].isin(shortlist))
        ].index
        e_AC_out = n.lines_t.p0[idx_AC_out_of].mul(snapshots, axis=0).sum()
        e_AC_in = n.lines_t.p1[idx_AC_out_of].mul(snapshots, axis=0).sum()
        AC_losses_vals = -(e_AC_in + e_AC_out)
        AC_idx_names = n.lines.bus1[idx_AC_out_of]
        AC_losses = pd.DataFrame(
            {
                "outgoing": element,
                "location": AC_idx_names,
                "values": AC_losses_vals,
            }
        )
        AC_losses = AC_losses.set_index(["outgoing", "location"], append=True)
        if not AC_losses.empty:
            AC_losses = AC_losses.groupby(
                [
                    AC_losses.index.get_level_values(1),
                    AC_losses.index.get_level_values(2).str[:nchar],
                ]
            ).sum()
            ac_transmission_losses.update(AC_losses["values"])

    return [ac_transmission_losses, dc_transmission_losses]


def get_relevant_cross_border_losses(
    cross_border_losses, loc_bal, loc_str, extra_comps
):
    """
    Reduce data by irrelevant cross border losses.

    Parameters
    ----------
    cross_border_losses : dict
        dict with cross border losses {year: {scen: list with cross
        border losses ((country1, country2), loss)
    loc_bal : pd.DataFrame
        df with data of local balances per region
    loc_str : list of str
        list (str) with cluster abbreviations
    extra_comps : list of str
        list (str) with additional losses

    Returns
    -------
    pd.DataFrame
        df reduced by irrelevant cross border losses
    """
    # Extract years and scenarios + get cross border losses
    years = list(cross_border_losses.keys())
    scens = list(cross_border_losses[years[0]].keys())
    for y in years:
        cross_border_losses_year = cross_border_losses[y]
        for s in scens:
            loss_list = cross_border_losses_year[s]

            correction = []
            for transmission_losses in loss_list:
                # Get losses in between loc_str countries/clusters:
                vals = transmission_losses[
                    transmission_losses.index.get_level_values(0).isin(loc_str)
                    & transmission_losses.index.get_level_values(1).isin(
                        loc_str
                    )
                ]
                # Inner country/cluster losses: national resolution:
                # already considered, cluster resolution: =0
                # --> ignore inner country losses here:
                vals = vals[
                    vals.index.get_level_values(0)
                    != vals.index.get_level_values(1)
                ]
                correction.append(vals.sum() * 1e-6)
            # Prepare df to remove vals from import
            # and add them to transmission losses
            # Add to transmission losses:
            if len(extra_comps) == 1:
                comp = extra_comps[0]
                loc_bal.loc[
                    loc_bal.index.get_level_values(1) == comp, (s, y)
                ] += correction.sum()
            else:
                for comp in extra_comps:
                    if "AC" in comp:
                        loc_bal.loc[
                            loc_bal.index.get_level_values(1) == comp, (s, y)
                        ] += correction[0]
                    elif "DC" in comp:
                        loc_bal.loc[
                            loc_bal.index.get_level_values(1) == comp, (s, y)
                        ] += correction[1]
                    else:  # else helper_to_check_completeness is not
                        # going to be empty
                        print(
                            f"Warning: did not add {comp} "
                            "to local balance df."
                        )

            # Remove transmission losses from import
            keys_with_value = list(
                loc_bal.loc[loc_bal.index.get_level_values(2) == "Import"]
                .index.get_level_values(1)
                .unique()
            )
            if len(keys_with_value) == 1:
                comp = keys_with_value[0]
                loc_bal.loc[
                    loc_bal.index.get_level_values(1) == comp, (s, y)
                ] -= correction.sum()
            else:
                for comp in keys_with_value:
                    if "AC" in comp:
                        loc_bal.loc[
                            loc_bal.index.get_level_values(1) == comp, (s, y)
                        ] -= correction[0]
                    elif "DC" in comp:
                        loc_bal.loc[
                            loc_bal.index.get_level_values(1) == comp, (s, y)
                        ] -= correction[1]
                    else:
                        print(
                            f"Warning: did not remove {comp} "
                            "from imports in df."
                        )

    return loc_bal


def get_values_for_balance(
    red_en_balance,
    comp_type,
    sub_component_typ_dict,
    geo_resolution,
    year,
    helper_to_check_completeness,
    extra_comps,
    carrier,
):
    """
    Gives values for balance related to sub component types.

    Parameters
    ----------
    red_en_balance : pd.Series
        pd.series with energy balance data (index, e.g.: (Load/
        agriculture electricity/low voltage))
    comp_type : str
        str of component type (e.g. 'Offshore Wind')
    sub_component_typ_dict : dict
        dict with nice names from energy_balance_dictionaries.py
        ({name: nice name})
    geo_resolution : str
        str of georesolution ('national', 'cluster')
    year : str
        str of year
    helper_to_check_completeness : dict
        dict  with nice names to check completeness
    extra_comps : list of str
        list (str) of extra components
    carrier : str
        str of carrier

    Returns
    -------
    pd.Series
        pd.series with component values
    dict
        dict of updated helper_to_check_completeness
    """
    # Proove sub component types
    keys_with_value = [
        key
        for key, value in sub_component_typ_dict.items()
        if value == comp_type
    ]
    if not keys_with_value:  # list is empty:should not be the case
        print(
            f"Warning: {comp_type} does not have a subcomponent in "
            "sub_component_typ_dict."
        )

    # If values are stored and possible remove sub component from
    # helper_to_check_completeness
    else:
        series_list = []
        for sub_key in keys_with_value:
            if bool(sub_key in helper_to_check_completeness.keys()) & bool(
                sub_key not in extra_comps
            ):
                helper_to_check_completeness.pop(sub_key)
            elif sub_key not in helper_to_check_completeness.keys():
                print(
                    f"Warning: List of components that are drawn for the "
                    f"energy balance might be incomplete (see {sub_key})"
                )
                print(
                    f"Warning: Incorrect list: {sub_key} is not an expected "
                    f"component of red_en_balance/not "
                    f"a part of sub_component_typ_dict."
                )

            # Get data from red_en_balance
            if type(red_en_balance) is pd.Series:
                loc_series = red_en_balance.loc[
                    :, red_en_balance.index.get_level_values(1) == sub_key
                ]
            if type(red_en_balance) is pd.DataFrame:
                loc_series = red_en_balance.loc[
                    red_en_balance.index.get_level_values(1) == sub_key
                ]
            if loc_series.empty & bool(sub_key not in extra_comps):
                # In case of a combination of carriers (as in electricity)
                # the warning might be unnecessary:
                _, local_sub_component_type_dict, _ = (
                    get_components_for_carrier(carrier)
                )
                if sub_key in list(local_sub_component_type_dict.keys()):
                    print(
                        f"Warning: {sub_key} not found for year {year} in "
                        f"index of red_en_balance for {carrier}."
                    )

            # Append values
            series_list.append(loc_series)
        values = pd.concat(series_list)

    if geo_resolution == "national":
        # country level grouping
        return (
            values.groupby(values.index.get_level_values(3).str[:2]).sum(),
            helper_to_check_completeness,
        )
    else:
        return (
            values.groupby(values.index.get_level_values(3).str[:5]).sum(),
            helper_to_check_completeness,
        )
