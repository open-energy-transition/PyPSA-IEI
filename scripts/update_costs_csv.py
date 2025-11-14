import pandas as pd
import geopandas as gpd
import re
from shapely.geometry import Point
from build_gas_network import diameter_to_capacity

import logging
from _helpers import configure_logging

logger = logging.getLogger(__name__)

def insert_new_costs(costs_file, invest_update, filename):
    costs = pd.read_csv(costs_file).set_index('technology')
    for key, investment in invest_update.items():
        mask = (costs.parameter == "investment") & (costs.index == key)
        costs.loc[mask, 'value'] = investment
    costs.to_csv(filename)

if __name__ == '__main__':
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake(
            "update_costs_csv",
            configfile=r'...',   # add the path to the config file with which you want to debug
            )

    configure_logging(snakemake)
    investment_update = snakemake.params.invest_update[int(snakemake.wildcards.planning_horizons)]
    insert_new_costs(snakemake.input.costs, investment_update, snakemake.output.costs)

    logger.info(f"Updated costs for in cost files according to config.")