# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2017-2024 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

import contextlib
import hashlib
import logging
import os
import re
import urllib
from pathlib import Path

import pandas as pd
import pytz
import requests
import yaml
import numpy as np
from tqdm import tqdm

from linopy import Model
import pypsa.optimization.constraints as cons
import pypsa.optimization.global_constraints as gcons
import pypsa.optimization.variables as vars
from pypsa.pf import _as_snapshots
from pypsa.optimization.optimize import lookup, define_objective

logger = logging.getLogger(__name__)

REGION_COLS = ["geometry", "name", "x", "y", "country"]


def get_opt(opts, expr, flags=None):
    """
    Return the first option matching the regular expression.

    The regular expression is case-insensitive by default.
    """
    if flags is None:
        flags = re.IGNORECASE
    for o in opts:
        match = re.match(expr, o, flags=flags)
        if match:
            return match.group(0)
    return None


def find_opt(opts, expr):
    """
    Return if available the float after the expression.
    """
    for o in opts:
        if expr in o:
            m = re.findall("[0-9]*\.?[0-9]+$", o)
            if len(m) > 0:
                return True, float(m[0])
            else:
                return True, None
    return False, None


# Define a context manager to temporarily mute print statements
@contextlib.contextmanager
def mute_print():
    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull):
            yield


def configure_logging(snakemake, skip_handlers=False):
    """
    Configure the basic behaviour for the logging module.

    Note: Must only be called once from the __main__ section of a script.

    The setup includes printing log messages to STDERR and to a log file defined
    by either (in priority order): snakemake.log.python, snakemake.log[0] or "logs/{rulename}.log".
    Additional keywords from logging.basicConfig are accepted via the snakemake configuration
    file under snakemake.config.logging.

    Parameters
    ----------
    snakemake : snakemake object
        Your snakemake object containing a snakemake.config and snakemake.log.
    skip_handlers : True | False (default)
        Do (not) skip the default handlers created for redirecting output to STDERR and file.
    """
    import logging
    import sys

    kwargs = snakemake.config.get("logging", dict()).copy()
    kwargs.setdefault("level", "INFO")

    if skip_handlers is False:
        fallback_path = Path(__file__).parent.joinpath(
            "..", "logs", f"{snakemake.rule}.log"
        )
        logfile = snakemake.log.get(
            "python", snakemake.log[0] if snakemake.log else fallback_path
        )
        kwargs.update(
            {
                "handlers": [
                    # Prefer the 'python' log, otherwise take the first log for each
                    # Snakemake rule
                    logging.FileHandler(logfile),
                    logging.StreamHandler(),
                ]
            }
        )
    logging.basicConfig(**kwargs)

    # Setup a function to handle uncaught exceptions and include them with their stacktrace into logfiles
    def handle_exception(exc_type, exc_value, exc_traceback):
        # Log the exception
        logger = logging.getLogger()
        logger.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception


def update_p_nom_max(n):
    # if extendable carriers (solar/onwind/...) have capacity >= 0,
    # e.g. existing assets from the OPSD project are included to the network,
    # the installed capacity might exceed the expansion limit.
    # Hence, we update the assumptions.

    n.generators.p_nom_max = n.generators[["p_nom_min", "p_nom_max"]].max(1)


def aggregate_p_nom(n):
    return pd.concat(
        [
            n.generators.groupby("carrier").p_nom_opt.sum(),
            n.storage_units.groupby("carrier").p_nom_opt.sum(),
            n.links.groupby("carrier").p_nom_opt.sum(),
            n.loads_t.p.groupby(n.loads.carrier, axis=1).sum().mean(),
        ]
    )


def aggregate_p(n):
    return pd.concat(
        [
            n.generators_t.p.sum().groupby(n.generators.carrier).sum(),
            n.storage_units_t.p.sum().groupby(n.storage_units.carrier).sum(),
            n.stores_t.p.sum().groupby(n.stores.carrier).sum(),
            -n.loads_t.p.sum().groupby(n.loads.carrier).sum(),
        ]
    )


def aggregate_e_nom(n):
    return pd.concat(
        [
            (n.storage_units["p_nom_opt"] * n.storage_units["max_hours"])
            .groupby(n.storage_units["carrier"])
            .sum(),
            n.stores["e_nom_opt"].groupby(n.stores.carrier).sum(),
        ]
    )


def aggregate_p_curtailed(n):
    return pd.concat(
        [
            (
                (
                    n.generators_t.p_max_pu.sum().multiply(n.generators.p_nom_opt)
                    - n.generators_t.p.sum()
                )
                .groupby(n.generators.carrier)
                .sum()
            ),
            (
                (n.storage_units_t.inflow.sum() - n.storage_units_t.p.sum())
                .groupby(n.storage_units.carrier)
                .sum()
            ),
        ]
    )


def aggregate_costs(n, flatten=False, opts=None, existing_only=False):
    components = dict(
        Link=("p_nom", "p0"),
        Generator=("p_nom", "p"),
        StorageUnit=("p_nom", "p"),
        Store=("e_nom", "p"),
        Line=("s_nom", None),
        Transformer=("s_nom", None),
    )

    costs = {}
    for c, (p_nom, p_attr) in zip(
        n.iterate_components(components.keys(), skip_empty=False), components.values()
    ):
        if c.df.empty:
            continue
        if not existing_only:
            p_nom += "_opt"
        costs[(c.list_name, "capital")] = (
            (c.df[p_nom] * c.df.capital_cost).groupby(c.df.carrier).sum()
        )
        if p_attr is not None:
            p = c.pnl[p_attr].sum()
            if c.name == "StorageUnit":
                p = p.loc[p > 0]
            costs[(c.list_name, "marginal")] = (
                (p * c.df.marginal_cost).groupby(c.df.carrier).sum()
            )
    costs = pd.concat(costs)

    if flatten:
        assert opts is not None
        conv_techs = opts["conv_techs"]

        costs = costs.reset_index(level=0, drop=True)
        costs = costs["capital"].add(
            costs["marginal"].rename({t: t + " marginal" for t in conv_techs}),
            fill_value=0.0,
        )

    return costs


def progress_retrieve(url, file, disable=False):
    if disable:
        urllib.request.urlretrieve(url, file)
    else:
        with tqdm(unit="B", unit_scale=True, unit_divisor=1024, miniters=1) as t:

            def update_to(b=1, bsize=1, tsize=None):
                if tsize is not None:
                    t.total = tsize
                t.update(b * bsize - t.n)

            urllib.request.urlretrieve(url, file, reporthook=update_to)


def mock_snakemake(rulename, configfile, root_dir=None, **wildcards):
    """
    This function is expected to be executed from the 'scripts'-directory of '
    the snakemake project. It returns a snakemake.script.Snakemake object,
    based on the Snakefile.

    If a rule has wildcards, you have to specify them in **wildcards.

    Parameters
    ----------
    rulename: str
        name of the rule for which the snakemake object should be generated
    root_dir: str/path-like
        path to the root directory of the snakemake project
    configfile: str
        configfile in the config folder that contains manual specifications to be used to read the config
    **wildcards:
        keyword arguments fixing the wildcards. Only necessary if wildcards are
        needed.
    """
    import os

    import snakemake as sm
    from packaging.version import Version, parse
    from pypsa.descriptors import Dict
    from snakemake.script import Snakemake
    import shutil
    import yaml

    script_dir = Path(__file__).parent.resolve()
    if root_dir is None:
        root_dir = script_dir.parent
    else:
        root_dir = Path(root_dir).resolve()

    run_name = yaml.safe_load(Path(configfile).read_text())["run"]["name"]
    full_configfile = root_dir / "results" / run_name / "config.yaml"
    user_in_script_dir = Path.cwd().resolve() == script_dir
    if user_in_script_dir:
        os.chdir(root_dir)
    elif Path.cwd().resolve() != root_dir:
        raise RuntimeError(
            "mock_snakemake has to be run from the repository root"
            f" {root_dir} or scripts directory {script_dir}"
        )
    try:
        for p in sm.SNAKEFILE_CHOICES:
            if os.path.exists(p):
                snakefile = p
                break
        kwargs = (
            dict(rerun_triggers=[]) if parse(sm.__version__) > Version("7.7.0") else {}
        )

        shutil.copyfile(full_configfile, "./config/config.yaml")
        workflow = sm.Workflow(snakefile, overwrite_configfiles=configfile, **kwargs)
        workflow.include(snakefile)
        workflow.configfile(configfile)

        workflow.global_resources = {}
        rule = workflow.get_rule(rulename)
        dag = sm.dag.DAG(workflow, rules=[rule])
        wc = Dict(workflow.config["scenario"])
        for this_wildcard, elem in wc.items():
            if len(elem) == 1:
                wc[this_wildcard] = str(elem[0])
        for wc_item, wc_elem in wildcards.items():
            wc[wc_item] = str(wc_elem)
        job = sm.jobs.Job(rule, dag, wc)

        def make_accessable(*ios):
            for io in ios:
                for i in range(len(io)):
                    io[i] = os.path.abspath(io[i])

        make_accessable(job.input, job.output, job.log)
        snakemake = Snakemake(
            job.input,
            job.output,
            job.params,
            job.wildcards,
            job.threads,
            job.resources,
            job.log,
            job.dag.workflow.config,
            job.rule.name,
            None,
        )
        # create log and output dir if not existent
        for path in list(snakemake.log) + list(snakemake.output):
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    finally:
        if user_in_script_dir:
            os.chdir(script_dir)
    return snakemake


def generate_periodic_profiles(dt_index, nodes, weekly_profile, localize=None):
    """
    Give a 24*7 long list of weekly hourly profiles, generate this for each
    country for the period dt_index, taking account of time zones and summer
    time.
    """
    weekly_profile = pd.Series(weekly_profile, range(24 * 7))

    week_df = pd.DataFrame(index=dt_index, columns=nodes)

    for node in nodes:
        timezone = pytz.timezone(pytz.country_timezones[node[:2]][0])
        tz_dt_index = dt_index.tz_convert(timezone)
        week_df[node] = [24 * dt.weekday() + dt.hour for dt in tz_dt_index]
        week_df[node] = week_df[node].map(weekly_profile)

    week_df = week_df.tz_localize(localize)

    return week_df


def parse(infix):
    """
    Recursively parse a chained wildcard expression into a dictionary or a YAML
    object.

    Parameters
    ----------
    list_to_parse : list
        The list to parse.

    Returns
    -------
    dict or YAML object
        The parsed list.
    """
    if len(infix) == 1:
        return yaml.safe_load(infix[0])
    else:
        return {infix.pop(0): parse(infix)}


def update_config_with_sector_opts(config, sector_opts):
    from snakemake.utils import update_config

    for o in sector_opts.split("-"):
        if o.startswith("CF+"):
            infix = o.split("+")[1:]
            update_config(config, parse(infix))


def get_checksum_from_zenodo(file_url):
    parts = file_url.split("/")
    record_id = parts[parts.index("record") + 1]
    filename = parts[-1]

    response = requests.get(f"https://zenodo.org/api/records/{record_id}", timeout=30)
    response.raise_for_status()
    data = response.json()

    for file in data["files"]:
        if file["key"] == filename:
            return file["checksum"]
    return None


def validate_checksum(file_path, zenodo_url=None, checksum=None):
    """
    Validate file checksum against provided or Zenodo-retrieved checksum.
    Calculates the hash of a file using 64KB chunks. Compares it against a
    given checksum or one from a Zenodo URL.

    Parameters
    ----------
    file_path : str
        Path to the file for checksum validation.
    zenodo_url : str, optional
        URL of the file on Zenodo to fetch the checksum.
    checksum : str, optional
        Checksum (format 'hash_type:checksum_value') for validation.

    Raises
    ------
    AssertionError
        If the checksum does not match, or if neither `checksum` nor `zenodo_url` is provided.


    Examples
    --------
    >>> validate_checksum("/path/to/file", checksum="md5:abc123...")
    >>> validate_checksum(
    ...     "/path/to/file",
    ...     zenodo_url="https://zenodo.org/record/12345/files/example.txt",
    ... )

    If the checksum is invalid, an AssertionError will be raised.
    """
    assert checksum or zenodo_url, "Either checksum or zenodo_url must be provided"
    if zenodo_url:
        checksum = get_checksum_from_zenodo(zenodo_url)
    hash_type, checksum = checksum.split(":")
    hasher = hashlib.new(hash_type)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):  # 64kb chunks
            hasher.update(chunk)
    calculated_checksum = hasher.hexdigest()
    assert calculated_checksum == checksum, (
        "Checksum is invalid. This may be due to an incomplete download. Delete the file and re-execute the rule."
    )


def get_bus_counts(n) -> pd.Series:
    all_buses = pd.Series(
        np.hstack([np.ravel(c.df.filter(like="bus")) for c in n.iterate_components()])
    )
    all_buses = all_buses[all_buses != ""]
    return all_buses.value_counts()


def create_model(
    n,
    snapshots=None,
    multi_investment_periods=False,
    transmission_losses=0,
    linearized_unit_commitment=False,
    **kwargs,
):
    """
    Create a linopy.Model instance from a pypsa network.

    This function mirrors `pypsa.optimization.create_model` with a modification
    to the nodal balance constraint formulation. The standard pypsa implementation
    (~v0.27) uses two bus sets (strongly/weakly connected), which can cause high
    memory usage in highly interconnected models. This version groups buses into
    four sets using connectivity thresholds (30, 100, 400), reducing memory
    footprint. See `get_bus_counts` for details.

    Parameters
    ----------
    n : pypsa.Network
    snapshots : list or index slice
        A list of snapshots to optimise, must be a subset of
        network.snapshots, defaults to network.snapshots
    multi_investment_periods : bool, default False
        Whether to optimise as a single investment period or to optimize in multiple
        investment periods. Then, snapshots should be a ``pd.MultiIndex``.
    transmission_losses : int, default 0
    linearized_unit_commitment : bool, default False
        Whether to optimise using the linearised unit commitment formulation or not.
    **kwargs:
        Keyword arguments used by `linopy.Model()`, such as `solver_dir` or `chunk`.

    Returns
    -------
    linopy.model
    """
    sns = _as_snapshots(n, snapshots)
    n._linearized_uc = int(linearized_unit_commitment)
    n._multi_invest = int(multi_investment_periods)
    n.consistency_check()

    model_kwargs = kwargs.get("model_kwargs", {})
    model_kwargs.setdefault("force_dim_names", True)
    n.model = Model(**model_kwargs)
    n.model.parameters = n.model.parameters.assign(snapshots=sns)

    for c, attr in lookup.query("nominal").index:
        vars.define_nominal_variables(n, c, attr)
        vars.define_modular_variables(n, c, attr)

    for c, attr in lookup.query("not nominal and not handle_separately").index:
        vars.define_operational_variables(n, sns, c, attr)
        vars.define_status_variables(n, sns, c)
        vars.define_start_up_variables(n, sns, c)
        vars.define_shut_down_variables(n, sns, c)

    vars.define_spillage_variables(n, sns)
    vars.define_operational_variables(n, sns, "Store", "p")

    if transmission_losses:
        for c in n.passive_branch_components:
            vars.define_loss_variables(n, sns, c)

    for c, attr in lookup.query("nominal").index:
        cons.define_nominal_constraints_for_extendables(n, c, attr)
        cons.define_fixed_nominal_constraints(n, c, attr)
        cons.define_modular_constraints(n, c, attr)

    for c, attr in lookup.query("not nominal and not handle_separately").index:
        cons.define_operational_constraints_for_non_extendables(
            n, sns, c, attr, transmission_losses
        )
        cons.define_operational_constraints_for_extendables(
            n, sns, c, attr, transmission_losses
        )
        cons.define_operational_constraints_for_committables(n, sns, c)
        cons.define_ramp_limit_constraints(n, sns, c, attr)
        cons.define_fixed_operation_constraints(n, sns, c, attr)

    thresholds = [30, 100, 400]
    bus_counts = get_bus_counts(n)
    prev = 0
    for t in thresholds + [float("inf")]:
        mask = (bus_counts > prev) & (bus_counts <= t) if t != float("inf") else (bus_counts > prev)
        buses = bus_counts.index[mask]
        suffix = f"-meshed-{prev}" if prev > 0 else ""
        if not buses.empty:
            cons.define_nodal_balance_constraints(
                n, sns, transmission_losses=transmission_losses, buses=buses, suffix=suffix
            )
        prev = t

    cons.define_kirchhoff_voltage_constraints(n, sns)
    cons.define_storage_unit_constraints(n, sns)
    cons.define_store_constraints(n, sns)

    if transmission_losses:
        for c in n.passive_branch_components:
            cons.define_loss_constraints(n, sns, c, transmission_losses)

    gcons.define_primary_energy_limit(n, sns)
    gcons.define_transmission_expansion_cost_limit(n, sns)
    gcons.define_transmission_volume_expansion_limit(n, sns)
    gcons.define_tech_capacity_expansion_limit(n, sns)
    gcons.define_operational_limit(n, sns)
    gcons.define_nominal_constraints_per_bus_carrier(n, sns)
    gcons.define_growth_limit(n, sns)

    define_objective(n, sns)

    return n.model
