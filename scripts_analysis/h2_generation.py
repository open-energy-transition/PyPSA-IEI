# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: Open Energy Transition GmbH and contributors
#
# SPDX-License-Identifier: MIT
from pathlib import Path
from typing import Dict, List

import pandas as pd
import pypsa
from common import log

# Technologies that produce H2, in display order.
H2_PRODUCERS = ["H2 Electrolysis", "SMR", "SMR CC"]


def extract_h2_metrics(
    networks: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    scenarios: List[str],
) -> pd.DataFrame:
    """
    Compute annual H2 production and full-load hours per technology and node.

    Uses n.statistics.energy_balance to obtain annually-weighted generation
    for each H2 producer (H2 Electrolysis, SMR, SMR CC) at each H2 bus.
    Full-load hours = annual generation / optimised H2 output capacity.
    Average FLH = total generation across technologies / total capacity.

    Parameters
    ----------
    networks : dict
        Nested dict {year: {scenario: pypsa.Network}}.
    years : list of str
        Planning years to process.
    scenarios : list of str
        Scenario keys matching the outer dict.

    Returns
    -------
    pd.DataFrame
        MultiIndex index (metric, node), MultiIndex columns (scenario, year).
        Row order: H2 generation per technology, Total, FLH per technology, Average.
    """
    records = {}  # {(scenario, year): {(metric, node): value}}

    for scenario in scenarios:
        for year in years:
            n = networks[year][scenario]
            eb = n.statistics.energy_balance(aggregate_bus=False)
            h2_buses = n.buses.index[n.buses.carrier == "H2"]
            rec = {}

            gen_by_carrier = {}
            cap_by_carrier = {}

            for carrier in H2_PRODUCERS:
                # energy_balance index: (component, carrier, bus) — keep supply only
                s = eb.loc[pd.IndexSlice[:, carrier, :]]
                s = s[s.index.get_level_values(-1).isin(h2_buses)]
                s = s[s > 0].groupby(level=-1).sum()
                gen_by_carrier[carrier] = s
                for node, val in s.items():
                    rec[("H2 generation [GWh_H2]", carrier, node)] = round(val / 1e3, 2)

                # H2 output capacity per bus: p_nom_opt * efficiency, grouped by bus1
                links = n.links[n.links.carrier == carrier]
                cap = (links.p_nom_opt * links.efficiency).groupby(links["bus1"]).sum()
                cap_by_carrier[carrier] = cap

            # Total generation per node
            nonempty = [s for s in gen_by_carrier.values() if not s.empty]
            total_gen = (
                pd.concat(nonempty).groupby(level=0).sum()
                if nonempty
                else pd.Series(dtype=float)
            )
            for node, val in total_gen.items():
                rec[("H2 generation [GWh_H2]", "Total", node)] = round(val / 1e3, 2)

            # FLH per carrier and average (total gen / total cap)
            for carrier in H2_PRODUCERS:
                gen = gen_by_carrier[carrier]
                cap = cap_by_carrier[carrier]
                if gen.empty or cap.empty:
                    continue
                flh = (gen / cap.replace(0, float("nan"))).round(1)
                for node, val in flh.items():
                    rec[("Full-load hours [h/a]", carrier, node)] = val

            records[(scenario, year)] = rec

    df = pd.DataFrame(records)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["scenario", "year"])
    df.index = pd.MultiIndex.from_tuples(
        df.index, names=["metric", "technology", "node"]
    )
    log("Extracted H2 generation and full-load hours for all technologies")
    return df


def write_h2_metrics(
    metrics: pd.DataFrame,
    resultdir: Path,
) -> None:
    """
    Write H2 generation and full-load hours to a single Excel file.

    One sheet per H2 bus node. Rows follow the order:
      H2 generation per technology, Total, FLH per technology, Average FLH.
    Columns are MultiIndex (scenario, year).

    Parameters
    ----------
    metrics : pd.DataFrame
        Output of extract_h2_metrics.
    resultdir : pathlib.Path
        Directory where the output file is saved.

    Returns
    -------
    None
    """
    row_order = pd.MultiIndex.from_tuples(
        [("H2 generation [GWh_H2]", c) for c in H2_PRODUCERS]
        + [("H2 generation [GWh_H2]", "Total")]
        + [("Full-load hours [h/a]", c) for c in H2_PRODUCERS],
        names=["metric", "technology"],
    )
    filepath = resultdir / "hydrogen_generation.xlsx"
    all_nodes = metrics.index.get_level_values("node").unique()
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        for node in sorted(all_nodes):
            node_df = metrics.xs(node, level="node")
            node_df.index = node_df.index.rename(["metric", "technology"])
            node_df = node_df.reindex(row_order)
            sheet_name = str(node).removesuffix(" H2")
            node_df.to_excel(writer, sheet_name=sheet_name)
    log(f"Saved H2 metrics to {filepath.name}")


def analyze_h2_generation(
    networks: Dict[str, Dict[str, pypsa.Network]],
    years: List[str],
    scenarios: List[str],
    resultdir: Path,
) -> None:
    """
    Top-level entry point called from analysis_main.py.

    Orchestrates extraction and writing of H2 generation volumes and
    full-load hours for all scenarios and planning years.

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
    log("Starting: analyze_h2_generation")
    metrics = extract_h2_metrics(networks, years, scenarios)
    write_h2_metrics(metrics, resultdir)
    log("Done: analyze_h2_generation")
