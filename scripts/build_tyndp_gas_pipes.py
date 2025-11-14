import pandas as pd
import geopandas as gpd
import re
from shapely.geometry import Point
from build_gas_network import diameter_to_capacity

import logging
from _helpers import configure_logging

logger = logging.getLogger(__name__)


def coordinates_to_cluster(coordinates):
    """
    Get cluster code corresponding to a set of coordinates.

    Parameters
    ----------
    coordinates : str
        string of a pair of coordinates

    Returns
    -------
    str
        cluster in which the coordinates lay

    """
    parts = re.split('[^\d\w]+', coordinates)
    # get latitude degrees
    lat = float(parts[0])
    # get latitude minutes
    lat_min = float(parts[1])
    # get direction (N, S, E, W) for latitude
    lat_dir = parts[2]
    # get longitude degrees
    lon = float(parts[3])
    # get longitude minutes
    lon_min = float(parts[4])
    # get direction (N, S, E, W) for longitude
    lon_dir = parts[5]
    # convert to decimal format
    dd_lat = round(lat + lat_min/60, 5)
    dd_lon = round(lon + lon_min/60, 5)
    # add sign according to direction
    if lat_dir == 'S':
        dd_lat = -dd_lat
    if lon_dir == 'W':
        dd_lon = -dd_lon

    ### find cluster for coodinate
    # convert coordinate into point
    point = Point(dd_lon, dd_lat)
    # get cluster, which includes point
    return regions.loc[regions['geometry'].contains(point), 'name'].values[0]


if __name__ == '__main__':
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_tyndp_gas_pipes",
            configfile=r'...',   # add the path to the config file with which you want to debug
            )

    configure_logging(snakemake)

    # load outlines of the clusters
    regions = gpd.read_file(snakemake.input.regions)

    # load list of tyndp gas projects
    tyndp_raw_data = pd.read_excel(snakemake.input.tyndp_gas_projects)

    # remove projects, where crucial information is missing
    tyndp_raw_data.dropna(subset=['Code', 'Project Name', 'Maturity Status', 'Diameter (mm)',
                  'Length (km)', 'PCI 5th List', 'Project Commissioning Year Last',
                  'Start', 'End'], inplace=True)

    # create dataframe for implementation
    tyndp_processed_data = tyndp_raw_data.copy()

    # calculate capacity in MW from pipeline diameter according to procedure for existing pipelines
    tyndp_processed_data['p_nom'] = tyndp_processed_data['Diameter (mm)'].apply(diameter_to_capacity)

    ###  cluster assignment to the locations that are already given as a country code
    # map cluster to countrycode for each country
    cluster_mapping = {value[:2]: value for key, value in regions['name'].to_dict().items()}
    # select projects, where the starting point is in a country with just one cluster and therefore given by a country
    # code
    country_code = tyndp_processed_data['Start'].apply(len) == 2
    # replace the country codes in the starting points by the corresponding cluster
    tyndp_processed_data.loc[country_code, 'Start'] =(tyndp_processed_data.loc[country_code, 'Start']
                                                      .replace(cluster_mapping))
    # filter for projects, which have their endpoint in a country with one cluster
    country_code = tyndp_processed_data['End'].apply(len) == 2
    # replace the country code with the cluster for the end points of the pipelines
    tyndp_processed_data.loc[country_code, 'End'] = (tyndp_processed_data.loc[country_code, 'End']
                                                     .replace(cluster_mapping))


    ### cluster assignment for the locations that are given by coordinates since the country has several clusters
    # filter for projects with coordinates as starting point
    coordinate_code = tyndp_processed_data['Start'].apply(len) > 5
    # replace coordinates by their corresponding cluster for the starting point
    tyndp_processed_data.loc[coordinate_code, 'Start'] = (tyndp_processed_data.loc[coordinate_code, 'Start']
                                                          .apply(coordinates_to_cluster))
    # filter for projects with coordinates as their end point
    coordinate_code = tyndp_processed_data['End'].apply(len) > 5
    # replace coordinates by clusters for the end point
    tyndp_processed_data.loc[coordinate_code, 'End'] = (tyndp_processed_data.loc[coordinate_code, 'End']
                                                        .apply(coordinates_to_cluster))

    # rename columns for more consistent usage in prepare_sector_network.py
    tyndp_processed_data.rename(columns={'Start': 'bus0',
                                           'End': 'bus1',
                                           'Maturity Status': 'status',
                                           'PCI 5th List': 'PCI',
                                           'Project Commissioning Year Last': 'year',
                                           'Length (km)': 'length'}, inplace=True)

    # create tag with project information
    tyndp_processed_data['tag'] = tyndp_processed_data['Code'] + ': ' + tyndp_processed_data['Project Name']

    # create index of pipelines
    tyndp_processed_data['name'] = ('gas pipeline tyndp ' + tyndp_processed_data['bus0']
                                    + ' -> ' + tyndp_processed_data['bus1'])

    # replace PCI status with true and false
    tyndp_processed_data['PCI'].replace({'Yes': 'True', 'No': 'False'}, inplace=True)

    # delete unnecessary columns
    tyndp_processed_data.drop(columns=['Code',
                                       'Project Name',
                                       'Project Description',
                                       'Diameter (mm)',
                                       'Capacities',
                                       'Reference'],
                              inplace=True)

    # remove all projects are entirely within one cluster
    tyndp_processed_data = tyndp_processed_data.query('bus0!=bus1')

    # save processed data for later implementation
    tyndp_processed_data.to_csv(snakemake.output.clustered_tyndp_pipes, index=False)
    logger.info(f"Assign cluster to TYNDP gas piplines")