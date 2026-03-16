# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2024 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT
#
# Michael Lindner, Toni Seibold, Julian Geis, Tom Brown (2025).
# Kopernikus-Projekt Ariadne - Gesamtsystemmodell PyPSA-DE.
# https://github.com/PyPSA/pypsa-de
"""
Cluster Wasserstoff Kernnetz to clustered model regions.
"""

import logging

logger = logging.getLogger(__name__)

import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import LineString, Point
from shapely.ops import transform, unary_union
import pyproj

import os
import sys

paths = ["workflow/submodules/pypsa-eur/scripts", "../submodules/pypsa-eur/scripts"]
for path in paths:
    sys.path.insert(0, os.path.abspath(path))
from cluster_gas_network import (
    load_bus_regions,
    reindex_pipes,
    build_clustered_gas_network,
)

# Define a function for projecting points to meters
project_to_meters = pyproj.Transformer.from_proj(
    pyproj.Proj("epsg:4326"),  # assuming WGS84
    pyproj.Proj(proj="utm", zone=33, ellps="WGS84"),  # adjust the projection as needed
    always_xy=True,
).transform

# Define a function for projecting points back to decimal degrees
project_to_degrees = pyproj.Transformer.from_proj(
    pyproj.Proj(proj="utm", zone=33, ellps="WGS84"),  # adjust the projection as needed
    pyproj.Proj("epsg:4326"),
    always_xy=True,
).transform

def remove_double_crossing(df):
    """
    Make sure one pipeline is not counted twice by crossing a border twice.

    Parameters:
    - df (DataFrame): DataFrame containing the clustered pipeline segments

    Returns:
    DataFrame: DataFrame of pipelines without duplicates.
    """
    for idx, row in df.iterrows():
        df_temp = pd.concat([df, gpd.GeoDataFrame(row).transpose()])
        duplicated_rows = df_temp.duplicated(keep=False)
        row_in_df = duplicated_rows.iloc[-1]
        if not row_in_df:
            continue
        row_buses = row.loc[['bus0', 'bus1']]
        row_name = row['name']
        to_drop = df.query('(index!=@idx) & (name==@row_name) & bus0.isin(@row_buses) & bus1.isin(@row_buses)').index
        df.drop(to_drop, inplace=True)
    return df

def split_line_by_length(line, segment_length_km):
    """
    Split a Shapely LineString into segments of a specified length.

    Parameters:
    - line (LineString): The original LineString to be split.
    - segment_length_km (float): The desired length of each resulting segment in kilometers.

    Returns:
    list: A list of Shapely LineString objects representing the segments.
    """

    # Convert segment length from kilometers to meters
    segment_length_meters = segment_length_km * 1000

    # Project the LineString to a suitable metric projection
    projected_line = transform(project_to_meters, line)

    total_length = projected_line.length
    num_segments = int(total_length / segment_length_meters)

    # Return early if no segmentation required
    if num_segments <= 1:
        return [line]

    segments = []
    for i in range(1, num_segments + 1):
        start_point = projected_line.interpolate((i - 1) * segment_length_meters)
        end_point = projected_line.interpolate(i * segment_length_meters)

        # Extract x and y coordinates from the tuples
        start_point_coords = (start_point.x, start_point.y)
        end_point_coords = (end_point.x, end_point.y)

        # Create Shapely Point objects
        start_point_degrees = Point(start_point_coords)
        end_point_degrees = Point(end_point_coords)

        # Project the points back to decimal degrees
        start_point_degrees = transform(project_to_degrees, start_point_degrees)
        end_point_degrees = transform(project_to_degrees, end_point_degrees)

        # last point without interpolation
        if i == num_segments:
            end_point_degrees = Point(line.coords[-1])

        segment = LineString([start_point_degrees, end_point_degrees])
        segments.append(segment)

    return segments


def divide_pipes(df, offshore_regions, segment_length=10):
    """
    Divide a GeoPandas DataFrame of LineString geometries into segments of a specified length while making sure offshore
    regions are not counted as connections to a specific cluster.

    Parameters:
    - df (GeoDataFrame): The input DataFrame containing LineString geometries.
    - offshore_regions (GeoDataFrame): Shapes of the clusters' offshore regions.
    - segment_length (float): The desired length of each resulting segment in kilometers.

    Returns:
    GeoDataFrame: A new GeoDataFrame with additional rows representing the segmented pipes.
    """

    result = pd.DataFrame(columns=df.columns)

    for index, pipe in df.iterrows():
        segments = split_line_by_length(pipe.geometry, segment_length)
        i = 0
        j = 1
        temp_segment = LineString()
        temp_point0 = Point()
        for segment in segments:

            if (any(offshore_regions['geometry'].apply(lambda polygon: polygon.contains(Point(segment.coords[0]))))
                    & temp_segment.is_empty):
                continue
            else:
                if temp_point0.is_empty:
                    temp_point0 = Point(segment.coords[0])
            if any(offshore_regions['geometry'].apply(lambda polygon: polygon.contains(Point(segment.coords[-1])))):
                if temp_segment.is_empty:
                    temp_point0 = Point(segment.coords[0])
                temp_segment = unary_union([temp_segment, segment])
                j += 1
                continue
            res_row = pipe.copy()
            res_row.point0 = temp_point0
            res_row.point1 = Point(segment.coords[-1])
            res_row.geometry = unary_union([temp_segment, segment])
            res_row.length_haversine = segment_length * j
            result.loc[f"{index}-{i}"] = res_row
            i += 1
            temp_segment = LineString()
            temp_point0 = Point()

    return result

def aggregate_parallel_pipes(df):
    strategies = {
        "bus0": "first",
        "bus1": "first",
        "p_nom": "sum",
        "p_nom_diameter": "sum",
        "max_pressure_bar": "mean",
        "diameter_mm": "mean",
        "length": "mean",
        "name": " ".join,
        "p_min_pu": "min",
        "removed_gas_cap": "sum",
    }
    return df.groupby(["index", "build_year"]).agg(strategies)



if __name__ == "__main__":
    if "snakemake" not in globals():
        import os
        import sys

        path = "../submodules/pypsa-eur/scripts"
        sys.path.insert(0, os.path.abspath(path))
        from _helpers import mock_snakemake
        import os
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        snakemake = mock_snakemake(
            "cluster_wasserstoff_kernnetz",
            configfile=r"..."
        )

    logging.basicConfig(level=snakemake.config["logging"]["level"])

    fn_wkn = snakemake.input.cleaned_h2_network
    df_wkn = pd.read_csv(fn_wkn, index_col=0)
    for col in ["point0", "point1", "geometry"]:
        df_wkn[col] = df_wkn[col].apply(wkt.loads)

    bus_regions = load_bus_regions(
        snakemake.input.regions_onshore, snakemake.input.regions_offshore
    )
    # remove small snippit of the cluster IT1 0 that causes clustering problems
    faulty_cluster = "IT1 0"
    if faulty_cluster in bus_regions.index:
        bus_regions.loc["IT1 0"].geometry = bus_regions.loc["IT1 0"].geometry.geoms[1]

    offshore_regions = gpd.read_file(snakemake.input.regions_offshore)

    fn_h2i = snakemake.input.cleaned_h2_inframap
    df_h2i = gpd.read_file(fn_h2i, index_col=0)
    for col in ["point0", "point1", "geometry"]:
        df_h2i[col] = df_h2i[col].astype(str).apply(wkt.loads)
    df_h2i.drop(set(df_h2i.columns) - set(df_wkn.columns), axis=1, inplace=True)

    kernnetz_cf = snakemake.config["policy_plans"]["wasserstoff_kernnetz"]
    if kernnetz_cf["divide_pipes"]:
        segment_length = kernnetz_cf["pipes_segment_length"]
        df_wkn = divide_pipes(df_wkn, offshore_regions, segment_length=segment_length)
        df_h2i = divide_pipes(df_h2i, offshore_regions, segment_length=segment_length)

    wasserstoff_kernnetz = build_clustered_gas_network(df_wkn, bus_regions)
    h2_inframap = build_clustered_gas_network(df_h2i, bus_regions)

    wasserstoff_kernnetz = remove_double_crossing(wasserstoff_kernnetz)

    h2_inframap = remove_double_crossing(h2_inframap)

    wasserstoff_kernnetz[["bus0", "bus1"]] = (
        wasserstoff_kernnetz[["bus0", "bus1"]].apply(sorted, axis=1).apply(pd.Series)
    )

    h2_inframap[["bus0", "bus1"]] = (
        h2_inframap[["bus0", "bus1"]].apply(sorted, axis=1).apply(pd.Series)
    )

    reindex_pipes(wasserstoff_kernnetz, prefix="H2 pipeline")
    reindex_pipes(h2_inframap, prefix="H2 pipeline")

    h2_inframap.drop(h2_inframap.loc[h2_inframap.index.intersection(wasserstoff_kernnetz.index)].query("build_year <= 2032").index, inplace=True)
    wasserstoff_kernnetz = pd.concat([wasserstoff_kernnetz, h2_inframap])


    wasserstoff_kernnetz["p_min_pu"] = 0
    wasserstoff_kernnetz["p_nom_diameter"] = 0
    wasserstoff_kernnetz = aggregate_parallel_pipes(wasserstoff_kernnetz.reset_index())
    wasserstoff_kernnetz["build_year"] = wasserstoff_kernnetz.index.get_level_values(1).astype(int)
    wasserstoff_kernnetz = wasserstoff_kernnetz.droplevel(1)

    wasserstoff_kernnetz.to_csv(snakemake.output.clustered_h2_network)
