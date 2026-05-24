# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Open Energy Transition GmbH and contributors
#
# SPDX-License-Identifier: MIT
from pathlib import Path
from typing import Dict, List

import pandas as pd
import pypsa
from common import log


def extract_grid_emission_factors(
    networks_year: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    scenarios: List[str],
) -> Dict[str, pd.DataFrame]:
    """
    Compute hourly average grid emission factors per AC node.

    The emission factor at node b at time t is the generation-weighted average:

        EF_b(t) = Σ_g [ p_g(t) · co2_g ] / Σ_g [ p_g(t) ]

    where the sum is over all generators connected to bus b, co2_g is the
    CO2 emission intensity [tCO2/MWh_el] of the generator's carrier, and
    p_g(t) is the dispatch in MW. Hours with no local generation yield NaN.

    Parameters
    ----------
    networks_year : dict
        Nested dict {year: {scenario: pypsa.Network}}.
    years : list of str
        Planning years to process.
    scenarios : list of str
        Scenario keys matching the outer dict.

    Returns
    -------
    dict
        {bus: pd.DataFrame} where each DataFrame has MultiIndex(scenario, year)
        as columns and hourly time steps as index.
        Values are emission factors [tCO2/MWh_el].
    """
    pieces: Dict[str, list] = {}

    for scenario in scenarios:
        for year in years:
            n = networks_year[year][scenario]
            ac_buses = n.buses.index[n.buses.carrier == "AC"]
            co2_atm_buses = n.buses.index[n.buses.carrier == "co2"]

            # --- Links: exact per-link CO2 and electricity dispatch ---------------
            # Exclude links whose bus0 is an AC bus (HVDC, back-to-back converters,
            # etc.) — those are transmission, not local generation. Including them
            # would inject negative electricity into the denominator on reverse flow.
            bus0_is_ac = n.links["bus0"].isin(ac_buses)

            # co2_port_col: the single port per link that connects to the co2
            # atmosphere bus. CCS plants also have a "co2 stored" port, but its bus
            # has a different carrier so it is never matched here.
            co2_port_col: Dict[str, str] = {}  # {link: "p2" / "p3" / ...}
            ac_port_col: Dict[str, str] = {}  # {link: "p1" / "p2" / ...}

            for col in [
                c for c in n.links.columns if c.startswith("bus") and c[3:].isdigit()
            ]:
                port = col[3:]
                if port == "0":
                    continue  # bus0 is always the fuel/input side
                mask_co2 = n.links[col].isin(co2_atm_buses)
                # Only AC outputs for links that do NOT start from an AC bus
                mask_ac = n.links[col].isin(ac_buses) & ~bus0_is_ac
                for link in n.links.index[mask_co2]:
                    co2_port_col[link] = "p" + port
                for link in n.links.index[mask_ac]:
                    ac_port_col[link] = "p" + port

            # Links that have at least one AC output port (local generation only)
            ac_links = n.links[n.links.index.isin(ac_port_col)]

            # Hourly electricity [MW] per link.
            # Output port flows are negative in PyPSA → negate.
            # Clip to ≥ 0 as a safety net against edge cases (e.g. curtailment artefacts).
            p_el = pd.DataFrame(0.0, index=n.snapshots, columns=ac_links.index)
            for link, p_col in ac_port_col.items():
                if link in ac_links.index:
                    src = getattr(n.links_t, p_col, None)
                    if src is not None and link in src.columns:
                        p_el[link] = (-src[link]).clip(lower=0)

            # AC bus for each link (the bus connected to the AC port)
            ac_port_bus = {
                link: n.links.loc[link, "bus" + p_col[1:]]
                for link, p_col in ac_port_col.items()
                if link in ac_links.index
            }
            link_ac_bus = pd.Series(ac_port_bus)

            # Hourly CO2 [tCO2/h] per link — the single co2-atmosphere port.
            # Output port flows are negative in PyPSA → negate to get positive emissions.
            p_co2 = pd.DataFrame(0.0, index=n.snapshots, columns=ac_links.index)
            for link, p_col in co2_port_col.items():
                if link in ac_links.index:
                    src = getattr(n.links_t, p_col, None)
                    if src is not None and link in src.columns:
                        p_co2[link] = -src[link]

            # Aggregate to AC node
            el_by_bus = p_el.T.groupby(link_ac_bus).sum().T
            co2_by_bus = p_co2.T.groupby(link_ac_bus).sum().T

            # --- Generators: static co2_emissions parameter is exact per-generator
            gen_co2_ef = n.generators.carrier.map(n.carriers.co2_emissions).fillna(0)
            gen_dispatch = n.generators_t.p.reindex(
                columns=n.generators.index, fill_value=0
            )
            gen_el_by_bus = (
                gen_dispatch.T.groupby(n.generators.bus)
                .sum()
                .T.reindex(columns=ac_buses, fill_value=0)
            )
            gen_co2_by_bus = (
                gen_dispatch.multiply(gen_co2_ef, axis=1)
                .T.groupby(n.generators.bus)
                .sum()
                .T.reindex(columns=ac_buses, fill_value=0)
            )

            # --- StorageUnits: hydro and PHS, positive p = dispatch
            ac_sus = n.storage_units[n.storage_units.bus.isin(ac_buses)]
            su_dispatch = n.storage_units_t.p.reindex(
                columns=ac_sus.index, fill_value=0
            ).clip(
                lower=0
            )  # keep generation only, discard charging
            su_el_by_bus = (
                su_dispatch.T.groupby(ac_sus.bus)
                .sum()
                .T.reindex(columns=ac_buses, fill_value=0)
            )

            # --- Combine and compute EF per node ----------------------------------
            total_el = (
                el_by_bus.reindex(columns=ac_buses, fill_value=0)
                + gen_el_by_bus
                + su_el_by_bus
            )
            total_co2 = (
                co2_by_bus.reindex(columns=ac_buses, fill_value=0) + gen_co2_by_bus
            )

            # NaN when no local generation at all
            ef = total_co2 / total_el.replace(0, float("nan"))
            # Treat near-zero values as zero (numerical noise threshold)
            ef = ef.where(ef.abs() > 1e-4, 0)

            col_label = (scenario, year)
            for bus in ac_buses:
                s = ef[[bus]].rename(columns={bus: col_label})
                pieces.setdefault(bus, []).append(s)

    emission_factors: Dict[str, pd.DataFrame] = {}
    for bus, dfs in pieces.items():
        combined = pd.concat(dfs, axis=1)
        combined.columns = pd.MultiIndex.from_tuples(
            combined.columns, names=["scenario", "year [tCO2/MWh_el]"]
        )
        emission_factors[bus] = combined

    log("Extracted hourly grid emission factors for all AC nodes")
    return emission_factors


def write_grid_emission_factors(
    emission_factors: Dict[str, pd.DataFrame],
    resultdir: Path,
) -> None:
    """
    Write grid emission factor DataFrames to an Excel file.

    One sheet per AC bus. Columns are MultiIndex(scenario, year),
    rows are hourly time steps. Values in [tCO2/MWh_el].

    Parameters
    ----------
    emission_factors : dict
        Output of extract_grid_emission_factors.
    resultdir : pathlib.Path
        Directory where the output file is saved.

    Returns
    -------
    None
    """
    filepath = resultdir / "grid_emission_factors.xlsx"
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for bus, df in sorted(emission_factors.items()):
            df.to_excel(writer, sheet_name=str(bus))
    log(f"Saved grid emission factors to {filepath.name}")


def analyze_grid_emission_factors(
    networks_year: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    scenarios: List[str],
    resultdir: Path,
) -> None:
    """
    Top-level entry point called from analysis_main.py.

    Parameters
    ----------
    networks_year : dict
        Nested dict {year: {scenario: pypsa.Network}}.
    years : list of str
        Planning years to process.
    scenarios : list of str
        Scenario keys matching the outer dict.
    resultdir : pathlib.Path
        Directory where the output Excel file is saved.

    Returns
    -------
    None
    """
    log("Starting: analyze_grid_emission_factors")
    emission_factors = extract_grid_emission_factors(networks_year, years, scenarios)
    write_grid_emission_factors(emission_factors, resultdir)
    log("Done: analyze_grid_emission_factors")
