# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Open Energy Transition GmbH and contributors
#
# SPDX-License-Identifier: MIT
from pathlib import Path
from typing import Dict, List

import pandas as pd
import pypsa
from common import log

CARRIER_NAMES = {"AC": "electricity", "H2": "hydrogen"}


def extract_marginal_prices(
    networks_year: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    scenarios: List[str],
    carriers: List[str] = ["AC", "H2"],
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Extract nodal marginal prices for selected carriers from all networks.

    Parameters
    ----------
    networks_year : dict
        Nested dict {year: {scenario: pypsa.Network}}.
    years : list of str
        Planning years to process.
    scenarios : list of str
        Scenario keys matching the outer dict.
    carriers : list of str, optional
        Bus carriers whose marginal prices are extracted.
        Defaults to ["AC", "H2"].

    Returns
    -------
    dict
        Nested dict {carrier: {bus: pd.DataFrame}} where each DataFrame
        has a MultiIndex(scenario, year) as columns and time steps as the
        index.
    """
    log(f"Extracting marginal prices for carriers: {', '.join(carriers)}")
    # pieces[carrier][bus] accumulates one narrow DataFrame per (scenario, year)
    pieces: Dict[str, Dict[str, list]] = {c: {} for c in carriers}

    for scenario in scenarios:
        for year in years:
            n = networks_year[year][scenario]
            for carrier in carriers:
                buses = n.buses.index[n.buses.carrier == carrier]
                # reindex so missing buses become NaN rather than KeyError
                mp = n.buses_t.marginal_price.reindex(columns=buses)
                for bus in buses:
                    col_label = (scenario, year)
                    s = mp[[bus]].rename(columns={bus: col_label})
                    pieces[carrier].setdefault(bus, []).append(s)

    prices: Dict[str, Dict[str, pd.DataFrame]] = {}
    for carrier, bus_dict in pieces.items():
        prices[carrier] = {}
        for bus, dfs in bus_dict.items():
            combined = pd.concat(dfs, axis=1)
            combined.columns = pd.MultiIndex.from_tuples(
                combined.columns, names=["scenario", "year"]
            )
            prices[carrier][bus] = combined

    return prices


def write_marginal_prices(
    prices: Dict[str, Dict[str, pd.DataFrame]],
    resultdir: Path,
    carriers: List[str] = ["AC", "H2"],
) -> None:
    """
    Write marginal price DataFrames to Excel files, one file per carrier.

    Parameters
    ----------
    prices : dict
        Output of get_marginal_prices or aggregate_marginal_prices.
    resultdir : pathlib.Path
        Directory where the output files are saved.
    carriers : list of str, optional
        Carriers to write out.

    Returns
    -------
    None
    """

    for carrier in carriers:
        if carrier not in prices:
            log(f"Carrier {carrier} not found in prices, skipping.")
            continue
        label = CARRIER_NAMES.get(carrier, carrier)
        filepath = resultdir / f"marginal_prices_{label}.xlsx"
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            for bus, df in prices[carrier].items():
                df.to_excel(writer, sheet_name=str(bus))
        log(f"Saved marginal price for {carrier} to {filepath.name}")


def get_marginal_prices(
    networks_year: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    scenarios: List[str],
    scenario_colors: Dict[str, str],
    resultdir: Path,
    carriers: List[str] = ["AC", "H2"],
) -> None:
    """
    Top-level entry point called from analysis_main.py.

    Orchestrates extraction and writing of marginal prices for the given carriers.

    Parameters
    ----------
    networks_year : dict
        Nested dict {year: {scenario: pypsa.Network}}.
    years : list of str
        Planning years to process.
    scenarios : list of str
        Scenario keys matching the outer dict.
    scenario_colors : dict
        Mapping {scenario: hex color string} for plots.
    resultdir : pathlib.Path
        Directory where output files and figures are saved.
    carriers : list of str, optional
        Bus carriers to analyse. Defaults to ["AC", "H2"].

    Returns
    -------
    None
    """
    prices = extract_marginal_prices(networks_year, years, scenarios, carriers)
    write_marginal_prices(prices, resultdir, carriers)
