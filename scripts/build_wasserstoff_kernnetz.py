# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: : 2020-2023 The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT
#
# Michael Lindner, Toni Seibold, Julian Geis, Tom Brown (2025).
# Kopernikus-Projekt Ariadne - Gesamtsystemmodell PyPSA-DE.
# https://github.com/PyPSA/pypsa-de

"""
Preprocess hydrogen kernnetz based on data from FNB Gas
(https://fnb-gas.de/wasserstoffnetz-wasserstoff-kernnetz/).
"""

import logging

logger = logging.getLogger(__name__)

import uuid

import uuid

import geopandas as gpd
import numpy as np
import pandas as pd
from pypsa.geo import haversine_pts
import pandas as pd
from pypsa.geo import haversine_pts
from shapely import wkt
from shapely.geometry import LineString, Point, MultiLineString

import os
import sys

paths = ["workflow/submodules/pypsa-eur/scripts", "../submodules/pypsa-eur/scripts"]
for path in paths:
    sys.path.insert(0, os.path.abspath(path))
from build_gas_network import (
    diameter_to_capacity
)

MANUAL_ADDRESSES = {
    "Oude Statenzijl": (7.205108658430258, 53.20183834422634),
    "Helgoland": (7.882663327316698, 54.183393795580166),
    "SEN-1": (6.5, 55.0),
    "AWZ": (14.220711180456643, 54.429208831326804),
    "Bremen": (8.795818388451732, 53.077669699449594),
    "Bad Lauchstädt": (11.869106908389433, 51.38797498313352),
    "Großkugel": (12.151584743366769, 51.4166927585755),
    "Bobbau": (12.269345975889912, 51.69045938775995),
    "Visbeck": (8.310468203836264, 52.834518912466216),
    "Elbe-Süd": (9.608042769377906, 53.57422954537108),
    "Salzgitter": (10.386847343138689, 52.13861418123843),
    "Wefensleben": (11.15557835653467, 52.176005656180244),
    "Fessenheim": (7.5352027843079, 47.91300212650956),
    "Hittistetten": (10.09644829589717, 48.32667870548472),
    "Lindau": (9.690886766574819, 47.55387858107057),
    "Ludwigshafen": (8.444314472678961, 49.477207809634784),
    "Niederhohndorf": (12.466430165766688, 50.7532612203904),
    "Rückersdorf": (12.21941992347776, 50.822251899358236),
    "Bissingen": (10.6158383, 48.7177493),
    "Rehden": (8.476178919627396, 52.60675277527164),
    "Eynatten": (6.083339457526605, 50.69260916361823),
    "Vlieghuis": (6.8382504272201095, 52.66036497820981),
    "Kalle": (6.921180663621839, 52.573992586428425),
    'Carling': (6.713267207127634, 49.16738919353264),
    'Legden': (7.099754098013676, 52.03269789265483),
    'Ledgen': (7.099754098013676, 52.03269789265483),
    'Reiningen': (8.374879149975513, 52.50849502371421),
    'Buchholz': (12.929212986885771, 52.15737808332214),
    'Sandkrug': (8.257391972093515, 53.05387937393471),
}


def diameter_to_capacity_h2(pipe_diameter_mm):
    """
    Calculate pipe capacity in MW based on diameter in mm. Linear interpolation.

    20 inch (500 mm)  50 bar -> 1.2   GW H2 pipe capacity (LHV)
    36 inch (900 mm)  50 bar -> 4.7   GW H2 pipe capacity (LHV)
    48 inch (1200 mm) 80 bar -> 16.9  GW H2 pipe capacity (LHV)

    Based on table 4 of
    https://ehb.eu/files/downloads/EHB-Analysing-the-future-demand-supply-and-transport-of-hydrogen-June-2021-v3.pdf
    """
    # slopes definitions
    m0 = (1200 - 0) / (500 - 0)
    m1 = (4700 - 1200) / (900 - 500)
    m2 = (16900 - 4700) / (1200 - 900)
    # intercepts
    a0 = 0
    a1 = 1200 - m1 * 500
    a2 = 4700 - m2 * 900

    if pipe_diameter_mm < 500:
        return a0 + m0 * pipe_diameter_mm
    elif pipe_diameter_mm < 900:
        return a1 + m1 * pipe_diameter_mm
    else:
        return a2 + m2 * pipe_diameter_mm


def load_and_merge_raw(fn1, fn2):
    # load, clean and merge

    df_fn1 = pd.read_excel(fn1, skiprows=2, skipfooter=2)
    df_fn2_retrofit = pd.read_excel(
        fn2, "Wasserstoff-Kernnetz Umstellung", skiprows=2, skipfooter=4
    )
    df_fn2_new = pd.read_excel(
        fn2, "Wasserstoff-Kernnetz Neubau", skiprows=3, skipfooter=2
    )

    for df in [df_fn1, df_fn2_retrofit, df_fn2_new]:
        df.columns = df.columns.str.replace("\n", "")

    # clean first dataset
    # drop lines not in Kernetz
    df_fn1 = df_fn1[df_fn1["Bestandteil des Wasserstoff-Kernnetzes"] == "ja"]

    to_keep = [
        "Name (Lfd.Nr.-Von-Nach)",
        "Umstellungsdatum/ Planerische Inbetriebnahme",
        "Anfangspunkt(Ort)",
        "Endpunkt(Ort)",
        "Nenndurchmesser (DN)",
        "Länge (km)",
        "Druckstufe (DP)[mind. 30 barg]",
        "Bundesland",
        "Umstellung/ Neubau",
        "IPCEI-Projekt(ja/ nein)",
    ]

    to_rename = {
        "Name (Lfd.Nr.-Von-Nach)": "name",
        "Umstellungsdatum/ Planerische Inbetriebnahme": "build_year",
        "Nenndurchmesser (DN)": "diameter_mm",
        "Länge (km)": "length",
        "Druckstufe (DP)[mind. 30 barg]": "max_pressure_bar",
        "Umstellung/ Neubau": "retrofitted",
        "IPCEI-Projekt(ja/ nein)": "ipcei",
    }

    df_fn1 = df_fn1[to_keep].rename(columns=to_rename)

    # extract info on retrofitted
    df_fn1["retrofitted"] = df_fn1.retrofitted != "Neubau"

    # clean second dataset
    # select only pipes
    df_fn2_new = df_fn2_new[df_fn2_new["Maßnahmenart"] == "Leitung"]

    to_keep = [
        "Name",
        "Planerische Inbetriebnahme",
        "Anfangspunkt(Ort)",
        "Endpunkt(Ort)",
        "Nenndurchmesser (DN)",
        "Länge (km)",
        "Druckstufe (DP)[mind. 30 barg]",
        "Bundesland",
        "retrofitted",
        "IPCEI-Projekt(Name/ nein)",
    ]

    to_rename = {
        "Name": "name",
        "Planerische Inbetriebnahme": "build_year",
        "Nenndurchmesser (DN)": "diameter_mm",
        "Länge (km)": "length",
        "Druckstufe (DP)[mind. 30 barg]": "max_pressure_bar",
        "IPCEI-Projekt(Name/ nein)" : "ipcei",
    }

    df_fn2_new["retrofitted"] = False
    df_fn2_retrofit["retrofitted"] = True
    df_fn2 = pd.concat([df_fn2_retrofit, df_fn2_new])[to_keep].rename(columns=to_rename)
    df = pd.concat([df_fn1, df_fn2])
    df.reset_index(drop=True, inplace=True)

    return df


def prepare_dataset(df):

    # clean length
    df.length = df.length.astype(float)

    # clean diameter
    df.diameter_mm = (
        df.diameter_mm.astype(str)
        .str.extractall(r"(\d+)")
        .groupby(level=0)
        .last()
        .astype(int)
    )

    # clean max pressure
    df.max_pressure_bar = (
        df.max_pressure_bar.astype(str)
        .str.extractall(r"(\d+[.,]?\d*)")
        .groupby(level=0)
        .last()
        .squeeze()
        .str.replace(",", ".")
        .astype(float)
    )

    # clean build_year
    df.build_year = (
        df.build_year.astype(str)
        .str.extract(r"(\b\d{4}\b)")
        .astype(float)
        .fillna(2032)
    )

    # create bidirectional and set true
    df["bidirectional"] = True

    df[["BL1", "BL2"]] = (
        df["Bundesland"]
        .apply(lambda bl: [bl.split("/")[0].strip(), bl.split("/")[-1].strip()])
        .apply(pd.Series)
    )

    # calc capa
    df["p_nom"] = df.diameter_mm.apply(diameter_to_capacity_h2)

    # eliminated gas capacity from retrofitted pipes
    df["removed_gas_cap"] = df.diameter_mm.apply(diameter_to_capacity)
    df[df.retrofitted == False]["removed_gas_cap"] == 0

    # eliminate leading and trailing spaces
    df["Anfangspunkt(Ort)"] = df["Anfangspunkt(Ort)"].str.strip()
    df["Endpunkt(Ort)"] = df["Endpunkt(Ort)"].str.strip()

    # drop pipes with same start and end
    df = df[df["Anfangspunkt(Ort)"] != df["Endpunkt(Ort)"]]

    # drop pipes with length smaller than 5 km
    df = df[df.length > 5]

    # reindex
    df.reset_index(drop=True, inplace=True)

    return df


def geocode_locations(df):

    try:
        from geopy.extra.rate_limiter import RateLimiter
        from geopy.geocoders import Nominatim
    except:
        raise ModuleNotFoundError(
            "Optional dependency 'geopy' not found."
            "Install via 'conda install -c conda-forge geopy'"
        )

    locator = Nominatim(user_agent=str(uuid.uuid4()))
    geocode = RateLimiter(locator.geocode, min_delay_seconds=2)
    # load state data for checking
    gdf_state = gpd.read_file(snakemake.input.gadm).set_index("GID_1")

    def get_location(row):
        def get_loc_A(loc="location", add_info=""):
            loc_A = Point(
                gpd.tools.geocode(row[loc] + ", " + add_info, timeout=7)[
                    "geometry"
                ][0]
            )
            return loc_A

        def get_loc_B(loc="location", add_info=""):
            loc_B = geocode([row[loc], add_info], timeout=7)
            if loc_B is not None:
                loc_B = Point(loc_B.longitude, loc_B.latitude)
            else:
                loc_B = Point(0, 0)
            return loc_B

        def is_in_state(point, state="state"):
            if (row[state] in gdf_state.NAME_1.tolist()) & (point is not None):
                polygon_geometry = gdf_state[
                    gdf_state.NAME_1 == row[state]
                ].geometry.squeeze()
                return point.within(polygon_geometry)
            else:
                return False

        loc = get_loc_A("location", "Deutschland")

        # check if location is in Bundesland
        if not is_in_state(loc, "state"):
            # check if other loc is in Bundesland
            loc = get_loc_B("location", "Deutschland")
            # if both methods do not return loc in Bundesland, add Bundesland info
            if not is_in_state(loc, "state"):
                loc = get_loc_A("location", row["state"] + ", Deutschland")
                # if no location in Bundesland can be found
                if not is_in_state(loc, "state"):
                    loc = Point(0, 0)

        return loc

    # extract locations and state
    locations1, locations2 = (
        df[["Anfangspunkt(Ort)", "BL1"]],
        df[["Endpunkt(Ort)", "BL2"]],
    )
    locations1.columns, locations2.columns = ["location", "state"], [
        "location",
        "state",
    ]
    locations = pd.concat([locations1, locations2], axis=0)
    locations.drop_duplicates(inplace=True)

    # (3min)
    locations["point"] = locations.apply(lambda row: get_location(row), axis=1)

    # map manual locations (NOT FOUND OR WRONG)
    locations.point = locations.apply(
        lambda row: Point(
            MANUAL_ADDRESSES.get(row.location)
            if row.location in MANUAL_ADDRESSES.keys()
            else row.point
        ),
        axis=1,
    )

    return locations


def assign_locations(df, locations):

    df["point0"] = pd.merge(
        df,
        locations,
        left_on=["Anfangspunkt(Ort)", "BL1"],
        right_on=["location", "state"],
        how="left",
    )["point"]
    df["point1"] = pd.merge(
        df,
        locations,
        left_on=["Endpunkt(Ort)", "BL2"],
        right_on=["location", "state"],
        how="left",
    )["point"]

    # calc length of points
    length_factor = 1.0
    length_factor = 1.0
    df["length_haversine"] = df.apply(
        lambda p: length_factor
        * haversine_pts([p.point0.x, p.point0.y], [p.point1.x, p.point1.y]),
        axis=1,
    )

    # calc length ratio
    df["length_ratio"] = df.apply(
        lambda row: max(row.length, row.length_haversine)
        / (min(row.length, row.length_haversine) + 1),
        axis=1,
    )

    # only keep pipes with realistic length ratio
    df = df.query("retrofitted or length_ratio <= 2")

    # calc LineString
    df["geometry"] = df.apply(lambda x: LineString([x["point0"], x["point1"]]), axis=1)

    return df

def clean_h2_inframap(input_path):

    # Load geojson
    df = gpd.read_file(input_path)

    #filter for essential columns and rename for better accessibility
    to_keep = ["Project_Na", "Project_Ty", "Commission", "Share_of_t", "Location", "Increment", "Peak_Incre", "Shape__Length", "geometry"]
    to_rename = {
        "Project_Na":"name",
        "Project_Ty":"retrofit",
        "Commission":"build_year",
        "Share_of_t":"hydrogen_share",
        "Location":"location",
        "Increment":"increment",
        "Peak_Incre":"peak_increment",
        "Shape__Length":"shape_length",
    }
    df = df[to_keep].rename(columns=to_rename)

    # Mark missing values and adjust irregular entries in increment column
    df = df.replace({
        "No data available":None,
        "Data is not available":None,
        "Data not available":None,
        'Forward flows: IT-AT - 168 GWh/d, AT-SK - 142 GWh/d. Reverse flows: AT - IT and SK -AT - 126 GWh/d.':142,
        '25 GWh/d':25,
        ' ':None
        })

    # Fill missing values in increment column with values from peak_increment column and vice versa
    df.loc[df.increment.isna(), "increment"] = df.loc[df.increment.isna(), "peak_increment"]
    df.loc[df.increment.isna(), "peak_increment"] = df.loc[df.peak_increment.isna(), "increment"]

    # Choose column for capacity calculation
    if snakemake.params.peak_increment == True:
        df["p_nom"] = df["peak_increment"].astype(float)
    else:
        df["p_nom"] = df["increment"].astype(float)

    #Fill missing capacity values with values from pipeline where start/endpoints are the closest, using fix value or dropping pipelines
    if snakemake.params.fill_mode == "nearest":
        df.loc[df.p_nom.isna(), 'p_nom'] = (
            df.loc[df.p_nom.isna()].apply(
            lambda p: df.loc[p.geometry.boundary.distance(df.loc[df.p_nom.notna(), 'geometry'].boundary).nsmallest(1).index[-1], 'p_nom'],
            axis=1
            )
        )
    elif snakemake.params.fill_mode == "drop":
        df.dropna(subset=["p_nom"], inplace=True)
    else:
        try:
            df["p_nom"].fillna(int(snakemake.params.fill_mode) * 24 * snakemake.params.pipeline_utilization, inplace=True)
        except:
            print("No adequate fill mode or fill value has been provided in the config. Rows with missing values are dropped")
            df.dropna(subset=["p_nom"], inplace=True)

    # Convert unit of increment [GWh/d] to MW assuming 100% utilization
    df["p_nom"] = df["p_nom"].div(24 * snakemake.params.pipeline_utilization).mul(1e3)

    # Assign pipeline types to retrofit boolean
    df["retrofitted"] = True
    df.loc[df.retrofit == "New", "retrofitted"] = False

    # Calculate length_haversine and validate length column by ratio calculation    
    def haversine_length(line):
        if isinstance(line, LineString):
            coordinates = [(point[1], point[0]) for point in line.coords]
            length = sum(haversine_pts(coordinates[i], coordinates[i+1]) for i in range(len(coordinates)-1))
            return length
        elif isinstance(line, MultiLineString):
            total_length = 0
            for linestring in line.geoms:
                coordinates = [(point[1], point[0]) for point in linestring.coords]
                length = sum(haversine_pts(coordinates[i], coordinates[i+1]) for i in range(len(coordinates)-1))
                total_length += length
            return total_length
    df["length_haversine"] = df.geometry.apply(haversine_length)

    # Conversion of raw length data to km
    df["length"] = df.shape_length / 1000

    df["length_ratio"] = df.apply(
        lambda row: max(row.length, row.length_haversine)
        / (min(row.length, row.length_haversine) + 1),
        axis=1,
    )

    df = df.query('length_ratio <= 2')

    # CH4 pipeline capacity to be removed by repurposing according to config H2_retrofit_capacity_per_CH4: 0.6
    df["removed_gas_cap"] = df.p_nom.div(0.6)

    # Remove pipelines with gas mix
    df["hydrogen_share"] = df["hydrogen_share"].fillna(100).replace(["100", "100, and Ammonia"], 100)
    df = df.query('hydrogen_share == 100')

    # Insert bidirectionality column
    df["bidirectional"] = True

    # Split MultiLineString pipeline projects and distribute length according to haversine distance of LineString elements
    df_multi_idx = df.loc[df.geometry.geom_type == 'MultiLineString'].index
    df = df.explode(index_parts=True)
    project_parts = ' (part ' + pd.Series(df.loc[df_multi_idx].index.get_level_values(1) + 1).astype(str) + ')'
    df.loc[df_multi_idx, 'name'] = df.loc[df_multi_idx, 'name'] + project_parts.values
    df.loc[df_multi_idx, 'length'] = df.loc[df_multi_idx].apply(lambda p: haversine_length(p.geometry) / p.length_haversine * p.length, axis=1)

    # Insert boundary points as Point0 and Point1 columns
    df['point0'] = df.geometry.boundary.explode(index_parts=True).xs(0, level=2).to_wkt()
    df['point1'] = df.geometry.boundary.explode(index_parts=True).xs(1, level=2).to_wkt()

    # Cast build_year column
    df["build_year"] = df["build_year"].fillna(2045).astype(int)

    return df


if __name__ == "__main__":
    if "snakemake" not in globals():
        import os
        import sys

        path = "../submodules/pypsa-eur/scripts"
        sys.path.insert(0, os.path.abspath(path))
        from _helpers import mock_snakemake
        import os
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        snakemake = mock_snakemake("build_wasserstoff_kernnetz", configfile='/nimble/home/cas96273/agora/agora-copy/results/0314_wkn_test/config.yaml')

    logging.basicConfig(level=snakemake.config["logging"]["level"])

    wasserstoff_kernnetz = load_and_merge_raw(
        snakemake.input.wasserstoff_kernnetz_1[0],
        snakemake.input.wasserstoff_kernnetz_2[0],
    )

    wasserstoff_kernnetz = prepare_dataset(wasserstoff_kernnetz)

    if snakemake.config["policy_plans"]["wasserstoff_kernnetz"]["reload_locations"]:
        locations = geocode_locations(wasserstoff_kernnetz)
    else:
        locations = pd.read_csv(snakemake.input.locations, index_col=0)
        locations["point"] = locations["point"].apply(wkt.loads)

    wasserstoff_kernnetz = assign_locations(wasserstoff_kernnetz, locations)
    h2_inframap = clean_h2_inframap(snakemake.input.h2_inframap)

    wasserstoff_kernnetz.to_csv(snakemake.output.cleaned_wasserstoff_kernnetz)
    h2_inframap.to_file(snakemake.output.cleaned_h2_inframap)
