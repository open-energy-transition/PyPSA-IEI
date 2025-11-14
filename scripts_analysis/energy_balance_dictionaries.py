import pandas as pd

# In subcomponent type dict only modify right hand side
# left hand side is needed to ensure full balance

# How to create a new balance for a new carrier 'name':
# full balance
# en_balance = n.statistics.energy_balance(aggregate_bus=False)
# balance for the carrier 'name'
# test_bal = en_balance.loc[:,en_balance.index.get_level_values(2)=='name']
# get all components and put them as keys into a new sub_component_type_dict
# test_bal.index.get_level_values(1).unique()
# define your mapping and your component_type_dict
# whether a component is a demand (<0) or a generation (>0) component can be
# seen from the sign in test_bal.
# more easily if you look at:
# test_bal = test_bal.groupby(test_bal.index.get_level_values(1)).sum()
# add a new function to be called in get_components_for_carrier()
# if, when running configurable_energy_balance.py, the balance is not 0, check
# the console if there is a warning that you missed a component (only the once
# that are used in a specific year are in n.statistics.energy_balance())


def get_components_for_carrier(my_carrier):
    """
    Get dict of components for carrier by calling the right function.

    Parameters
    ----------
    my_carrier : str
        str of carrier

    Returns
    -------
    dict
        list of all components as shown in final Energy Balance
    dict
        list of all sub components at model level mapped to component
        type- keys named as in n.statistics Energy Balance
    list
        additional element in sub_component_type dict: not in
        n.statistics Energy Balance but needed due to different
        accounting of AC transmission losses
    """
    # If list is complete and all subcomponents are drawn, balance sum
    # for the carrier is 0 (numerical error possible).
    if my_carrier == "H2":
        return get_H2_components()
    elif my_carrier == "AC":
        return get_AC_components()
    elif my_carrier == "low voltage":
        return get_low_voltage_components()
    elif my_carrier == "electricity":
        return get_electricity_components()
    elif my_carrier == "services urban decentral heat":
        return get_services_urban_decentral_heat_components()
    elif my_carrier == "urban central heat":
        return get_urban_central_heat_components()
    elif my_carrier == "residential rural heat":
        return get_residential_rural_heat_components()
    elif my_carrier == "residential urban decentral heat":
        return get_residential_urban_decentral_heat_components()
    elif my_carrier == "services rural heat":
        return get_services_rural_heat_components()
    elif my_carrier == "heat":
        return get_heat_components()
    elif my_carrier == "gas":
        return get_gas_components()


def get_H2_components():
    component_type_dict_H2 = {
        "H2 electrolysis": "Generation",
        "Steam-methane reforming": "Generation",
        "Non-European import": "Import",
        "Inner-European import": "Import",
        "Synfuel": "Demand",
        "H2 fuel cell": "Demand",
        "H2 turbine": "Demand",
        "Hydrogen storage": "Demand",
        "Industry$^{3}$": "Demand",
        "Fuel cell transport": "Demand",
    }
    sub_component_typ_dict_H2 = {
        "SMR": "Steam-methane reforming",
        "SMR CC": "Steam-methane reforming",
        "H2 Electrolysis": "H2 electrolysis",
        "import pipeline-H2": "Non-European import",
        "import shipping-H2": "Non-European import",
        "H2 pipeline": "Inner-European import",
        "H2 pipeline retrofitted": "Inner-European import",
        "H2 pipeline (Kernnetz)": "Inner-European import",
        "Fischer-Tropsch": "Synfuel",
        "Sabatier": "Synfuel",
        "methanolisation": "Synfuel",
        "H2 Fuel Cell": "H2 fuel cell",
        "H2 turbine": "H2 turbine",
        "Hydrogen Storage": "Hydrogen storage",
        "H2 for industry": "Industry$^{3}$",
        "land transport fuel cell": "Fuel cell transport",
    }
    extra_sub_comps = []  # components in sub_component_type_dict but
    # not in n.statistics energy balance
    return component_type_dict_H2, sub_component_typ_dict_H2, extra_sub_comps


def get_gas_components():
    component_type_dict_gas = {
        "Methanation": "Generation",
        "Biomethane": "Generation",
        "Non-European import": "Import",
        "Inner-European import/export": "Import",
        "Natural gas production": "Generation",
        "Gas turbines": "Demand",
        "CHP": "Demand",
        "Storage": "Demand",
        "Industry": "Demand",
        "Gas boiler": "Demand",
        "Steam-methane reforming": "Demand",
    }
    sub_component_typ_dict_gas = {
        "import lng gas": "Non-European import",
        "import pipeline gas": "Non-European import",
        "production gas": "Natural gas production",
        "import pipeline-syngas": "Non-European import",
        "import shipping-syngas": "Non-European import",
        "gas": "Storage",
        "biogas": "Biomethane",
        "Open-Cycle Gas": "Gas turbines",
        "gas pipeline": "Inner-European import/export",
        "gas pipeline new": "Inner-European import/export",
        "SMR CC": "Steam-methane reforming",
        "SMR": "Steam-methane reforming",
        "residential rural gas boiler": "Gas boiler",
        "residential rural micro gas CHP": "CHP",
        "services rural gas boiler": "Gas boiler",
        "services rural micro gas CHP": "CHP",
        "residential urban decentral gas boiler": "Gas boiler",
        "residential urban decentral micro gas CHP": "CHP",
        "services urban decentral gas boiler": "Gas boiler",
        "services urban decentral micro gas CHP": "CHP",
        "urban central gas boiler": "Gas boiler",
        "urban central gas CHP": "CHP",
        "urban central gas CHP CC": "CHP",
        "biogas to gas": "Biomethane",
        "biogas to gas CC": "Biomethane",
        "allam": "Gas turbines",
        "gas pipeline tyndp": "Inner-European import/export",
        "Combined-Cycle Gas": "Gas turbines",
        "Sabatier": "Methanation",
        "BioSNG": "Biomethane",
        "gas for industry": "Industry",
        "gas for industry CC": "Industry",
    }
    extra_sub_comps = []  # components in sub_component_type_dict but
    # not in n.statistics energy balance
    return (
        component_type_dict_gas,
        sub_component_typ_dict_gas,
        extra_sub_comps,
    )


def get_AC_components():
    component_type_dict_AC = {
        "Offshore wind": "Generation",
        "Onshore wind": "Generation",
        "Solar": "Generation",
        "Fossil": "Generation",
        "Nuclear": "Generation",
        "Battery discharger": "Generation",
        "PHS": "Generation",
        "Hydro": "Generation",
        # Careful: Do no modify AC/DC Import components
        # and Transmission loss components
        # unless you looked at how the following functions work:
        # get_relevant_cross_border_losses(),
        # calculate_internal_transmission_losses(),
        # calculate_crossborder_transmission_losses()
        "AC": "Import",
        "DC": "Import",
        "AC transmission losses": "Demand",
        "DC transmission losses": "Demand",
        "DAC": "Demand",
        "H2 electrolysis": "Demand",
        "H2 pipeline": "Demand",
        "H2 turbine": "Demand",
        "H2 fuel cell": "Demand",
        "Battery charger": "Demand",
        "Gas pipeline": "Demand",
        "Heat application": "Demand",
        "Methanol production": "Demand",
        "CHP": "Generation",
        # Careful when modifying distribution grid due to aggregation of AC
        # and low voltage in case of carrier "electricity"!
        "Electricity distribution grid": "Demand",
    }
    # AC List
    sub_component_typ_dict_AC = {
        # n.statistics statistics does not consider transmission losses
        # since the balance is always at cluster level.
        # to be able to correctly show imported energy and losses due to
        # transmission within a country/set of countries,
        # the following two components need to be added:
        "AC Losses": "AC transmission losses",  # not in n.statistics - added
        # manually to be able to calculate import
        "DC Losses": "DC transmission losses",  # not in n.statistics - added
        # manually to be able to calculate import
        # Careful: Do no modify AC/DC Import components and
        # Transmission loss components
        # unless you looked at how the following functions work:
        # get_relevant_cross_border_losses(),
        # calculate_internal_transmission_losses(),
        # calculate_crossborder_transmission_losses()
        # Energy Balance components
        "AC": "AC",
        "DC": "DC",
        "Offshore Wind (AC)": "Offshore wind",
        "Offshore Wind (DC)": "Offshore wind",
        "Onshore Wind": "Onshore wind",
        "Run of River": "Hydro",
        "Solar": "Solar",
        "Combined-Cycle Gas": "Fossil",  # CCGT
        "Open-Cycle Gas": "Fossil",  # 'OCGT'
        "oil": "Fossil",
        "lignite": "Fossil",
        "coal": "Fossil",
        "urban central gas CHP": "Fossil",
        "urban central gas CHP CC": "Fossil",
        "allam": "Fossil",
        "nuclear": "Nuclear",
        "urban central solid biomass CHP": "CHP",
        "urban central solid biomass CHP CC": "CHP",
        "battery discharger": "Battery discharger",
        "H2 turbine": "H2 turbine",
        "H2 Fuel Cell": "H2 fuel cell",
        "Pumped Hydro Storage": "PHS",
        "Reservoir & Dam": "Hydro",
        "DAC": "DAC",
        "H2 Electrolysis": "H2 electrolysis",
        "H2 pipeline": "H2 pipeline",
        "battery charger": "Battery charger",
        "gas pipeline": "Gas pipeline",
        "residential rural ground heat pump": "Heat application",
        "residential rural resistive heater": "Heat application",
        "residential urban decentral air heat pump": "Heat application",
        "residential urban decentral resistive heater": "Heat application",
        "services rural ground heat pump": "Heat application",
        "services rural resistive heater": "Heat application",
        "services urban decentral air heat pump": "Heat application",
        "services urban decentral resistive heater": "Heat application",
        "methanolisation": "Methanol production",
        "H2 pipeline(Kernnetz)": "H2 pipeline",
        "H2 pipeline (Kernnetz)": "H2 pipeline",
        # Careful when modifying distribution grid due to aggregation of AC
        # and low voltage in case of carrier "electricity"!
        "electricity distribution grid": "Electricity distribution grid",
    }
    extra_sub_comps = [
        "AC Losses",
        "DC Losses",
    ]  # components in sub_component_type_dict but
    # not in n.statistics energy balance
    return component_type_dict_AC, sub_component_typ_dict_AC, extra_sub_comps


def get_low_voltage_components():
    component_type_dict_lv = {
        "Solar": "Generation",
        "Fossil": "Generation",
        "Heat application": "Demand",
        "Home battery charger": "Demand",
        "Home battery discharger": "Generation",
        "Agriculture electricity": "Demand",
        "Residential & services": "Demand",
        "Industry electricity": "Demand",
        "Vehicles charger": "Demand",
        "Vehicle-to-grid": "Generation",
        # Careful when modifying distribution grid due to aggregation of AC
        # and low voltage in case of carrier "electricity"!
        "Distribution grid": "Generation",
    }
    sub_component_typ_dict_lv = {
        # Careful when modifying distribution grid due to aggregation of AC
        # and low voltage in case of carrier "electricity"!
        "electricity distribution grid": "Distribution grid",
        "home battery charger": "Home battery charger",
        "home battery discharger": "Home battery discharger",
        "residential rural air heat pump": "Heat application",
        "residential rural ground heat pump": "Heat application",
        "residential rural micro gas CHP": "Fossil",
        "residential rural resistive heater": "Heat application",
        "residential urban decentral air heat pump": "Heat application",
        "residential urban decentral micro gas CHP": "Fossil",
        "residential urban decentral resistive heater": "Heat application",
        "services rural air heat pump": "Heat application",
        "services rural ground heat pump": "Heat application",
        "services rural micro gas CHP": "Fossil",
        "services rural resistive heater": "Heat application",
        "services urban decentral air heat pump": "Heat application",
        "services urban decentral micro gas CHP": "Fossil",
        "services urban decentral resistive heater": "Heat application",
        "urban central air heat pump": "Heat application",
        "urban central resistive heater": "Heat application",
        "agriculture electricity": "Agriculture electricity",
        "electricity": "Residential & services",
        "industry electricity": "Industry electricity",
        "solar rooftop": "Solar",
        "V2G": "Vehicle-to-grid",
        "BEV charger": "Vehicles charger",
    }
    extra_sub_comps = []  # components in sub_component_type_dict but
    # not in n.statistics energy balance
    return component_type_dict_lv, sub_component_typ_dict_lv, extra_sub_comps


def get_electricity_components():
    component_type_dict, sub_component_typ_dict, extra_comps_ac = (
        get_AC_components()
    )
    component_type_dict_lv, sub_component_typ_dict_lv, extra_comps_lv = (
        get_low_voltage_components()
    )
    # update AC + low voltage dict:
    # distribution gird -> distribution grid losses
    key_comp_1 = sub_component_typ_dict["electricity distribution grid"]
    key_comp_2 = sub_component_typ_dict_lv["electricity distribution grid"]
    component_type_dict.update(component_type_dict_lv)
    sub_component_typ_dict.update(sub_component_typ_dict_lv)
    # modify interpretation of distribution grid:
    component_type_dict.pop(key_comp_1)
    component_type_dict.pop(key_comp_2)
    sub_component_typ_dict["electricity distribution grid"] = "grid losses"
    component_type_dict["grid losses"] = "Demand"
    return component_type_dict, sub_component_typ_dict, extra_comps_ac


def get_services_urban_decentral_heat_components():
    component_type_dict_udh = {
        "Services urban dec. heat": "Demand",
        "Industry heat demand": "Demand",
        "Water tanks charger": "Demand",
        "DAC": "Demand",
        "Biomass boiler": "Generation",
        "Gas boiler": "Generation",
        "Oil boiler": "Generation",
        "Heat pump": "Generation",
        "CHP": "Generation",
        "Water tanks discharger": "Generation",
        "Resistive heater": "Generation",
        "Solar thermal": "Generation",
    }
    sub_component_type_dict_udh = {
        "DAC": "DAC",
        "services urban decentral air heat pump": "Heat pump",
        "services urban decentral biomass boiler": "Biomass boiler",
        "services urban decentral gas boiler": "Gas boiler",
        "services urban decentral micro gas CHP": "CHP",
        "services urban decentral oil boiler": "Oil boiler",
        "services urban decentral resistive heater": "Resistive heater",
        "services urban decentral water tanks charger": "Water tanks charger",
        "services urban decentral water tanks discharger": (
            "Water tanks discharger"
        ),
        "services urban decentral solar thermal": "Solar thermal",
        "low-temperature heat for industry": "Industry heat demand",
        "services urban decentral heat": "Services urban dec. heat",
    }
    extra_sub_comps = []
    return (
        component_type_dict_udh,
        sub_component_type_dict_udh,
        extra_sub_comps,
    )


def get_urban_central_heat_components():
    component_type_dict_uch = {
        "DAC": "Demand",
        "Urban central heat": "Demand",
        "Industry heat demand": "Demand",
        "Water tanks charger": "Demand",
        "Gas boiler": "Generation",
        "Heat pump": "Generation",
        "CHP": "Generation",
        "Residual heat": "Generation",
        "Methanol production": "Generation",
        "Resistive heater": "Generation",
        "Solar thermal": "Generation",
        "Water tanks discharger": "Generation",
    }
    sub_component_type_dict_uch = {
        "DAC": "DAC",
        "Fischer-Tropsch": "Residual heat",
        "H2 Electrolysis": "Residual heat",
        "H2 Fuel Cell": "Residual heat",
        "Sabatier": "Residual heat",
        "methanolisation": "Methanol production",
        "urban central air heat pump": "Heat pump",
        "urban central gas CHP": "CHP",
        "urban central gas CHP CC": "CHP",
        "urban central gas boiler": "Gas boiler",
        "urban central resistive heater": "Resistive heater",
        "urban central solid biomass CHP": "CHP",
        "urban central solid biomass CHP CC": "CHP",
        "urban central water tanks charger": "Water tanks charger",
        "urban central water tanks discharger": "Water tanks discharger",
        "low-temperature heat for industry": "Industry heat demand",
        "urban central heat": "Urban central heat",
        "urban central heat vent": "Urban central heat",
        "urban central solar thermal": "Solar thermal",
    }
    extra_sub_comps = []
    return (
        component_type_dict_uch,
        sub_component_type_dict_uch,
        extra_sub_comps,
    )


def get_residential_rural_heat_components():
    component_type_dict_rrh = {
        "Biomass boiler": "Generation",
        "Gas boiler": "Generation",
        "Oil boiler": "Generation",
        "Heat pump": "Generation",
        "CHP": "Generation",
        "Resistive heater": "Generation",
        "Solar thermal": "Generation",
        "Water tanks discharger": "Generation",
        "Water tanks charger": "Demand",
        "Resid. rural heat": "Demand",
    }
    sub_component_type_dict_rrh = {
        "residential rural air heat pump": "Heat pump",
        "residential rural biomass boiler": "Biomass boiler",
        "residential rural gas boiler": "Gas boiler",
        "residential rural ground heat pump": "Heat pump",
        "residential rural heat": "Resid. rural heat",
        "residential rural micro gas CHP": "CHP",
        "residential rural oil boiler": "Oil boiler",
        "residential rural resistive heater": "Resistive heater",
        "residential rural solar thermal": "Solar thermal",
        "residential rural water tanks charger": "Water tanks charger",
        "residential rural water tanks discharger": "Water tanks discharger",
    }
    extra_sub_comps = []
    return (
        component_type_dict_rrh,
        sub_component_type_dict_rrh,
        extra_sub_comps,
    )


def get_residential_urban_decentral_heat_components():
    component_type_dict_rudh = {
        "Biomass boiler": "Generation",
        "Gas boiler": "Generation",
        "Oil boiler": "Generation",
        "Heat pump": "Generation",
        "CHP": "Generation",
        "Resistive heater": "Generation",
        "Solar thermal": "Generation",
        "Water tanks discharger": "Generation",
        "Water tanks charger": "Demand",
        "Resid. urban dec. heat": "Demand",
    }
    sub_component_type_dict_rudh = {
        "residential urban decentral air heat pump": "Heat pump",
        "residential urban decentral biomass boiler": "Biomass boiler",
        "residential urban decentral gas boiler": "Gas boiler",
        "residential urban decentral micro gas CHP": "CHP",
        "residential urban decentral oil boiler": "Oil boiler",
        "residential urban decentral resistive heater": "Resistive heater",
        "residential urban decentral water tanks charger": (
            "Water tanks charger"
        ),
        "residential urban decentral water tanks discharger": (
            "Water tanks discharger"
        ),
        "residential urban decentral heat": "Resid. urban dec. heat",
        "residential urban decentral solar thermal": "Solar thermal",
    }
    extra_sub_comps = []
    return (
        component_type_dict_rudh,
        sub_component_type_dict_rudh,
        extra_sub_comps,
    )


def get_services_rural_heat_components():
    component_type_dict_srh = {
        "Biomass boiler": "Generation",
        "Gas boiler": "Generation",
        "Oil boiler": "Generation",
        "Heat pump": "Generation",
        "CHP": "Generation",
        "Resistive heater": "Generation",
        "Solar thermal": "Generation",
        "Water tanks discharger": "Generation",
        "Water tanks charger": "Demand",
        "Agriculture heat": "Demand",
        "Services rural heat": "Demand",
    }
    sub_component_type_dict_srh = {
        "services rural air heat pump": "Heat pump",
        "services rural biomass boiler": "Biomass boiler",
        "services rural gas boiler": "Gas boiler",
        "services rural ground heat pump": "Heat pump",
        "services rural micro gas CHP": "CHP",
        "services rural oil boiler": "Oil boiler",
        "services rural resistive heater": "Resistive heater",
        "services rural solar thermal": "Solar thermal",
        "services rural water tanks discharger": "Water tanks discharger",
        "agriculture heat": "Agriculture heat",
        "services rural heat": "Services rural heat",
        "services rural water tanks charger": "Water tanks charger",
    }
    extra_sub_comps = []
    return (
        component_type_dict_srh,
        sub_component_type_dict_srh,
        extra_sub_comps,
    )


def get_heat_components():
    carrier_for_balance_list = [
        "services urban decentral heat",
        "urban central heat",
        "residential rural heat",
        "residential urban decentral heat",
        "services rural heat",
    ]
    component_type_dict = {}
    sub_component_typ_dict = {}
    extra_comps = []

    for carrier in carrier_for_balance_list:
        (
            component_type_dict_loc,
            sub_component_typ_dict_loc,
            extra_comps_loc,
        ) = get_components_for_carrier(carrier)
        component_type_dict.update(component_type_dict_loc)
        sub_component_typ_dict.update((sub_component_typ_dict_loc))
        extra_comps.extend(extra_comps_loc)
        unique_extra_comps = pd.Series(extra_comps).drop_duplicates().tolist()

    return component_type_dict, sub_component_typ_dict, unique_extra_comps


if __name__ == "__main__":
    # for debugging
    get_services_urban_decentral_heat_components()
