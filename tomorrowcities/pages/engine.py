import solara
from solara.lab.components.confirmation_dialog import ConfirmationDialog
import time
import random
import json
import pandas as pd
import os
os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
from typing import Callable, List, Optional, Union, cast, Tuple
from pathlib import Path
import ipyleaflet
from ipyleaflet import AwesomeIcon, CircleMarker, Marker, Icon
import numpy as np
import rasterio 
from rasterio.warp import calculate_default_transform, reproject, Resampling
import io
from shapely.geometry import Point, Polygon
import xml
import xml.etree.ElementTree as ET
import logging, sys
import re
import textwrap
from html import escape
#logging.basicConfig(stream=sys.stderr, level=logging.INFO)
import pickle
import datetime
from solara.hooks.dataframe import cross_filter_context
from . import storage, user, session_storage, store_in_session_storage, read_from_session_storage, config
# from .settings import landslide_max_trials
# from .settings import threshold_flood_ds2, threshold_flood_ds3, threshold_flood_ds4, threshold_flood_distance, threshold_road_water_height, threshold_culvert_water_height

landslide_max_trials = solara.reactive(5)
threshold_flood_ds2 = solara.reactive(0.05)
threshold_flood_ds3 = solara.reactive(0.20)
threshold_flood_ds4 = solara.reactive(0.50)

threshold_flood_distance = solara.reactive(10)
threshold_road_water_height = solara.reactive(0.3) 
threshold_culvert_water_height = solara.reactive(1.5)
from ..backend.engine import compute, compute_power_infra, compute_road_infra, generate_exposure, \
    create_tally, generate_metrics
from ..backend.utils import building_preprocess, identity_preprocess, ParameterFile, read_gem_xml, read_gem_xml_fragility, read_gem_xml_vulnerability, getText
from .utilities import S3FileBrowser, extension_list, extension_list_w_dots, PowerFragilityDisplayer, FragilityFunctionDisplayer, \
                        convert_data_for_filter_view, lbl_2_str
from ..components.file_drop import FileDrop, FileDropMultiple
from ..components.notification_center import (
    NotificationCenter,
    clear_notifications,
    log_error as notify_error,
    log_info as notify_info,
    log_success as notify_success,
    log_warning as notify_warning,
)
from .docs import data_import_help
import ipywidgets
from solara.lab import task
import tempfile
from ..backend.exposure_generator import (
    fetch_osm_constraints,
    merge_constraints,
    process_data as process_generated_exposure,
    read_excel_bytes,
    read_geospatial_bytes,
    read_multiple_geospatial_bytes,
)
from ..backend.exposure_generator.logging_utils import clear_log_buffer, set_log_sink
from ..backend.exposure_generator.basic_mode import (
    BASIC_MODE_CONFIG,
    INCOME_OPTIONS,
    URBAN_ATLAS_CLASSES,
    create_basic_mapping_table,
    normalize_basic_mapping_table,
    prepare_basic_landuse,
)

EXPOSURE_DATA_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "data"
BASIC_SYMBOLOGY_SLD_PATH = Path(__file__).resolve().parents[1] / "assets" / "symbology" / "Urban_Atlas_2018_Legend.sld"
BASIC_LUF_PLACEHOLDER = "Select appropriate class..."
BASIC_INCOME_PLACEHOLDER = "Select average income..."


def get_sld_color_map():
    if not BASIC_SYMBOLOGY_SLD_PATH.exists():
        return {}

    try:
        tree = ET.parse(BASIC_SYMBOLOGY_SLD_PATH)
        root = tree.getroot()
        ns = {
            "sld": "http://www.opengis.net/sld",
            "se": "http://www.opengis.net/se",
            "ogc": "http://www.opengis.net/ogc",
        }
        color_map = {}
        for rule in root.findall(".//se:Rule", ns):
            title_elem = rule.find(".//se:Title", ns)
            fill_elem = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', ns)
            if title_elem is None or fill_elem is None or not title_elem.text or not fill_elem.text:
                continue
            title = title_elem.text
            class_name = title.split(":", 1)[1].strip() if ":" in title else title.strip()
            norm_name = re.sub(r"[^a-z0-9]", "", class_name.lower())
            color_map[norm_name] = fill_elem.text
        return color_map
    except Exception:
        return {}


SLD_COLOR_MAP = get_sld_color_map()


def landuse_style(fill_color: str):
    return {"color": "#666666", "fillColor": fill_color, "weight": 1, "fillOpacity": 0.7}

tally_counter = solara.reactive(0)
tally_filter = solara.reactive(None)
building_filter = solara.reactive(None)
landuse_filter = solara.reactive(None)
selected_tab = solara.reactive(None)
MAP_INFO_TAB_INDEX = 2
scenario_name = solara.reactive("")
is_public = solara.reactive(True)
save_status = solara.reactive("")
center_default = (41.01,28.98)
population_displacement_consensus = solara.reactive(2)
def create_new_app_state():
    return solara.reactive({
    'infra': solara.reactive(["building"]),
    'hazard': solara.reactive("flood"),
    'hazard_list': ["earthquake","flood"],
    'datetime_analysis': datetime.datetime.utcnow(),
    'landslide_trigger_level': solara.reactive('moderate'),
    'landslide_trigger_level_list': ['minor','moderate','severe'],
    'preserve_edge_directions': solara.reactive(False),
    'earthquake_intensity_unit': solara.reactive('m/s2'),
    'earthquake_simulation_methods': ["legacy","monte carlo"],
    'earthquake_simulation_method_selected': solara.reactive('legacy'),
    'earthquake_simulation_trial_count': solara.reactive(5),
    'cdf_median_increase_in_percent': solara.reactive(0.2),
    'threshold_increase_culvert_water_height': solara.reactive(0.2),
    'threshold_increase_road_water_height': solara.reactive(0.2),
    'damage_curve_suppress_factor': solara.reactive(0.9),
    'flood_depth_reduction': solara.reactive(0.2),
    'dialog_message_to_be_shown': solara.reactive(None),
    'seed': solara.reactive(42),
    'version': '1.0',
    'layers' : {
        'parameter': {
            'render_order': 0,
            'map_info_tooltip': 'Number of records',
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'attributes_required': [set(['unnamed: 0'])],
            'attributes': [set(['unnamed: 0'])]},
        'landuse': {
            'render_order': 20,
            'map_info_tooltip': 'Number of landuse zones',
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['luf'],
            'attributes_required': [set(['geometry', 'zoneid', 'luf', 'population', 'densitycap', 'avgincome'])],
            'attributes': [set(['geometry', 'zoneid', 'luf', 'population', 'densitycap', 'floorarat', 'setback', 'avgincome'])]},
        'constraint': {
            'render_order': 25,
            'map_info_tooltip': 'Number of exclusion/alignment features',
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': [],
            'attributes_required': [set(['geometry'])],
            'attributes': [set(['geometry'])]},
        'building': {
            'render_order': 50,
            'map_info_tooltip': 'Number of buildings',
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'pre_processing': building_preprocess,
            'extra_cols': {'freqincome': '', 'ds': 0,
                            'node_id': None,'hospital_access': True, 'has_power': True, 'casualty': 0},
            'filter_cols': ['expstr'],
            'attributes_required': [set(['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac'])],
            'attributes': [set(['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac'])]},
        'household': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of households',
            'pre_processing': identity_preprocess,
            'extra_cols': {'node_id': None, 'hospital_access': True, 'has_power':True,'hospital_has_power':True},
            'filter_cols': ['income'],
            'attributes_required': [set(['hhid', 'nind', 'income', 'bldid', 'commfacid'])],
            'attributes': [set(['hhid', 'nind', 'income', 'bldid', 'commfacid'])]},
        'individual': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of individuals',
            'pre_processing': identity_preprocess,
            'extra_cols': {'facility_access':True},
            'filter_cols': ['gender'],
            'attributes_required': [set(['individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid'])],
            'attributes': [set(['individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid'])]},
        'intensity': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of intensity measurements',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['im'],
            'attributes_required': [set(['geometry','im']), set(['geometry','pga'])],
            'attributes': [set(['geometry','im']), set(['geometry','pga'])]},
        'fragility': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of records in fragility configuration',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['expstr'],
            'attributes_required': [set(['expstr','muds1_g','muds2_g','muds3_g','muds4_g','sigmads1','sigmads2','sigmads3','sigmads4'])],
            'attributes': [set(['expstr','muds1_g','muds2_g','muds3_g','muds4_g','sigmads1','sigmads2','sigmads3','sigmads4'])]},
        'landslide fragility': {
            'render_order': 0,
            'map_info_tooltip': 'Number of landslide fragility records',
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['expstr'],
            'attributes_required': [set(['expstr','susceptibility','minor','moderate','severe'])],
            'attributes': [set(['expstr','susceptibility','minor','moderate','severe','description'])]},            
        'vulnerability': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of records in vulnerabilty configuration',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['expstr'],
            'attributes_required': [set(['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5','hw6'])],
            'attributes': [set(['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5','hw6'])]},
        'gem_vulnerability': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of functions in gem vulnerabilty',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['id'],
            'attributes_required': [set(['id', 'assetCategory', 'lossCategory', 'description', 'vulnerabilityFunctions'])],
            'attributes': [set(['id', 'assetCategory', 'lossCategory', 'description', 'vulnerabilityFunctions'])],
        },
        'gem_fragility': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of functions in gem fragility',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['id'],
            'attributes_required': [set(['id', 'assetCategory', 'lossCategory', 'description', 'fragilityFunctions'])],
            'attributes': [set(['id', 'assetCategory', 'lossCategory', 'description', 'fragilityFunctions'])],
        },
        'power nodes': {
            'render_order': 90,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of electrical power nodes',
            'pre_processing': identity_preprocess,
            'extra_cols': {'ds': 0, 'is_damaged': False, 'is_operational': True},
            'filter_cols': ['node_id'],
            'attributes_required': [set(['geometry', 'node_id', 'pwr_plant', 'n_bldgs'])],
            'attributes': [set(['geometry', 'fltytype', 'strctype', 'utilfcltyc', 'indpnode', 'guid', 
                         'node_id', 'x_coord', 'y_coord', 'pwr_plant', 'serv_area', 'n_bldgs', 
                         'income', 'eq_frgl'])]},
        'power edges': {
            'render_order': 80,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of connections in power grid',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['edge_id'],
            'attributes_required': [set(['geometry','from_node','to_node', 'edge_id'])],
            'attributes': [set(['from_node', 'direction', 'pipetype', 'edge_id', 'guid', 'capacity', 
                         'geometry', 'to_node', 'length'])]},
        'power fragility': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Number of records in fragility configuration for power',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['vuln_string'],
            'attributes_required': [set(['vuln_string', 'med_slight', 'med_moderate', 'med_extensive', 'med_complete', 
                         'beta_slight', 'beta_moderate', 'beta_extensive', 'beta_complete'])],
            'attributes': [set(['vuln_string', 'med_slight', 'med_moderate', 'med_extensive', 'med_complete', 
                         'beta_slight', 'beta_moderate', 'beta_extensive', 'beta_complete', 'description'])]},
        'road nodes': {
            'render_order': 90,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': '# nodes in road network',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['node_id'],
            'attributes_required': [set(['geometry', 'node_id'])],
            'attributes': [set(['geometry', 'node_id'])]},
        'road edges': {
            'render_order': 80,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': '# edges in road network',
            'pre_processing': identity_preprocess,
            'extra_cols': {'ds': 0,'is_damaged': False},
            'filter_cols': ['bridge_type'],
            'attributes_required': [set(['geometry','from_node','to_node', 'edge_id','bridge_type','length'])],
            'attributes': [set(['geometry','from_node','to_node', 'edge_id','bridge','bridge_type','length'])]},
        'road fragility': {
            'render_order': 0,
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'map_info_tooltip': 'Road fragility records',
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'filter_cols': ['vuln_string'],
            'attributes_required': [set(['vuln_string', 'med_slight', 'med_moderate', 'med_extensive', 'med_complete', 
                         'dispersion'])],
            'attributes': [set(['vuln_string', 'med_slight', 'med_moderate', 'med_extensive', 'med_complete', 
                         'dispersion'])]}
            },
    'center': solara.reactive(center_default),
    'selected_layer' : solara.reactive(None),    
    'render_count': solara.reactive(0),
    'bounds': solara.reactive(None),
    'selected_policies': solara.reactive([]),
    'policies': {
        '1': {'id':1, 'label': 'P1', 'description': 'Land and tenure security program'},
        '2': {'id':2, 'label': 'P2', 'description': 'Housing retrofitting'},
        '3': {'id':3, 'label': 'P3', 'description': 'Investment in water and sanitation'},
        '4': {'id':4, 'label': 'P4', 'description': 'Investments in road networks'},
        '5': {'id':5, 'label': 'P5', 'description': 'Access to more shelters'},
        '6': {'id':6, 'label': 'P6', 'description': 'Funding community networks'},
        #'7': {'id':7, 'label': 'P7', 'description': 'Support for local livelihoods'},
        '8': {'id':8, 'label': 'P8', 'description': 'Cash transfers to vulnerable groups'},
        '9': {'id':9, 'label': 'P9', 'description': 'Waste collection and river cleaning program'},
        #'10': {'id':10, 'label': 'P10', 'description': 'Environmental protection zones'},
        #'11': {'id':11, 'label': 'I1', 'description': 'DRR-oriented zoning and urban transformation', 'applied': solara.reactive(False)},
        #'12': {'id':12, 'label': 'I2', 'description': 'Increased monitoring and supervision on new constructions in terms of disaster-resilience', 'applied': solara.reactive(False)},
        #'13': {'id':13, 'label': 'I3', 'description': 'Taking social equality into consideration in the making of urbanisation and DRR policies', 'applied': solara.reactive(False)},
        #'14': {'id':14, 'label': 'I4', 'description': 'Establishing financial supports to incentivise the public, which can be referred to as "policy financing"', 'applied': solara.reactive(False)},
        #'15': {'id':15, 'label': 'I5', 'description': 'Awareness raising on disasters and disaster risk reduction', 'applied': solara.reactive(False)},
        #'16': {'id':16, 'label': 'I6', 'description': 'Strengthening of Büyükçekmece bridge against earthquake and tsunami risks', 'applied': solara.reactive(False)},
        #'17': {'id':17, 'label': 'I7', 'description': 'Strengthening of public buildings (especially schools) against earthquake', 'applied': solara.reactive(False)},
        #'18': {'id':18, 'label': 'I8', 'description': 'Increased financial assistance for people whose apartments are under urban transformation', 'applied': solara.reactive(False)},
        #'19': {'id':19, 'label': 'I9', 'description': 'Increased monitoring and supervision of building stock', 'applied': solara.reactive(False)},
        #'20': {'id':20, 'label': 'I10', 'description': 'Improvement of infrastructure', 'applied': solara.reactive(False)},
    },
    'implementation_capacity_score': solara.reactive("high"),
    'data_import_method': solara.reactive("drag&drop"),
    'map_info_button': solara.reactive("summary"),
    'map_info_detail': solara.reactive({}),
    'tally_filter_cols': ['zoneid','ds','income','material','gender','age','head','eduattstat','luf','occupancy'],
    'tally_is_available': solara.reactive(False),
    'metrics_realized': solara.reactive(None),
    'metrics': {
        "metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": 100},
        "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": 100},
        "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": 100},
        "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 100},
        "metric5": {"desc": "Number of households displaced", "value": 0, "max_value": 100},
        "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": 100},
        "metric7": {"desc": "Population displacement", "value": 0, "max_value":100},
        "metric8": {"desc": "Number of casualties", "value": 0, "max_value":100},}})

layers = create_new_app_state()

metric_icon1 = 'tomorrowcities/content/icons/metric1.png'
metric_icon2 = 'tomorrowcities/content/icons/metric2.png'
metric_icon3 = 'tomorrowcities/content/icons/metric3.png'
metric_icon4 = 'tomorrowcities/content/icons/metric4.png'
metric_icon5 = 'tomorrowcities/content/icons/metric5.png'
metric_icon6 = 'tomorrowcities/content/icons/metric6.png'
metric_icon7 = 'tomorrowcities/content/icons/metric7.png'
metric_icon8 = 'tomorrowcities/content/icons/metric8.png'

ds_to_color = {0: '#2c7bb6', 1: '#abd9e9', 2:'#ffffbf', 3:'#fdae61', 4: '#d7191c'}
# approximate color names when hex codes can't be used
ds_to_color_approx = {0: 'darkblue', 1: 'lightblue', 2:'beige', 3:'orange', 4: 'red'}
def show_dialog_message(topic):
    layers.value['dialog_message_to_be_shown'].value = topic

def clear_help_topic():
    layers.value['dialog_message_to_be_shown'].value = None

def assign_nested_value(dictionary, keys, value):
    for key in keys[:-1]:
        dictionary = dictionary.setdefault(key, {})
    dictionary[keys[-1]] = value

def get_nested_value(dictionary, keys):
    for key in keys[:-1]:
        dictionary = dictionary[key]
    return dictionary[keys[-1]]

def clone_app_state(dictionary):
    dict_pars = []
    stack = [((), dictionary)]
    while stack:
        path, current_dict = stack.pop()
        for key, value in current_dict.items():
            if str(key).startswith('_'):
                continue
            if isinstance(value, dict):
                stack.append((path + (key,), value))
            else:
                keys = list(path + (key,))
                if isinstance(value,solara.toestand.Reactive):
                    value = value.value
                dict_pars.append((keys, value))
    
    new_dict = dict()
    for keys, value in dict_pars:
        assign_nested_value(new_dict, keys, value)
    return new_dict

def load_from_state(source_dict):
    stack = [((), layers.value)]
    while stack:
        path, current_dict = stack.pop()
        for key, value in current_dict.items():
            if isinstance(value, dict):
                stack.append((path + (key,), value))
            else:
                keys = list(path + (key,))
                src_value = get_nested_value(source_dict, keys)
                if isinstance(value,solara.toestand.Reactive):
                    assign_nested_value(layers.value, keys, solara.reactive(src_value))
                else:
                    assign_nested_value(layers.value, keys, src_value)

def store_info_to_session():
    store_in_session_storage('population_displacement_consensus', population_displacement_consensus.value)
    for layer_name in layers.value['layers'].keys():
        store_in_session_storage(layer_name, {
            'data':layers.value['layers'][layer_name]['data'].value,
            'df': layers.value['layers'][layer_name]['df'].value,
        })
    for attr in ['hazard', 'tally_is_available', 'selected_policies','center',
                'bounds','selected_layer','render_count','implementation_capacity_score',
                'data_import_method','map_info_button','map_info_detail']:
        print('saving',attr, layers.value[attr].value)
        store_in_session_storage(attr, layers.value[attr].value)

def reload_info_from_session():
    print('reloading info from session')
    session_data = read_from_session_storage('population_displacement_consensus')
    if session_data is not None:
        population_displacement_consensus.set(session_data)
    for layer_name in layers.value['layers'].keys():
        session_data = read_from_session_storage(layer_name)
        if session_data is not None:
            if layers.value['layers'][layer_name]['data'].value is None:
                layers.value['layers'][layer_name]['data'].set(session_data['data'])
            if layers.value['layers'][layer_name]['df'].value is None:
                layers.value['layers'][layer_name]['df'].set(session_data['df'])
       
    for attr in ['hazard', 'tally_is_available', 'selected_policies','center',
                'bounds','selected_layer','render_count','implementation_capacity_score',
                'data_import_method','map_info_button','map_info_detail']:
        session_data = read_from_session_storage(attr)
        if session_data is not None:
            print('reloading',attr, session_data)
            layers.value[attr].set(session_data)

reset_counter = solara.reactive(0)

def reset_session():
    reset_counter.value += 1
    clear_notifications()
    scenario_name.set("")
    is_public.set(True)
    save_status.set("")
    store_in_session_storage('population_displacement_consensus', None)
    for layer_name in layers.value['layers'].keys():
        store_in_session_storage(layer_name, None)
    for attr in ['hazard', 'tally_is_available', 'selected_policies','center',
                'bounds','selected_layer','render_count','implementation_capacity_score',
                'data_import_method','map_info_button','map_info_detail']:
        store_in_session_storage(attr, None)
    store_in_session_storage('tally', None)
    store_in_session_storage('tally_geo', None)
    store_in_session_storage('tally_minimal', None)  
    layers.set(create_new_app_state().value)
    tally_filter.set(None)
    building_filter.set(None)
    landuse_filter.set(None)
    tally_counter.set(0)

def create_metadata(data):
    m = dict()
    m['hazard'] = data['hazard']
    m['infra'] = data['infra']
    cleaned_name = scenario_name.value.strip()
    m['scenario_name'] = cleaned_name if cleaned_name else None
    m['datetime_analysis'] = data['datetime_analysis']
    m['datetime_upload'] = datetime.datetime.utcnow()
    m['is_public'] = is_public.value
    if user.value:
        m['user_id'] = user.value.get_unique_id()
    else:
        m['user_id'] = None
    return m

def build_scenario_basename(metadata):
    date_string = metadata['datetime_upload'].strftime('%Y%m%d%H%M%S')
    cleaned_name = (metadata.get('scenario_name') or "").strip()
    slug = re.sub(r"[^A-Za-z0-9]+", "_", cleaned_name).strip("_")
    if not slug:
        slug = "SCENARIO"
    
    is_pub = metadata.get('is_public', True)
    if is_pub:
        return f'PUBLIC_{date_string}_{slug}'
    else:
        user_id = metadata.get('user_id') or "anonymous"
        user_id_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", user_id)
        return f'PRIVATE_{date_string}_{user_id_slug}_{slug}'

@task 
def save_app_state():
    save_status.set("")
    try:
        data = clone_app_state(layers.value)
        metadata = create_metadata(data)
        print('metadata', metadata)
        basename = build_scenario_basename(metadata)
        for ext, var in zip(['data','metadata'],[data,metadata]):
            filename = f'{basename}.{ext}'
            with tempfile.TemporaryDirectory() as temp_dir:
                with open(os.path.join(temp_dir,filename), 'wb') as fileObj:
                    pickle.dump(var, fileObj)
                if storage.value is not None:
                    print('uploading file', filename)
                    storage.value.upload_file(os.path.join(temp_dir,filename), filename)
                    os.unlink(os.path.join(temp_dir, filename))
        save_status.set("success")
    except Exception as e:
        save_status.set(f"error: {str(e)}")
        raise e

def generic_layer_colors(feature):
    return None

def ensure_map_info_state():
    if 'map_info_detail' not in layers.value:
        layers.value['map_info_detail'] = solara.reactive({})
    if 'map_info_button' not in layers.value:
        layers.value['map_info_button'] = solara.reactive("summary")

def open_map_info(properties):
    ensure_map_info_state()
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")
    selected_tab.set(MAP_INFO_TAB_INDEX)

def generic_layer_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def building_colors(feature):
    ds = feature['properties']['ds']
    return {'fillColor': ds_to_color[ds], 'color': 'black'}

def building_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def road_node_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def road_edge_colors(feature):
    is_damaged = feature['properties']['is_damaged']
    if is_damaged:
        return {'color': 'black',  'dashArray': '8'}
    else:
        return {'color': 'black',  'dashArray': '0'}

def road_edge_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def power_edge_colors(feature):
    is_damaged = feature['properties'].get('is_damaged', False)
    if is_damaged:
        return {'color': 'blue',  'dashArray': '8'}
    else:
        return {'color': 'blue',  'dashArray': '0'}

def power_edge_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def landuse_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def intensity_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties)

def landuse_colors(feature):
    properties = feature.get("properties", {})
    luf_value = str(properties.get("luf", "") or "")
    norm_luf = re.sub(r"[^a-z0-9]", "", luf_value.lower())
    if norm_luf in SLD_COLOR_MAP:
        return landuse_style(SLD_COLOR_MAP[norm_luf])
    for key, color in SLD_COLOR_MAP.items():
        if key and (key in norm_luf or norm_luf in key):
            return landuse_style(color)

    luf_type = set(luf_value.lower().replace('(','').replace(')','').split())
    if {'continuous', 'urban', 'fabric'}.issubset(luf_type):
        return landuse_style('#800000')
    if {'discontinuous', 'dense', 'urban', 'fabric'}.issubset(luf_type):
        return landuse_style('#BF0000')
    if {'discontinuous', 'medium', 'density', 'urban', 'fabric'}.issubset(luf_type):
        return landuse_style('#FF4040')
    if {'discontinuous', 'low', 'density', 'urban', 'fabric'}.issubset(luf_type):
        return landuse_style('#FF8080')
    if {'discontinuous', 'very', 'low', 'density', 'urban', 'fabric'}.issubset(luf_type):
        return landuse_style('#FFBFBF')
    if {'isolated', 'structures'}.issubset(luf_type):
        return landuse_style('#CC6666')
    if {'industrial', 'commercial', 'public', 'military', 'private', 'units'}.issubset(luf_type):
        return landuse_style('#CC4DF2')
    if {'fast', 'transit', 'roads'}.issubset(luf_type):
        return landuse_style('#959595')
    if {'other', 'roads'}.issubset(luf_type):
        return landuse_style('#B3B3B3')
    if {'railways'}.issubset(luf_type) or {'railway'}.issubset(luf_type):
        return landuse_style('#595959')
    if {'port', 'areas'}.issubset(luf_type):
        return landuse_style('#E6CCCC')
    if {'airports'}.issubset(luf_type) or {'airport'}.issubset(luf_type):
        return landuse_style('#E6CCCC')
    if {'mineral', 'extraction'}.issubset(luf_type):
        return landuse_style('#A64D00')
    if {'construction', 'sites'}.issubset(luf_type):
        return landuse_style('#FF4DFF')
    if {'without', 'current', 'use'}.issubset(luf_type):
        return landuse_style('#FFA6FF')
    if {'green', 'urban', 'areas'}.issubset(luf_type):
        return landuse_style('#A6FF80')
    if {'sports', 'leisure'}.issubset(luf_type) or {'recreational'}.issubset(luf_type):
        return landuse_style('#A6E64D')
    if {'arable', 'land'}.issubset(luf_type):
        return landuse_style('#FFFFA8')
    if {'permanent', 'crops'}.issubset(luf_type):
        return landuse_style('#E68000')
    if {'pastures'}.issubset(luf_type) or {'pasture'}.issubset(luf_type):
        return landuse_style('#E6A64D')
    if {'complex', 'mixed', 'cultivation'}.issubset(luf_type):
        return landuse_style('#E6E64D')
    if {'orchards'}.issubset(luf_type):
        return landuse_style('#F2A64D')
    if {'forests'}.issubset(luf_type) or {'forest'}.issubset(luf_type):
        return landuse_style('#00A600')
    if {'herbaceous'}.issubset(luf_type):
        return landuse_style('#A6F200')
    if {'open', 'spaces', 'vegetation'}.issubset(luf_type):
        return landuse_style('#E6E64D')
    if {'wetlands'}.issubset(luf_type) or {'wetland'}.issubset(luf_type):
        return landuse_style('#A6A6FF')
    if {'water', 'bodies'}.issubset(luf_type) or {'water'}.issubset(luf_type):
        return landuse_style('#00CCFF')
    if luf_type == {'residential'}:
        return landuse_style('#FF4040')
    if {'high', 'residential', 'density'}.issubset(luf_type):
        return landuse_style('#800000')
    if {'medium', 'residential', 'density'}.issubset(luf_type) or {'moderate', 'residential', 'density'}.issubset(luf_type):
        return landuse_style('#FF4040')
    if {'low', 'residential', 'density'}.issubset(luf_type):
        return landuse_style('#FF8080')
    if {'commercial', 'residential'}.issubset(luf_type):
        return landuse_style('#CC4DF2')
    if {'industry'}.issubset(luf_type) or {'industrial'}.issubset(luf_type):
        return landuse_style('#CC4DF2')
    if {'road'}.issubset(luf_type):
        return landuse_style('#B3B3B3')
    if {'public'}.issubset(luf_type):
        return landuse_style('#CC4DF2')
    return landuse_style('orange')



def create_map_layer(df, name):
    if name == "intensity":
        # Take the largest 500_000 values to display
        im_col = 'pga' if 'pga' in df.columns else 'im'
        df_non_zero = df[df[im_col] > 0]
        df_limited = df_non_zero.sample(min(len(df_non_zero),500_000)).copy()
        df_limited[im_col] = df_limited[im_col] / df_limited[im_col].max()
        #df_limited = df.sort_values(by=im_col,ascending=False).head(500_000)
        locs = np.array([df_limited.geometry.y.to_list(), df_limited.geometry.x.to_list(), df_limited[im_col].to_list()]).transpose().tolist()
        heatmap_layer = ipyleaflet.Heatmap(locations=locs, radius = 3, blur = 2, name = name)
        clickable_df = df_non_zero.sample(min(len(df_non_zero),5000)).copy()
        info_layer = ipyleaflet.GeoJSON(
            data=json.loads(clickable_df.to_json()),
            name=f"{name}-info",
            point_style={'radius': 5, 'color': 'white', 'fillOpacity': 0.2, 'opacity': 0, 'weight': 15},
            style={"opacity": 0, "fillOpacity": 0.2, "weight": 0},
            hover_style={"opacity": 0.8, "fillOpacity": 0.8, "weight": 1, "color": "#ffffff"},
        )
        info_layer.on_click(intensity_click_handler)
        map_layer = ipyleaflet.LayerGroup(layers=(heatmap_layer, info_layer), name=name)
    elif name == "landuse":
        style_callback = landuse_colors if "luf" in df.columns else generic_layer_colors
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '0', 'fillOpacity': 1, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 1},
            style_callback=style_callback)
        map_layer.on_click(landuse_click_handler)
        map_layer = ipyleaflet.LayerGroup(layers=(map_layer,), name=name)
    elif name == "building":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '0', 'fillOpacity': 1, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 1},
            style_callback=building_colors)
        map_layer.on_click(building_click_handler)
        map_layer = ipyleaflet.LayerGroup(layers=(map_layer,), name=name)
    elif name == "road edges":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            hover_style={'color': 'orange'},
            style_callback=road_edge_colors)
        map_layer.on_click(road_edge_click_handler)
    elif name == "road nodes":
        df_squares = df.copy()
        half_side = 0.00005
        df_squares['geometry']  = df['geometry'].apply(lambda point: Polygon([
                    (point.x - half_side, point.y - half_side),
                    (point.x + half_side, point.y - half_side),
                    (point.x + half_side, point.y + half_side),
                    (point.x - half_side, point.y + half_side)
                ]))
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df_squares.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '0', 'fillOpacity': 0.8, 'weight': 1},
            hover_style={'color': 'orange', 'dashArray': '0', 'fillOpacity': 0.5})
        map_layer.on_click(road_node_click_handler)
    elif name == "power nodes":
        markers = []
        for index, node in df.iterrows():
            x = node.geometry.x
            y = node.geometry.y
            # marker_color = ds_to_color_approx[node['ds']]
            # icon_name = 'fa-industry' if node['pwr_plant'] == 1 else 'bolt'
            # icon_color = 'black'
            # marker = Marker(icon=AwesomeIcon(
                        # name=icon_name,
                        # marker_color=marker_color,
                        # icon_color=icon_color,
                        # spin=False
                    # ),location=(y,x),title=f'{node["node_id"]}',draggable=False)
            # icon_urls = '/static/public/icons/power_plant.png' if node['pwr_plant'] == 1 else '/static/public/icons/pole.png'
            # icons = Icon(icon_url=icon_urls, icon_size=[35,35]) if node['pwr_plant'] == 1 else Icon(icon_url=icon_urls, icon_size=[15,20])
            # marker = Marker(icon=icons, location=(y,x), title=f'{node["node_id"]}', draggable=False)
            if node['is_operational'] == True:        
                icon_urls = '/static/public/icons/power_plant0.png' if node['pwr_plant'] == 1 else '/static/public/icons/pole0.png'
                icons = Icon(icon_url=icon_urls, icon_size=[30,30]) if node['pwr_plant'] == 1 else Icon(icon_url=icon_urls, icon_size=[15,20])
                marker = Marker(icon=icons, location=(y,x), title=f'{node["node_id"]}', draggable=False)
            else:
                icon_urls = '/static/public/icons/power_plant4.png' if node['pwr_plant'] == 1 else '/static/public/icons/pole4.png'
                icons = Icon(icon_url=icon_urls, icon_size=[30,30]) if node['pwr_plant'] == 1 else Icon(icon_url=icon_urls, icon_size=[15,20])
                marker = Marker(icon=icons, location=(y,x), title=f'{node["node_id"]}', draggable=False)
                
            markers.append(marker)
        map_layer= ipyleaflet.MarkerCluster(markers=markers, name = name,
                                                   disable_clustering_at_zoom=5)
    elif name == 'power edges':
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            hover_style={'color': 'orange'},
            style_callback=power_edge_colors)
        map_layer.on_click(power_edge_click_handler)
    else:
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '9', 'fillOpacity': 0.5, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 0.5},
            style_callback=generic_layer_colors)
        map_layer.on_click(generic_layer_click_handler)
    return map_layer

def fast_transform_xy(T,x,y):
    TI = rasterio.transform.IDENTITY.translation(0.5, 0.5)
    TI_mat = np.array([[TI[0],TI[1],TI[2]],[TI[3],TI[4],TI[5]]])
    T_mat = np.array([[T[0],T[1],T[2]],[T[3],T[4],T[5]]])
    n = len(x)
    first_input = np.ones((3,n))
    first_input[0,:] = x
    first_input[1,:] = y
    first_pass = np.dot(TI_mat, first_input)
    second_inp = np.concatenate([first_pass[[1]],first_pass[[0]],first_input[[2]]])    
    second_pass = np.dot(T_mat, second_inp)
    return second_pass[0], second_pass[1]

def read_tiff(file_bytes):
    byte_io = io.BytesIO(file_bytes)
    with rasterio.open(byte_io) as src:
        if src.nodata == None:
            ims = src.read()
            # when nodata is not specificed, do my best to clean data
            # no negative intensity
            ims[ims < 0] = 0
            # very large values indicate nodata
            ims[ims > 100000] = 0
        else:
            # replace nodata with zero
            ims = src.read(masked=True)
            ims = ims.filled(fill_value=0)
        band_names = list(src.descriptions)
    n_bands = ims.shape[0] if len(ims.shape) == 3 else 1
    for b,name in enumerate(src.descriptions):
        if name is None:
            if b == 0:
                band_names[b] = 'im'
            else:
                band_names[b] = f'im{b+1}'
    current_crs = src.crs
    target_crs = 'EPSG:4326'
    transform, width, height = calculate_default_transform(current_crs, target_crs, src.width, src.height, *src.bounds)
    ims_transformed = np.zeros((n_bands, height, width))

    print('start reproject ..........')
    for b in range(n_bands):
        reproject(
            source=ims[b],
            destination=ims_transformed[b],
            src_transform=src.transform,
            src_crs=current_crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=Resampling.nearest)

    lon_pos, lat_pos = np.meshgrid(range(width),range(height))
    print('start transform ..........')
    #lon, lat = rasterio.transform.xy(transform,lat_pos.flatten(),lon_pos.flatten())
    lon, lat = fast_transform_xy(transform,lat_pos.flatten(),lon_pos.flatten())
    print('start dataframe ..........')
    gdf = gpd.GeoDataFrame({band_names[i]:ims_transformed[i].flatten() for i in range(n_bands)},
            geometry = gpd.points_from_xy(lon, lat, crs="EPSG:4326"))
    #gdf = gdf.rename(columns={0:'im'})
    # return only the non-zero intensity measures
    return gdf[(gdf.drop(columns='geometry')>0).any(axis=1)]
    #return gdf.sort_values(by='im',ascending=False).head(10000)


@solara.component
def ParameterFileWidget(parameter_file: ParameterFile):
    df_nc, ipdf, df1, df2, df3 = parameter_file.get_sheets()
    nonempty_layers = {'sheet 1': solara.reactive(df_nc),
                        'sheet 2': solara.reactive(ipdf),
                        'sheet 3': solara.reactive(df1),
                        'sheet 4': solara.reactive(df2),
                        'sheet 5': solara.reactive(df3)}
    nonempty_layer_names = list(nonempty_layers.keys())
    selected, set_selected = solara.use_state('sheet 1')
    solara.ToggleButtonsSingle(value=selected, on_value=set_selected, 
                            values=nonempty_layer_names)
    data = nonempty_layers[selected].value
    solara.DataFrame(data, items_per_page=5)

@solara.component
def VulnerabilityFunctionDisplayer(vuln_func):
    vuln_func, _ = solara.use_state_or_update(vuln_func)

    x = vuln_func['imls']
    y = vuln_func['meanLRs']
    s = vuln_func['covLRs']
    xlabel = vuln_func['imt']
   
    options = { 
        'title': {
            'text': vuln_func['id'],
            'left': 'center'},
        'tooltip': {
            'trigger': 'axis',
            'axisPointer': {
                'type': 'cross'
            }
        },
        #'legend': {'data': ['Covariance','Mean']},
        'xAxis': {
            'axisTick': {
                'alignWithLabel': True
            },
            'data': list(x),
            'name': xlabel,
            'nameLocation': 'middle',
            'nameTextStyle': {'verticalAlign': 'top','padding': [10, 0, 0, 0]}
        },
        'yAxis': [
            {
                'type': 'value',
                'name': "Covariance",
                'position': 'left',
                'alignTicks': True,
                'axisLine': {
                    'show': True,
                    'lineStyle': {'color': 'green'}}
            },
            {
                'type': 'value',
                'name': "Mean",
                'position': 'right',
                'alignTicks': True,
                'axisLine': {
                    'show': True,
                    'lineStyle': {'color': 'blue'}}
            },

        ],
        'series': [
            {
            'name': 'Mean',
            'data': list(y),
            'type': 'line',
            'yAxisIndex': 1
            },
            {
            'name': 'Covariance',
            'data': list(s),
            'type': 'line',
            'yAxisIndex': 0
            },
        ],
    }
    solara.FigureEcharts(option=options) 


@solara.component
def VulnerabiliyDisplayer(vuln_xml: dict):
    vuln_xml, set_vuln_xml = solara.use_state_or_update(vuln_xml)

    func_labels = [f'{v["imt"]}---{v["id"]}' for v in vuln_xml['vulnerabilityFunctions']]
    func_label, set_func_label  = solara.use_state_or_update(func_labels[0])

    with solara.GridFixed(columns=2):
        with solara.Column(gap="1px"):
            solara.Text('Description:',style={'fontWeight': 'bold'})
            with solara.Row(justify="left"):
                solara.Text(f'{vuln_xml["description"]}')   
            with solara.GridFixed(columns=2,row_gap="1px"):
                solara.Text('Asset Category:',style={'fontWeight': 'bold'})
                with solara.Row(justify="right"):
                    solara.Text(f'{vuln_xml["assetCategory"]}')
                solara.Text('Loss Category:',style={'fontWeight': 'bold'})
                with solara.Row(justify="right"):
                    solara.Text(f'{vuln_xml["lossCategory"]}')
                solara.Text('# of vulnerability functions:',style={'fontWeight': 'bold'})
                with solara.Row(justify="right"):
                    solara.Text(f'{len(vuln_xml["vulnerabilityFunctions"])}')      
            solara.Text('Select vulnerability function:',style={'fontWeight': 'bold'})
            solara.Select(label='',value=func_label, values=func_labels,
                        on_value=set_func_label)
        with solara.Column():
            VulnerabilityFunctionDisplayer(vuln_xml['vulnerabilityFunctions'][func_labels.index(func_label)])


@solara.component
def FragilityDisplayer(vuln_xml: dict):
    vuln_xml, set_vuln_xml = solara.use_state_or_update(vuln_xml)

    func_labels = [f'{v["imt"]}---{v["id"]}' for v in vuln_xml['fragilityFunctions']]
    func_label, set_func_label  = solara.use_state_or_update(func_labels[0])

    with solara.GridFixed(columns=2):
        with solara.Column(gap="1px"):
            solara.Text('Description:',style={'fontWeight': 'bold'})
            with solara.Row(justify="left"):
                solara.Text(f'{vuln_xml["description"]}')   
            with solara.GridFixed(columns=2,row_gap="1px"):
                solara.Text('Asset Category:',style={'fontWeight': 'bold'})
                with solara.Row(justify="right"):
                    solara.Text(f'{vuln_xml["assetCategory"]}')
                solara.Text('Loss Category:',style={'fontWeight': 'bold'})
                with solara.Row(justify="right"):
                    solara.Text(f'{vuln_xml["lossCategory"]}')
                solara.Text('# of vulnerability functions:',style={'fontWeight': 'bold'})
                with solara.Row(justify="right"):
                    solara.Text(f'{len(vuln_xml["fragilityFunctions"])}')      
            solara.Text('Select vulnerability function:',style={'fontWeight': 'bold'})
            solara.Select(label='',value=func_label, values=func_labels,
                        on_value=set_func_label)
        with solara.Column():
            FragilityFunctionDisplayer(vuln_xml['fragilityFunctions'][func_labels.index(func_label)])


@solara.component
def MetricParameters():
    with solara.Details(summary="Calculation Parameters"):
        with solara.Card(title='Metric Parameters', subtitle='Choose metric calculation parameters'):
            solara.Select(label='population displacement consensus (default:2)', values=[1,2,3,4], value=population_displacement_consensus)
            with solara.Tooltip('Minimum number of conditions to claim a population displacement. Click for more info.'):
                solara.Button(icon_name="mdi-help-box", attributes={"href": "https://github.com/TomorrowsCities/tomorrowscities/wiki/4%E2%80%90Engine#parameters", "target": "_blank"}, text=True, outlined=False)

        with solara.Card(title='Earthquake Parameters', subtitle='Choose the parameters for the earthquake simulations'):
            with solara.Column(gap='10px'):
                solara.Select(label='unit of earthquake intensity map', values=['m/s2','g'], value=layers.value['earthquake_intensity_unit'])
                solara.Select(label='earthquake simulation method', values=layers.value['earthquake_simulation_methods'], value=layers.value['earthquake_simulation_method_selected'])
                if layers.value['earthquake_simulation_method_selected'].value == 'monte carlo':
                    solara.InputInt(label='Number of trials',value=layers.value['earthquake_simulation_trial_count'])

        with solara.Card(title='Flood Parameters',subtitle='Choose the parameters for the flood simulations'):
            solara.Markdown(md_text='''
                            If the relative damage obtained from the vulnerability curve is beyond 
                            the flood threshold, the structure is assumed to flooded.
                            After resetting the value, please execute the simulation again to see its effect.''')
            
            solara.Text('Flood Threshold for DS2')
            solara.SliderFloat(label=None, value=threshold_flood_ds2, min=0.05,max=1, step=0.05)
            
            solara.Text('Flood Threshold for DS3')
            solara.SliderFloat(label=None, value=threshold_flood_ds3, min=0.05,max=1, step=0.05)
            
            solara.Text('Flood Threshold for DS4')
            solara.SliderFloat(label=None, value=threshold_flood_ds4, min=0.05,max=1, step=0.05)
            
            solara.Markdown(md_text='''
                            If the distance from a structure to the nearest flood intensity measure
                            is greater than Flood Distance, then the structure is assumed to be
                            intact from flood.
                            After resetting the value, please execute the simulation again to see its effect.''')
            solara.Text('Minimum Flood Distance Threshold (meters)')
            solara.SliderInt(label=None, value=threshold_flood_distance, min=0,max=100)

            solara.Markdown(md_text='''
                            If the water level is beyond this threshold then the road 
                            is assumed to be flooded.''')
            solara.Text('Minimum Water Level Threshold for Roads (meters)')
            solara.SliderFloat(label=None, value=threshold_road_water_height, min=0,max=1)
            
            solara.Markdown(md_text='''
                            If the water level is beyond this threshold then the culvert 
                            hence the road containing it is assumed to be flooded.''')
            solara.Text('Minimum Water Level Threshold for Culverts (meters)')
            solara.SliderFloat(label=None, value=threshold_culvert_water_height, min=0,max=3)

        # with solara.Card(title='Landslide Parameters',subtitle='Choose the parameters for the landslide simulation'):
        #     solara.SliderInt(label='Number of Monte-Carlo Trials', value=landslide_max_trials, min=1,max=100)

@solara.component
def MetricWidget(name, description, value, max_value, render_count, icon=None):
    value, set_value = solara.use_state_or_update(value)
    max_value, set_max_value = solara.use_state_or_update(max_value)
    options = { 
        "series": [ {
                "type": 'gauge',  
                "min": 0,
                "name": description,
                "radius": '90%', # Reduce radius slightly to accommodate lower value
                "center": ['50%', '65%'], # Move up closer to text
                "max": max(1,max_value), # workaround when max_value = 0
                "startAngle": 180,
                "endAngle": 0,
                "progress": {"show": True, "width": 8}, # Thinner line
                "pointer": { "show": False},
                "axisLine": {"lineStyle": {"width": 8, "color": [ # Thinner line
                    #[0.25, 'hotpink'],
                    #[0.5, 'red'],
                    #[0.75, 'brown'],
                    [1, '#ADADAD']
                ]}},
                "axisTick": {"show": False},
                "splitLine": {"show": False},            
                "axisLabel": {"show": False},
                "anchor": {"show": False},
                "title": {"show": False},
                "detail": {
                    "valueAnimation": True,
                    "offsetCenter": [0, '50%'], # Move value below the arc
                    "fontSize": 20,
                    "color": 'inherit'},
                #"title": {"fontSize": 12},
                "data": [{"value": value, "name": name}]}]}
    print(f'value/max_value {value}:{max_value}')

    with solara.Card(elevation=2, style={"height": "240px", "padding": "2px", "text-align": "center", "border-radius": "8px"}):
        with solara.Column(align="center", gap="0px"): # Center stack, tight gap
            if icon:
                solara.Image(icon, width="75px") 
            # Visible Label, Fixed Height for Alignment, vertically centered
            solara.Text(description, style={"font-weight": "bold", "font-size": "14px", "height": "55px", "display": "flex", "align-items": "center", "justify-content": "center", "margin-top": "4px", "line-height": "1.2"})
            solara.FigureEcharts(option=options, attributes={"style": "height:100px; width:100%; display: flex; justify-content: center; align-items: center;"}) #min-width: 80px;


def create_distribution_chart(dataframe: pd.DataFrame, column_name: str, title: str, sort_order=None):
    if dataframe is None:
        return None

    # Case-insensitive column search with common aliases
    target_col = None
    aliases = {
        'occbld': ['occbld', 'occ_bld', 'occupancy', 'occupancy_type'],
        'codelevel': ['codelevel', 'code_level', 'codelevel_type'],
        'nstoreys': ['nstoreys', 'storeys', 'number_of_storeys', 'stories', 'nstories'],
        'lrstype': ['lrstype', 'lrs_type', 'lrstype_type', 'material'],
        'nind': ['nind', 'household_size', 'size', 'members'],
        'income': ['income', 'income_level', 'income_type'],
        'gender': ['gender', 'sex'],
        'age': ['age', 'age_group'],
        'education': ['education', 'edu'],
        'employment': ['employment', 'job', 'work']
    }
    
    col_lower = column_name.lower()
    search_names = [col_lower] + aliases.get(col_lower, [])
    
    for col in dataframe.columns:
        if col.lower() in search_names:
            target_col = col
            break
            
    if target_col is None:
        return None

    column_name = target_col
    series = dataframe[column_name].dropna()
    if series.empty:
        return None

    counts = series.value_counts().reset_index()
    counts.columns = [column_name, "Count"]

    if sort_order is not None:
        counts[column_name] = pd.Categorical(counts[column_name], categories=sort_order, ordered=True)
        counts = counts.sort_values(column_name)
    else:
        try:
            counts = counts.sort_values(column_name)
        except Exception:
            counts = counts.sort_values("Count", ascending=False)

    counts["Label"] = counts[column_name].astype(str)
    counts["Percent"] = (counts["Count"] / counts["Count"].sum() * 100).round(1)

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": 700}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 40, "right": 20, "top": 55, "bottom": 80},
        "xAxis": {
            "type": "category",
            "data": counts["Label"].tolist(),
            "axisLabel": {"interval": 0, "rotate": 25, "fontSize": 11},
        },
        "yAxis": {"type": "value", "name": "Count", "nameTextStyle": {"fontSize": 11}},
        "series": [
            {
                "type": "bar",
                "data": counts["Count"].tolist(),
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0,
                        "y": 0,
                        "x2": 0,
                        "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "#235789"},
                            {"offset": 1, "color": "#7fb7df"},
                        ],
                    },
                    "borderRadius": [6, 6, 0, 0],
                },
                "label": {
                    "show": True,
                    "position": "top",
                    "formatter": [f"{value}%" for value in counts["Percent"].tolist()],
                    "fontSize": 11,
                },
            }
        ],
        "backgroundColor": "transparent",
    }


@solara.component
def ChartCard(option):
    with solara.Card(
        elevation=1,
        style={
            "padding": "8px",
            "borderRadius": "14px",
            "border": "1px solid rgba(31, 42, 51, 0.08)",
            "background": "#fcfdff",
        },
    ):
        solara.FigureEcharts(option=option, attributes={"style": "height:340px; width:100%;"})


@solara.component
def GeneratedDataTablesCharts(layers=layers):
    buildings = layers.value["layers"]["building"]["data"].value
    households = layers.value["layers"]["household"]["data"].value
    individuals = layers.value["layers"]["individual"]["data"].value

    if buildings is None:
        solara.Info("There is no generated exposure data yet.")
        return

    building_df = pd.DataFrame(buildings.drop(columns="geometry", errors="ignore")) if isinstance(buildings, gpd.GeoDataFrame) else pd.DataFrame(buildings)
    household_df = pd.DataFrame(households) if households is not None else None
    individual_df = pd.DataFrame(individuals) if individuals is not None else None

    with solara.lab.Tabs():
        with solara.lab.Tab("Statistics"):
            with solara.Row(gap="16px", style={"flexWrap": "wrap"}):
                with solara.Card(title="Buildings", elevation=1, style={"minWidth": "180px"}):
                    solara.Text(f"{len(building_df):,}", style={"font-size": "1.6rem", "font-weight": "800"})
                with solara.Card(title="Households", elevation=1, style={"minWidth": "180px"}):
                    solara.Text(f"{0 if household_df is None else len(household_df):,}", style={"font-size": "1.6rem", "font-weight": "800"})
                with solara.Card(title="Individuals", elevation=1, style={"minWidth": "180px"}):
                    solara.Text(f"{0 if individual_df is None else len(individual_df):,}", style={"font-size": "1.6rem", "font-weight": "800"})

        with solara.lab.Tab("Building Data"):
            solara.Markdown("Generated building attributes.")
            solara.DataFrame(building_df, items_per_page=10)

        with solara.lab.Tab("Building Charts"):
            solara.Markdown("Distribution views for the generated building stock.")
            with solara.GridFixed(columns=2):
                for option in [
                    create_distribution_chart(building_df, "lrstype", "LRS Distribution"),
                    create_distribution_chart(building_df, "occbld", "Occupancy Distribution"),
                    create_distribution_chart(building_df, "codelevel", "Code Level Distribution"),
                    create_distribution_chart(building_df, "nstoreys", "Storey Distribution"),
                ]:
                    if option is not None:
                        ChartCard(option)

        if household_df is not None:
            with solara.lab.Tab("Household Data"):
                solara.Markdown("Generated household attributes.")
                solara.DataFrame(household_df, items_per_page=10)

            with solara.lab.Tab("Household Charts"):
                solara.Markdown("Distribution views for household composition.")
                with solara.GridFixed(columns=2):
                    for option in [
                        create_distribution_chart(household_df, "nind", "Household Size Distribution"),
                        create_distribution_chart(household_df, "income", "Income Level Distribution", sort_order=["veryLowIncome", "lowIncome", "midIncome", "highIncome"]),
                    ]:
                        if option is not None:
                            ChartCard(option)

        if individual_df is not None:
            with solara.lab.Tab("Individual Data"):
                solara.Markdown("Generated individual attributes.")
                solara.DataFrame(individual_df, items_per_page=10)

            with solara.lab.Tab("Individual Charts"):
                solara.Markdown("Distribution views for individual demographics.")
                with solara.GridFixed(columns=2):
                    for option in [
                        create_distribution_chart(individual_df, "gender", "Gender Distribution"),
                        create_distribution_chart(individual_df, "eduattstat", "Education Status Distribution"),
                        create_distribution_chart(individual_df, "age", "Age Distribution"),
                    ]:
                        if option is not None:
                            ChartCard(option)


def import_data(fileinfo: solara.components.file_drop.FileInfo):
    data_array = fileinfo['data']
    extension = fileinfo['name'].split('.')[-1]
    if extension == 'xlsx':
        import io
        data = pd.read_excel(io.BytesIO(data_array))
    elif extension in ['tiff','tif']:
        data = read_tiff(data_array)
    elif extension.lower() in ['xml']:
        data = read_gem_xml(data_array)
    else:
        json_string = data_array.decode('utf-8')
        json_data = json.loads(json_string)
        if "features" in json_data.keys():
            data = gpd.GeoDataFrame.from_features(json_data['features'])
        else:
            import io
            data = pd.read_json(io.StringIO(json_string))

    if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
        # reset existing index to avoid conflicts in index-related computations
        data = data.reset_index(drop=True)
        data.columns = data.columns.str.lower()
        attributes = set(data.columns)
    elif isinstance(data, dict):
        attributes = set(data.keys())
    else:
        return (None, None)

    # in the first pass, look for exact column match
    name = None
    for layer_name, layer in layers.value['layers'].items():
        if attributes in layer['attributes']:
            name = layer_name
            break
    # if not, check only the required columns
    # select the one with maximum match
    if name is None:
        size_of_best_match = 0
        for layer_name, layer in layers.value['layers'].items():
            for layer_attributes in layer['attributes_required']:
                if layer_attributes.issubset(attributes):
                    if len(layer_attributes) > size_of_best_match:
                        name = layer_name
                        size_of_best_match = len(layer_attributes)
                        logging.debug('There are extra columns', attributes - layer_attributes)

    # Internal checking
    if name in ["road edges", "power edges"]:
        if "edge_id" in data.columns:
            if len(pd.unique(data['edge_id'])) != len(data):
                # workaround: TODO remove later and raise Exception
                data['edge_id'] = range(len(data))
                #raise Exception(f'edge_id column is not unique')
                          
    # Preprocess
    data = layers.value['layers'][name]['pre_processing'](data, layers.value['layers'][name]['extra_cols'])

    if name == "parameter":
        data = ParameterFile(content=data_array)
        
    return (name, data)


def update_map_center_from_gdf(data: gpd.GeoDataFrame):
    if data is None or data.empty or "geometry" not in data.columns:
        return
    data_wgs84 = data if data.crs == "EPSG:4326" else data.to_crs("EPSG:4326")
    centroids = data_wgs84.to_crs("EPSG:3857").centroid.to_crs("EPSG:4326")
    layers.value["center"].set((centroids.y.mean(), centroids.x.mean()))


def set_layer_data(layer_name: str, data, update_center: bool = False):
    if isinstance(data, gpd.GeoDataFrame):
        gdf = data.reset_index(drop=True)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        layers.value["layers"][layer_name]["data"].set(gdf)
        layers.value["layers"][layer_name]["df"].set(gdf.drop(columns=["geometry"], errors="ignore"))
        if update_center:
            update_map_center_from_gdf(gdf)
    elif isinstance(data, pd.DataFrame):
        df = data.reset_index(drop=True)
        layers.value["layers"][layer_name]["data"].set(df)
        layers.value["layers"][layer_name]["df"].set(df)
    else:
        layers.value["layers"][layer_name]["data"].set(data)


def clear_layer_data(layer_name: str):
    layers.value["layers"][layer_name]["data"].set(None)
    layers.value["layers"][layer_name]["df"].set(None)

@solara.component
def FilterPanel():
    cross_filter_store = solara.use_context(cross_filter_context)
    #print(f'{layers.value["bounds"].value}')
    # nonempty_layers = {name: layer for name, layer in layers.value['layers'].items() if layer['data'].value is not None}
    #with solara.lab.Tabs(background_color="#ebebeb"):
    # for layer_name, layer in nonempty_layers.items():
        #with solara.lab.Tab(layer_name):
        # data = layer['data'].value
        # if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
            # df = layer['df'].value
            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Damage State Filter</h4>''')
                # for filter_col in ['ds']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Income Level Filter</h4>''')
                # for filter_col in ['freqincome']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Load Resisting System Filter</h4>''')
                # for filter_col in ['lrstype']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")        

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Code Level Filter</h4>''')
                # for filter_col in ['codelevel']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Height Filter</h4>''')
                # for filter_col in ['nstoreys']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Occupation Type Filter</h4>''')
                # for filter_col in ['occbld']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Special Facility Filter</h4>''')
                # for filter_col in ['specialfac']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")

            # if layer_name in ['building']:
                # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Polygon (ZoneID) Filter</h4>''')
                # for filter_col in ['zoneid']:
                    # solara.CrossFilterSelect(df, filter_col, multiple=True)
                # filters[layer_name], _ = solara.use_cross_filter(id(df), "dataframe")
    building_filter_view, set_building_filter_view = solara.use_state(None)
    landuse_filter_view, set_landuse_filter_view = solara.use_state(None)
    tally_minimal_filter_view, set_tally_minimal_filter_view = solara.use_state(None)

    def create_building_filter_view():
        data = layers.value['layers']['building']['df'].value
        df = convert_data_for_filter_view(data, 'building')
        set_building_filter_view(df)

    def create_landuse_filter_view():
        data = layers.value['layers']['landuse']['df'].value
        df = convert_data_for_filter_view(data, 'landuse')
        set_landuse_filter_view(df)

    def create_tally_minimal_filter_view():
        print('create_tally_minimal_filter_view triggered')
        data = read_from_session_storage('tally_minimal')
        df = convert_data_for_filter_view(data, 'tally_minimal')
        print(df)
        set_tally_minimal_filter_view(df)

    with solara.Column(classes=["map-filter-panel"], gap="8px"):
        solara.Markdown("#### Filters")

        solara.use_memo(create_landuse_filter_view, [layers.value['layers']['landuse']['df'].value])
        landuse_filter.value, set_landuse_cross_filter = solara.use_cross_filter(id(landuse_filter_view), "landuse_filter")
        solara.use_memo(create_building_filter_view, [layers.value['layers']['building']['df'].value])
        building_filter.value, set_building_cross_filter = solara.use_cross_filter(id(building_filter_view), "building_filter")
        solara.use_memo(create_tally_minimal_filter_view, [tally_counter.value])
        tally_filter.value, set_tally_cross_filter = solara.use_cross_filter(id(tally_minimal_filter_view), "tally_filter")
        if landuse_filter_view is None and building_filter_view is None and tally_minimal_filter_view is None:
            solara.Text("Filters become available when analysis results are ready.")

        if landuse_filter_view is not None:
            btn = solara.Button("LANDUSE FILTERS", classes=["filter-section-button"], style={"width":"100%"})
            with solara.Column(align="stretch"):
                with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"320px"}):
                    with solara.Div(classes=["filter-menu-body"]):
                        solara.Markdown("**Land Use Filters**")
                        solara.CrossFilterReport(landuse_filter_view)
                        for col, colinfo in lbl_2_str['landuse'].items():
                            if colinfo['name'] in landuse_filter_view.columns:
                                solara.CrossFilterSelect(landuse_filter_view, colinfo['name'], multiple=True, max_unique=5000)

        if building_filter_view is not None:
            btn = solara.Button("BUILDING FILTERS", classes=["filter-section-button"], style={"width":"100%"})
            with solara.Column(align="stretch"):
                with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"320px"}):
                    with solara.Div(classes=["filter-menu-body"]):
                        solara.Markdown("**Building Filters**")
                        solara.CrossFilterReport(building_filter_view)
                        for col, colinfo in lbl_2_str['building'].items():
                            if colinfo['name'] in building_filter_view.columns:
                                solara.CrossFilterSelect(building_filter_view, colinfo['name'], multiple=True, max_unique=5000)

        if tally_minimal_filter_view is not None:
            btn = solara.Button("METRIC FILTERS", classes=["filter-section-button"], style={"width":"100%"})
            with solara.Column(align="stretch"):
                with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"320px"}):
                    with solara.Div(classes=["filter-menu-body"]):
                        solara.Markdown("**Metric Filters**")
                        solara.CrossFilterReport(tally_minimal_filter_view)
                        for col, colinfo in lbl_2_str['tally_minimal'].items():
                            if colinfo['name'] in tally_minimal_filter_view.columns:
                                solara.CrossFilterSelect(tally_minimal_filter_view, colinfo['name'], multiple=True, max_unique=5000)
        def reset_filters():
            for data_key in [id(landuse_filter_view), id(building_filter_view), id(tally_minimal_filter_view)]:
                if data_key in cross_filter_store.filters:
                    for key in list(cross_filter_store.filters[data_key].keys()):
                        cross_filter_store.filters[data_key][key] = None
            for listener in list(cross_filter_store.listeners):
                listener()
        solara.Button("Reset Filters", on_click=reset_filters, text=True, outlined=True, style={"width": "100%"})

@solara.component
def LayerDisplayer():
    print(f'{layers.value["bounds"].value}')
    nonempty_layers = {name: layer for name, layer in layers.value['layers'].items() if layer['data'].value is not None}
    nonempty_layer_names = list(nonempty_layers.keys())
    
    if len(nonempty_layer_names) == 0:
        solara.Info("There is no layer details data yet!")
        return

    selected = layers.value['selected_layer'].value
    def set_selected(s):
        layers.value['selected_layer'].set(s)

    solara.ToggleButtonsSingle(value=selected, on_value=set_selected,
                               values=nonempty_layer_names)
    if selected is None and len(nonempty_layer_names) > 0:
        set_selected(nonempty_layer_names[0])
    if selected is not None:
        data = nonempty_layers[selected]['data'].value
        if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
            if "geometry" in data.columns:
                ((ymin,xmin),(ymax,xmax)) = layers.value['bounds'].value
                df_filtered = data.cx[xmin:xmax,ymin:ymax].drop(columns='geometry')
                if df_filtered.empty:
                    df_filtered = data.drop(columns='geometry')
                solara.DataFrame(df_filtered, items_per_page=5)
            else:
                if selected == "power fragility":
                    PowerFragilityDisplayer(data, items_per_page=5)
                else:
                    solara.DataFrame(data, items_per_page=5)
            if selected in ["landuse","building","road edges","road nodes","power nodes","power edges","intensity"] :
                with solara.Row():
                    file_object = data.to_json()
                    with solara.FileDownload(file_object, f"{selected}_export.geojson", mime_type="application/geo+json"):
                        solara.Button("Download GeoJSON", icon_name="mdi-cloud-download-outline", color="primary")
                    with solara.FileDownload(data.to_csv(), f"{selected}_export.csv", mime_type="text/csv"):
                        solara.Button("Download CSV", icon_name="mdi-cloud-download-outline", color="primary")
                solara.Text("Spacer", style={"visibility": "hidden"})
            elif selected in ['household', 'individual', 'fragility', 'landslide fragility', 'vulnerability', 'power fragility', 'road fragility']:
                 with solara.Row():
                    file_object = data.to_json()
                    with solara.FileDownload(file_object, f"{selected}_export.json", mime_type="application/json"):
                        solara.Button("Download JSON", icon_name="mdi-cloud-download-outline", color="primary")
                    with solara.FileDownload(data.to_csv(), f"{selected}_export.csv", mime_type="text/csv"):
                        solara.Button("Download CSV", icon_name="mdi-cloud-download-outline", color="primary")
                 solara.Text("Spacer", style={"visibility": "hidden"})
        elif isinstance(data, ParameterFile):
            ParameterFileWidget(parameter_file=data)                        
        if selected == 'gem_vulnerability':
            def default(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return str(obj)
            with solara.Row():
                file_object = json.dumps(data, default=default)
                with solara.FileDownload(file_object, f"{selected}_export.json", mime_type="application/json"):
                    solara.Button("Download JSON", icon_name="mdi-cloud-download-outline", color="primary")
            solara.Text("Spacer", style={"visibility": "hidden"})
            VulnerabiliyDisplayer(data)
        elif selected == 'gem_fragility':
            def default(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return str(obj)
            with solara.Row():
                file_object = json.dumps(data, default=default)
                with solara.FileDownload(file_object, f"{selected}_export.json", mime_type="application/json"):
                    solara.Button("Download JSON", icon_name="mdi-cloud-download-outline", color="primary")
            solara.Text("Spacer", style={"visibility": "hidden"})
            FragilityDisplayer(data)

metric_update_pending = solara.reactive(False)

@task
def generate_metrics_local():
    metric_update_pending.set(True)
    print("Emtering generate_metrics_local")
    metrics = {name: {'value':0, 'max_value':0, 'desc': metric['desc']} for name, metric in layers.value['metrics'].items()}

    tally_geo = read_from_session_storage('tally_geo')
    hazard = read_from_session_storage('hazard')
    population_displacement_consensus = read_from_session_storage('population_displacement_consensus')
    print('is tally_geo none', tally_geo is None)
    print('is hazard none', hazard is None)
    print('is population_displacement_consensus none', population_displacement_consensus is None)
    if tally_geo is not None and layers.value['bounds'].value is not None:
        ((ymin,xmin),(ymax,xmax)) = layers.value['bounds'].value
        tally_filtered = tally_geo.cx[xmin:xmax,ymin:ymax]
        if tally_filter.value is not None:
            tally_filtered = tally_filtered[tally_filter.value]
        print('Triggering generate_metrics')
        metrics = generate_metrics(tally_filtered, tally_geo, hazard, population_displacement_consensus)
        
        is_unfiltered = (len(tally_filtered) == len(tally_geo))
        if is_unfiltered:
            realized = layers.value['metrics_realized'].value
            if realized is not None and len(realized) > 1:
                for metric_key in metrics.keys():
                    avg_val = sum(trial[metric_key]['value'] for trial in realized) / len(realized)
                    avg_max = sum(trial[metric_key]['max_value'] for trial in realized) / len(realized)
                    metrics[metric_key]['value'] = int(round(avg_val))
                    metrics[metric_key]['max_value'] = int(round(avg_max))
        
        print('metrics', metrics)
    metric_update_pending.set(False)
    return metrics

@solara.component
def MetricPanel():
    filtered_metrics = {name: {'value':0, 'max_value':0, 'desc': metric['desc']} for name, metric in layers.value['metrics'].items()}
    solara.use_memo(generate_metrics_local, 
                    [tally_counter.value,
                     layers.value['bounds'].value,
                     tally_filter.value,
                     layers.value['render_count'].value], debug_name="generate_metrics_loca")
    if generate_metrics_local.finished:
        filtered_metrics = generate_metrics_local.value


    metric_icons = [metric_icon1,metric_icon2,metric_icon3,metric_icon4,metric_icon5,metric_icon6,metric_icon7,metric_icon8]
    with solara.Row(justify="center", style="align-items: center; margin-top: -25px; margin-bottom: -25px"):
        solara.Markdown('''<h2 style="font-weight: bold; margin: 0px; line-height: 1.1">IMPACTS</h2>''')
        with solara.Link("/docs/metrics"):
             with solara.Tooltip('Click for impact metric definitions'):
                solara.Button(icon_name="mdi-help-box", text=True, outlined=False, style={"margin": "0 0 -12px -32px", "padding": "0px"})
    if metric_update_pending.value:
        solara.ProgressLinear(metric_update_pending.value)
    
    with solara.v.Row(justify="space-around", style_="margin-top: 0px; padding-top: 0px;"):
        for (name, metric), icon in zip(filtered_metrics.items(), metric_icons):
            # Responsive grid: 
            # cols=6 (Mobile 2/row), sm=4 (Tablet 3/row), md=3 (Small Desktop 4/row)
            # class_="col-lg-custom-8" (Large Desktop 8/row via custom CSS)
            with solara.v.Col(cols=6, sm=4, md=3, class_="col-lg-custom-8", style_="padding: 5px;"):
                MetricWidget(name, metric['desc'], 
                            metric['value'], 
                            metric['max_value'],
                            layers.value['render_count'].value,
                            icon=icon)      

@solara.component
def MetricStatistics():
    if layers.value['metrics_realized'].value is None:
        solara.Info('There is no metrics statistics data yet!')
        return

    # list of metrics measurements
    metrics = layers.value['metrics_realized'].value
    
    # get the metric names from the first measurement
    metric_names = metrics[0].keys()
    metric_labels = {
        metric_name: metrics[0][metric_name].get('desc', metric_name)
        for metric_name in metric_names
    }

    def render_metric_table(table_df, first_column_left=False):
        headers = [escape(str(col)) for col in table_df.columns]
        rows = []
        for row in table_df.itertuples(index=False):
            cells = []
            for idx, value in enumerate(row):
                align = "left" if first_column_left and idx == 0 else "center"
                display_value = "" if pd.isna(value) else str(value)
                cells.append(
                    f'<td style="text-align:{align};">{escape(display_value)}</td>'
                )
            rows.append(f"<tr>{''.join(cells)}</tr>")
        header_html = "".join(f"<th>{header}</th>" for header in headers)
        table_classes = "metric-stats-table"
        if first_column_left:
            table_classes += " first-column-left"
        table_html = f"""
            <div class="{table_classes}">
                <table>
                    <thead>
                        <tr>{header_html}</tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        """
        solara.Markdown(table_html, unsafe_solara_execute=True)

    metric_dict = {}
    for metric_name in metric_names:
        metric_values = [m[metric_name]['value'] for m in metrics]
        metric_dict[metric_name] = metric_values
    df = pd.DataFrame.from_dict(metric_dict).rename(columns=metric_labels)
    summary = df.describe()
    if 'std' in summary.index:
        summary.loc['std'] = summary.loc['std'].fillna(0)

    chart_categories = []
    chart_values = []
    for metric_name in metric_names:
        metric_label = metric_labels[metric_name]
        chart_categories.append("\n".join(textwrap.wrap(metric_label, width=18)))
        total_value = sum(float(m[metric_name].get('value', 0)) for m in metrics) / max(len(metrics), 1)
        chart_values.append(total_value)

    options = { 
        "backgroundColor": "transparent",
        "toolbox": {
            "feature": {
                "saveAsImage": {
                    "title": "Save as PNG",
                    "pixelRatio": 2
                }
            }
        },
        "title": [{
            "text": 'Total Impact Metrics',
            "left": 'center',
            "textStyle": {
                "fontSize": 16,
                "fontWeight": 700,
                "color": "#1f2933"
            }
        }],
        "legend": {
            "top": 32,
            "left": "center",
            "textStyle": {
                "fontSize": 11,
                "color": "#3e4c59"
            }
        },
        "tooltip": {
            "trigger": 'axis',
            "axisPointer": {
                "type": 'shadow'
            }
        },
        "grid": {
            "top": 90,
            "left": 60,
            "right": 24,
            "bottom": 110,
            "containLabel": True
        },
        "xAxis": {
            "type": 'category',
            "data": chart_categories,
            "axisLabel": {
                "interval": 0,
                "fontSize": 10,
                "lineHeight": 12,
                "color": "#3e4c59",
                "margin": 14
            },
            "axisLine": {
                "lineStyle": {
                    "color": "#9fb3c8"
                }
            },
            "axisTick": {
                "alignWithLabel": True
            }
        },
        "yAxis": {
            "type": 'value',
            "name": "Value",
            "nameLocation": "middle",
            "nameGap": 45,
            "nameTextStyle": {
                "fontSize": 11,
                "fontWeight": 600,
                "color": "#3e4c59"
            },
            "axisLabel": {
                "fontSize": 10,
                "color": "#52606d"
            },
            "axisLine": {
                "show": False
            },
            "axisTick": {
                "show": False
            },
            "splitArea": {
                "show": False
            },
            "splitLine": {
                "lineStyle": {
                    "color": "rgba(15, 23, 42, 0.08)"
                }
            }
        },
        "series": [
            {
                "name": "Total Value",
                "type": "bar",
                "data": chart_values,
                "barMaxWidth": 34,
                "itemStyle": {"color": "#3b82f6", "borderRadius": [6, 6, 0, 0]},
                "label": {
                    "show": True,
                    "position": "top",
                    "color": "#1f2933",
                    "fontSize": 10,
                    "formatter": "{c}"
                }
            }
        ]
    }
    solara.Style('''
        .metric-stats-table {
            width: 100%;
            overflow-x: auto;
        }
        .metric-stats-table table {
            width: 100% !important;
            max-width: 100% !important;
            table-layout: fixed !important;
            border-collapse: collapse;
        }
        .metric-stats-table th,
        .metric-stats-table td {
            border: 1px solid rgba(0, 0, 0, 0.12);
            padding: 6px 8px;
            font-size: 11px;
            line-height: 1.25;
            white-space: normal !important;
            word-break: break-word !important;
            overflow-wrap: anywhere !important;
            vertical-align: middle;
            text-align: center;
        }
        .metric-stats-table th {
            font-weight: bold;
            text-align: center !important;
            vertical-align: middle;
        }
        .metric-stats-table th:first-child {
            text-align: center !important;
        }
        .metric-stats-table.first-column-left th:first-child,
        .metric-stats-table.first-column-left td:first-child {
            width: 160px !important;
            min-width: 160px !important;
        }
        .metric-stats-table.first-column-left td:first-child {
            text-align: left !important;
        }
    ''')
    with solara.lab.Tabs():
        with solara.lab.Tab("Boxplot"):
            with solara.GridFixed(columns=1):
                solara.FigureEcharts(option=options, attributes={"style": "height:520px; width:100%"})
        with solara.lab.Tab("Data"): 
            with solara.Row(justify="end", style={"margin-bottom": "8px", "padding-right": "8px", "margin-top": "8px"}):
                solara.FileDownload(data=lambda: df.to_csv(index=False), filename="Metric_Data.csv", label="Export CSV")
            render_metric_table(df)
        with solara.lab.Tab("Stats"): 
            stats_df = summary.reset_index().rename(columns={'index': 'Statistic'})
            with solara.Row(justify="end", style={"margin-bottom": "8px", "padding-right": "8px", "margin-top": "8px"}):
                solara.FileDownload(data=lambda: stats_df.to_csv(index=False), filename="Metric_Stats.csv", label="Export CSV")
            render_metric_table(stats_df, first_column_left=True)
        with solara.lab.Tab("DS Breakdown"):
            ds_avg_dict = {m_name: {ds: 0.0 for ds in [0, 1, 2, 3, 4]} for m_name in metric_names}
            for m in metrics:
                for m_name in metric_names:
                    if 'ds_breakdown' in m[m_name]:
                        for ds, count in m[m_name]['ds_breakdown'].items():
                            ds_avg_dict[m_name][ds] += count / len(metrics)
                            
            ds_labels = {
                0: 'DS0 (No Damage)',
                1: 'DS1 (Slight)',
                2: 'DS2 (Moderate)',
                3: 'DS3 (Extensive)',
                4: 'DS4 (Complete)'
            }
            ds_records = []
            for ds in [0, 1, 2, 3, 4]:
                record = {'Damage State': ds_labels[ds]}
                for m_name in metric_names:
                    desc = metric_labels[m_name]
                    if 'ds_breakdown' in metrics[0][m_name]:
                        record[desc] = int(round(ds_avg_dict[m_name][ds]))
                    else:
                        record[desc] = 'N/A'
                ds_records.append(record)
            
            ds_df = pd.DataFrame(ds_records)
            with solara.Row(justify="end", style={"margin-bottom": "8px", "padding-right": "8px", "margin-top": "8px"}):
                solara.FileDownload(data=lambda: ds_df.to_csv(index=False), filename="Metric_DS_Breakdown.csv", label="Export CSV")
            render_metric_table(ds_df, first_column_left=True)

@solara.component
def MapViewer():
    print('rendering mapviewer')
    default_zoom = 14
    zoom, set_zoom = solara.use_state(default_zoom)
    filters_open, set_filters_open = solara.use_state(False)

    def zoom_to_landuse():
        l = layers.value['layers']['landuse']['data'].value
        if l is not None:
            import math
            bounds = l.total_bounds
            minx, miny, maxx, maxy = bounds
            center_x = (minx + maxx) / 2
            center_y = (miny + maxy) / 2
            layers.value['center'].set((center_y, center_x))
            max_diff = max(maxx - minx, maxy - miny)
            if max_diff > 0:
                calculated_zoom = int(math.floor(math.log2(360 / max_diff)))
                calculated_zoom = max(1, min(calculated_zoom, 18))
                set_zoom(calculated_zoom)
    def create_base_layers():
        base_layer1 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.OpenStreetMap.Mapnik.build_url(),name="OpenStreetMap",base = True)
        base_layer2 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.OpenTopoMap.build_url(),name="OpenTopoMap",base = True)
        base_layer3 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.Esri.WorldStreetMap.build_url(),name="Esri WorldStreetMap",base = True)
        base_layer4 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.Esri.WorldImagery.build_url(),name="Esri WorldImagery",base = True)        
        base_layer5 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.CartoDB.Positron.build_url(),name="CartoDB",base = True) 
        base_layer6 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.CartoDB.DarkMatter.build_url(),name="CartoDB Dark",base = True)                                                                                                                                        
        return [base_layer2, base_layer3, base_layer4, base_layer5, base_layer6, base_layer1]

    # create base layers only once
    base_layers = solara.use_memo(create_base_layers,[])
    
    layout = ipywidgets.Layout.element(width='100%', height='55vh')

    tool1 = ipyleaflet.ZoomControl.element(position='topleft')
    tool2 = ipyleaflet.FullScreenControl.element(position='topleft')    
    tool3 = ipyleaflet.LayersControl.element(position='topright', collapsed=False)
    tool4 = ipyleaflet.ScaleControl.element(position='bottomleft')                                                                                                                                              

    def cleanup_cache():
        # Clear the map layer cache when the MapViewer is unmounted. 
        # Solara automatically closes the ipyleaflet widgets on unmount, 
        # so if we revisit this page, we don't want to reuse dead widgets.
        return lambda: layers.value.setdefault('_map_layer_cache', {}).clear()
    
    solara.use_effect(cleanup_cache, [])

    def create_layers():
        map_layers = []
        sorted_layers = sorted(
            layers.value['layers'].items(),
            key=lambda item: item[1].get('render_order', 0)
        )
        for l, layer_config in sorted_layers:
            df = layer_config['data'].value
            if df is not None and isinstance(df, gpd.GeoDataFrame):
                df_filtered = df
                if l == 'building':
                    if building_filter.value is not None:
                        df_filtered = df[building_filter.value]
                if l == 'landuse':
                    if landuse_filter.value is not None:
                        df_filtered = df[landuse_filter.value]

                # Use a robust cache key rather than id(df_filtered) to avoid id() collisions when ephemeral filtered dataframes are garbage collected
                cache_key_parts = [l, layers.value['render_count'].value]

                if l == 'building' and building_filter.value is not None:
                    cache_key_parts.append(hash(tuple(building_filter.value)))
                elif l == 'landuse' and landuse_filter.value is not None:
                    cache_key_parts.append(hash(tuple(landuse_filter.value)))

                cache_key = tuple(cache_key_parts)
                if cache_key not in layers.value.setdefault('_map_layer_cache', {}):
                    print(f"Creating new layer for {l}, df_filtered size: {len(df_filtered)}")
                    layers.value['_map_layer_cache'][cache_key] = create_map_layer(df_filtered, l)
                
                map_layer = layers.value['_map_layer_cache'][cache_key]
                map_layers.append(map_layer)

        return map_layers

    map_layers = solara.use_memo(create_layers,
                    [building_filter.value, landuse_filter.value] + 
                    [layers.value['render_count'].value])  

    def create_legend_control():
        df_lu = layers.value['layers']['landuse']['data'].value
        df_b = layers.value['layers']['building']['data'].value
        
        has_lu = df_lu is not None and isinstance(df_lu, gpd.GeoDataFrame) and 'luf' in df_lu.columns
        has_b = df_b is not None and isinstance(df_b, gpd.GeoDataFrame) and 'ds' in df_b.columns
        
        if not has_lu and not has_b:
            return None
            
        import uuid
        uid = str(uuid.uuid4())[:8]

        html_lu = ""
        if has_lu:
            unique_lufs = set(df_lu['luf'].dropna().unique())
            for luf in sorted(list(unique_lufs)):
                color = landuse_colors({'properties': {'luf': luf}})['fillColor']
                html_lu += f"<div style='display: flex; align-items: center; margin-bottom: 3px;'><div style='width: 15px; height: 15px; flex-shrink: 0; background-color: {color}; border: 1px solid black; margin-right: 5px;'></div><span style='font-size: 12px; line-height: 1.2;'>{luf}</span></div>"
        else:
            html_lu = "<span style='font-size: 12px;'>No land use data</span>"

        html_ds = ""
        ds_labels = {0: "DS0 (No Damage)", 1: "DS1 (Slight)", 2: "DS2 (Moderate)", 3: "DS3 (Extensive)", 4: "DS4 (Complete)"}
        for ds in [0, 1, 2, 3, 4]:
            color = ds_to_color[ds]
            label = ds_labels[ds]
            html_ds += f"<div style='display: flex; align-items: center; margin-bottom: 3px;'><div style='width: 15px; height: 15px; flex-shrink: 0; background-color: {color}; border: 1px solid black; margin-right: 5px;'></div><span style='font-size: 12px; line-height: 1.2;'>{label}</span></div>"

        html_content = f"""
        <style>
        .tabs-{uid} {{ display: flex; margin-bottom: 5px; }}
        .tab-label-{uid} {{ flex: 1; padding: 4px 2px; text-align: center; cursor: pointer; border: 1px solid #ccc; background: #eee; font-size: 11px; font-weight: bold; border-radius: 3px 3px 0 0; margin-right: 2px; }}
        .tab-radio-{uid} {{ display: none; }}
        .tab-content-{uid} {{ display: none; padding-top: 5px; }}
        #tab1-{uid}:checked ~ .tabs-{uid} .label1-{uid} {{ background: white; border-bottom: 2px solid white; margin-bottom: -1px; }}
        #tab2-{uid}:checked ~ .tabs-{uid} .label2-{uid} {{ background: white; border-bottom: 2px solid white; margin-bottom: -1px; }}
        #tab1-{uid}:checked ~ #content1-{uid} {{ display: block; }}
        #tab2-{uid}:checked ~ #content2-{uid} {{ display: block; }}
        </style>
        <details open style='background: white; padding: 8px; border-radius: 5px; box-shadow: 0 1px 5px rgba(0,0,0,0.4); max-height: 300px; overflow-y: auto; width: 170px;'>
            <summary style='cursor: pointer; font-weight: bold; margin-bottom: 8px; font-size: 13px;'>Map Legend</summary>
            <input type="radio" name="legend-tab-{uid}" id="tab1-{uid}" class="tab-radio-{uid}" checked>
            <input type="radio" name="legend-tab-{uid}" id="tab2-{uid}" class="tab-radio-{uid}">
            <div class="tabs-{uid}">
                <label for="tab1-{uid}" class="tab-label-{uid} label1-{uid}">Land Use</label>
                <label for="tab2-{uid}" class="tab-label-{uid} label2-{uid}">Damage</label>
            </div>
            <div id="content1-{uid}" class="tab-content-{uid}">
                {html_lu}
            </div>
            <div id="content2-{uid}" class="tab-content-{uid}">
                {html_ds}
            </div>
        </details>
        """
        
        legend_widget = ipywidgets.HTML(value=html_content)
        return ipyleaflet.WidgetControl.element(widget=legend_widget, position='bottomright')

    legend_control = solara.use_memo(create_legend_control, [
        layers.value['layers']['landuse']['data'].value,
        layers.value['layers']['building']['data'].value
    ])
    controls = [tool1, tool2, tool3, tool4]
    if legend_control is not None:
        controls.append(legend_control)

    with solara.Div(classes=["map-shell"]):
        ipyleaflet.Map.element(
            zoom=zoom,
            max_zoom=23,                    
            on_zoom=set_zoom,
            on_bounds=layers.value['bounds'].set,
            center=layers.value['center'].value,
            on_center=layers.value['center'].set,
            scroll_wheel_zoom=True,
            dragging=True,
            double_click_zoom=True,
            touch_zoom=True,
            box_zoom=True,
            keyboard=True if random.random() > 0.5 else False,
            layers=base_layers + map_layers,
            controls = controls,
            layout = layout
            )
        with solara.Div(classes=["map-filter-overlay"]):
            with solara.Div(style={"display": "flex", "flex-direction": "column", "gap": "8px", "align-items": "flex-start"}):
                with solara.Tooltip("Zoom to Land-use Layer"):
                    solara.Button(
                        icon_name="mdi-crosshairs-gps",
                        icon=True,
                        on_click=zoom_to_landuse,
                        outlined=True,
                        classes=["map-filter-toggle"],
                        style={"width": "32px", "min-width": "32px", "height": "32px", "padding": "0"},
                        disabled=layers.value['layers']['landuse']['data'].value is None
                    )
                with solara.Tooltip("Show filters"):
                    solara.Button(
                        icon_name="mdi-filter-variant",
                        icon=True,
                        on_click=lambda: set_filters_open(not filters_open),
                        outlined=True,
                        classes=["map-filter-toggle"],
                        style={"width": "32px", "min-width": "32px", "height": "32px", "padding": "0"},
                    )
                if filters_open:
                    with solara.Card(elevation=2, style={"padding": "0", "border-radius": "12px", "background": "rgba(255,255,255,0.98)", "min-width": "260px", "margin-top": "2px", "border": "1px solid rgba(0,0,0,0.08)", "box-shadow": "0 10px 26px rgba(0,0,0,0.16)"}):
                        with solara.Div(classes=["map-filter-content"]):
                            FilterPanel()
        
@solara.component
def ExecutePanel(): 

    progress_message, set_progress_message = solara.use_state("")
    execute_counter, set_execute_counter = solara.use_state(0)
    execute_btn_disabled, set_execute_btn_disabled = solara.use_state(False)
    execute_error = solara.reactive("")

    def on_click():
        set_execute_counter(execute_counter + 1)
        execute_error.set("")
        save_status.set("")

    def on_reset():
        reset_session()


    def is_ready_to_run(infra, hazard):
        existing_layers = set([name for name, l in layers.value['layers'].items() if l['data'].value is not None])
        missing = []

        if hazard == "earthquake":
            if "power" in  infra:
                missing += list(set(["building","household","individual","power edges","power nodes","intensity","power fragility"]) - existing_layers)
            if "road" in  infra:
                missing += list(set(["building","household","individual","road edges","road nodes","intensity","road fragility"]) - existing_layers)
            if "building" in infra:
                missing += list(set(["landuse","building","household","individual","intensity"]) - existing_layers)
                if not "fragility" in existing_layers and not "gem_fragility" in existing_layers:
                    missing += ["fragility or gem_fragility"]
        elif hazard == "flood":
            if "power" in  infra:
                missing += list(set(["landuse","building","household","individual","power edges","power nodes","intensity","vulnerability"]) - existing_layers)
            if "road" in  infra:
                missing += list(set(["landuse","building","household","individual","road edges","road nodes","intensity"]) - existing_layers)
            if "building" in infra:
                missing += list(set(["landuse","building","household","individual","intensity","vulnerability"]) - existing_layers)
        elif hazard == "landslide":
            if "power" in  infra:
                missing += list(set(["landuse","building","household","individual","power edges","power nodes","landslide fragility"]) - existing_layers)
            if "road" in  infra:
                missing += list(set(["landuse","building","household","individual","road edges","road nodes","landslide fragility"]) - existing_layers)
            if "building" in infra:
                missing += list(set(["landuse","building","household","individual","landslide fragility"]) - existing_layers)
 
        if infra == []:
            missing += ['You should select at least one of power, road or building']
        return missing == [], missing
    
    def pre_compute_checks():
        hazard = layers.value['hazard'].value
        infra = layers.value['infra'].value
        building = layers.value['layers']['building']['data'].value
        household = layers.value['layers']['household']['data'].value
        individual = layers.value['layers']['individual']['data'].value
        landslide_fragility = layers.value['layers']['landslide fragility']['data'].value
        fragility = layers.value['layers']['fragility']['data'].value
        gem_fragility = layers.value['layers']['gem_fragility']['data'].value
        intensity = layers.value['layers']['intensity']['data'].value


        missing_buildings = set(household['bldid']) - set(building['bldid'])
        print('missing buildings', missing_buildings)
        if len(missing_buildings) == 1:
            return False, f"There is {len(missing_buildings)} household without building. Please check your exposure."          
        elif len(missing_buildings) > 1:
            return False, f"There are {len(missing_buildings)} households without buildings. Please check your exposure."
        if hazard == 'landslide':
            unique_records = len(landslide_fragility.groupby(['expstr','susceptibility']).agg({'expstr':'count'}))
            all_records = len(landslide_fragility)
            if unique_records != all_records:
                return False, "there are duplicate expstr + susceptibility records in landslide fragility"

        missing_hospitals = set(household['commfacid']) - set(building['bldid'])
        if len(missing_hospitals) > 0:
            return False, f"Hospital(s) ({missing_hospitals}) do not exist in building data"

        missing_households = [str(x) for x in set(individual['hhid']) - set(household['hhid'])]
        if len(missing_households) > 0:
            error_message = f"There are {len(missing_households)} households associated with individuals but not defined in the household layer: "
            # if there are too many, only show the first 5 and last 5.
            if len(missing_households) > 10:
                error_message += ','.join(missing_households[:5])
                error_message += ',...,'
                error_message += ','.join(missing_households[-5:])
            else:
                error_message += ','.join(missing_households)
            return False, error_message

        if "building" in infra and hazard == "earthquake":
            if gem_fragility is not None:
                exposure_in_fragility = set([f['id'] for f in gem_fragility['fragilityFunctions']])
                exposure_in_building= set(pd.unique(building['expstr']))
                missing_exposures = exposure_in_building - exposure_in_fragility
                print(exposure_in_building, exposure_in_fragility)
                if len(missing_exposures) > 0:
                    return False, f"missing exposures in gem_fragility: {missing_exposures}"

                # Only "discrete" format is supported
                formats_in_fragility = set([f['format'] for f in gem_fragility['fragilityFunctions']]) 
                unsupported_formats = formats_in_fragility - set(['discrete'])
                if len(unsupported_formats) > 0:
                    return False, f"Unsupported GEM fragility format detected: {unsupported_formats}. Only 'discrete' is supported"

                # Check for missing bands
                sa_list = np.array([float(x.split()[-1]) for x in intensity.columns if x.startswith('sa ')])
                sa_cols = [x for x in intensity.columns  if x.startswith('sa ') or x == 'pga']
                imtypes = set([f['imt'].lower().replace('(',' ').replace(')','') for f in gem_fragility['fragilityFunctions']])
                sa_list_in_fragility = np.array([float(x.split()[-1]) for x in imtypes if x.startswith('sa ')])
                missing_bands = set(sa_list_in_fragility) - set(sa_list) 

                non_sa_bands_in_fragility = set([x for x in imtypes if not x.startswith('sa ')])
                non_sa_bands_in_intensity = set([x for x in intensity.columns if not x.startswith('sa ')])
                missing_bands = missing_bands.union(non_sa_bands_in_fragility - non_sa_bands_in_intensity)
                if len(missing_bands) > 0:
                    return False, f"{missing_bands} band(s) should be in the intensity map"

        return True, ''

    def execute_engine():

        def execute_road():
            buildings = layers.value['layers']['building']['data'].value
            household = layers.value['layers']['household']['data'].value
            individual = layers.value['layers']['individual']['data'].value
            nodes = layers.value['layers']['road nodes']['data'].value
            edges = layers.value['layers']['road edges']['data'].value
            intensity = layers.value['layers']['intensity']['data'].value
            fragility = layers.value['layers']['road fragility']['data'].value
            earthquake_intensity_unit = layers.value['earthquake_intensity_unit'].value
            preserve_edge_directions = layers.value['preserve_edge_directions'].value
            if layers.value['hazard'].value == 'landslide':
                fragility = layers.value['layers']['landslide fragility']['data'].value
                trigger_level= layers.value['landslide_trigger_level'].value
                fragility = fragility[['expstr','susceptibility',trigger_level]].rename(columns={trigger_level:'collapse_probability'})
            hazard = layers.value['hazard'].value
            cdf_median_increase_in_percent = layers.value['cdf_median_increase_in_percent'].value
            threshold_increase_culvert_water_height = layers.value['threshold_increase_culvert_water_height'].value
            threshold_increase_road_water_height = layers.value['threshold_increase_road_water_height'].value
            policies = [p['id'] for _, p in layers.value['policies'].items() if f"{p['description']} ({p['label']})" in layers.value['selected_policies'].value]

            edges['ds'] = 0
            edges['is_damaged'] = False
            buildings['node_id'] = None
            buildings['hospital_access'] = False
            household['node_id'] = None
            household['hospital_access'] = False
            individual['facility_access'] = True
            ds, is_damaged, building_node_id, building_hospital_acess, household_node_id, \
                    household_hospital_access, individual_facility_access  = \
                compute_road_infra(buildings, household, individual, nodes, edges, intensity, 
                fragility, hazard, threshold_road_water_height.value, threshold_culvert_water_height.value,
                threshold_flood_distance.value, preserve_edge_directions,
                earthquake_intensity_unit=earthquake_intensity_unit,
                policies=policies,
                cdf_median_increase_in_percent=cdf_median_increase_in_percent,
                threshold_increase_culvert_water_height=threshold_increase_culvert_water_height,
                threshold_increase_road_water_height=threshold_increase_road_water_height,
                )
            
            edges['ds'] = list(ds)
            edges['is_damaged'] = list(is_damaged)
            buildings['node_id'] = list(building_node_id)
            buildings['hospital_access'] = list(building_hospital_acess)
            household['node_id'] = list(household_node_id)   
            household['hospital_access'] = list(household_hospital_access)
            individual['facility_access'] = list(individual_facility_access)
  
            #print(buildings.head())
            print('number of damaged roads/bridges',len(edges[edges['is_damaged']]))

            return edges, buildings, household, individual

        def execute_power():
            buildings = layers.value['layers']['building']['data'].value
            household = layers.value['layers']['household']['data'].value
            nodes = layers.value['layers']['power nodes']['data'].value
            edges = layers.value['layers']['power edges']['data'].value
            intensity = layers.value['layers']['intensity']['data'].value
            fragility = layers.value['layers']['power fragility']['data'].value
            hazard = layers.value['hazard'].value
            earthquake_intensity_unit = layers.value['earthquake_intensity_unit'].value
            preserve_edge_directions = layers.value['preserve_edge_directions'].value
            threshold_flood = [threshold_flood_ds2.value, threshold_flood_ds3.value, threshold_flood_ds4.value]

            if layers.value['hazard'].value == 'landslide':
                fragility = layers.value['layers']['landslide fragility']['data'].value
                trigger_level= layers.value['landslide_trigger_level'].value
                fragility = fragility[['expstr','susceptibility',trigger_level]].rename(columns={trigger_level:'collapse_probability'})

            if layers.value['hazard'].value == 'flood':
                fragility = layers.value['layers']['vulnerability']['data'].value

            ds, is_damaged, is_operational, has_power, household_has_power, hospital_has_power = \
                compute_power_infra(buildings,
                                    household,
                                    nodes, 
                                    edges,
                                    intensity,
                                    fragility,
                                    hazard, threshold_flood, threshold_flood_distance.value,
                                    preserve_edge_directions,
                                    earthquake_intensity_unit=earthquake_intensity_unit,
                                    )
            
            #power_node_df =  dfs['Power Nodes'].copy()                         
            nodes['ds'] = list(ds)
            nodes['is_damaged'] = list(is_damaged)
            nodes['is_operational'] = list(is_operational)
            buildings['has_power'] = has_power
            household['has_power'] = household_has_power
            household['hospital_has_power'] = hospital_has_power
            return nodes, buildings, household

        def execute_building():
            landuse = layers.value['layers']['landuse']['data'].value
            buildings = layers.value['layers']['building']['data'].value
            household = layers.value['layers']['household']['data'].value
            individual = layers.value['layers']['individual']['data'].value
            intensity = layers.value['layers']['intensity']['data'].value

            fragility = layers.value['layers']['fragility']['data'].value
            vulnerability = layers.value['layers']['vulnerability']['data'].value
            earthquake_intensity_unit = layers.value['earthquake_intensity_unit'].value
            flood_depth_reduction = layers.value['flood_depth_reduction'].value
            cdf_median_increase_in_percent = layers.value['cdf_median_increase_in_percent'].value
            damage_curve_suppress_factor = layers.value['damage_curve_suppress_factor'].value
            earthquake_simulation_method = layers.value['earthquake_simulation_method_selected'].value
            threshold_flood = [threshold_flood_ds2.value, threshold_flood_ds3.value, threshold_flood_ds4.value]

            policies = [p['id'] for _, p in layers.value['policies'].items() if f"{p['description']} ({p['label']})" in layers.value['selected_policies'].value]

            # Find most frequent income in a building
            freqincome = household.groupby('bldid')['income'].value_counts().reset_index(name='v')
            freqincome = freqincome.drop_duplicates('bldid')[['bldid','income']]
            freqincome.rename(columns = {'income':'freqincome'}, inplace = True) 

            buildings_freqincome = buildings[['bldid']].merge(freqincome,on='bldid',how='left')
            buildings['freqincome'] = buildings_freqincome['freqincome']
            #print('policies',policies)
            if layers.value['hazard'].value == 'landslide':
                fragility = layers.value['layers']['landslide fragility']['data'].value
                trigger_level= layers.value['landslide_trigger_level'].value
                df_bld_hazard = compute(
                    landuse,
                    buildings,
                    household,
                    individual,
                    intensity,
                    fragility[['expstr','susceptibility',trigger_level]].rename(columns={trigger_level:'collapse_probability'}),
                    layers.value['hazard'].value,
                    policies=policies,
                    threshold_flood = threshold_flood,
                    threshold_flood_distance = threshold_flood_distance.value,
                    earthquake_intensity_unit=earthquake_intensity_unit,
                    cdf_median_increase_in_percent=cdf_median_increase_in_percent,
                    flood_depth_reduction=flood_depth_reduction,
                    damage_curve_suppress_factor=damage_curve_suppress_factor,
                    earthquake_simulation_method=earthquake_simulation_method,
                    )
            else:
                if fragility is None:
                    fragility = layers.value['layers']['gem_fragility']['data'].value
                df_bld_hazard = compute(
                    landuse,
                    buildings,
                    household,
                    individual,
                    intensity,
                    fragility if layers.value['hazard'].value == "earthquake" else vulnerability,
                    layers.value['hazard'].value, policies=policies,
                    threshold_flood = threshold_flood,
                    threshold_flood_distance = threshold_flood_distance.value,
                    earthquake_intensity_unit=earthquake_intensity_unit,
                    cdf_median_increase_in_percent=cdf_median_increase_in_percent,
                    flood_depth_reduction=flood_depth_reduction,
                    damage_curve_suppress_factor=damage_curve_suppress_factor,
                    earthquake_simulation_method=earthquake_simulation_method,
                    )
            buildings['ds'] = list(df_bld_hazard['ds'])
            buildings['casualty'] = list(df_bld_hazard['casualty'])

            return buildings

        def execute_metric():
            landuse = layers.value['layers']['landuse']['data'].value
            buildings = layers.value['layers']['building']['data'].value
            household = layers.value['layers']['household']['data'].value
            individual = layers.value['layers']['individual']['data'].value
            
            tally, tally_geo = create_tally(landuse, buildings, household, individual)
            return tally, tally_geo

        if execute_counter > 0 :
            is_ready, missing = is_ready_to_run(layers.value['infra'].value, layers.value['hazard'].value)
            if not is_ready:
                raise Exception(f'Missing {missing}')
            is_ready, message = pre_compute_checks()
            if not is_ready:
                raise Exception(message)

            if layers.value['hazard'].value == "earthquake" and layers.value['earthquake_simulation_method_selected'].value == 'monte carlo':
                    max_trials = layers.value['earthquake_simulation_trial_count'].value
            elif layers.value['hazard'].value == "landslide":
                max_trials = landslide_max_trials.value
            elif layers.value['hazard'].value == "flood":
                max_trials = 1
            else:
                max_trials = 1

            metrics_results = []
            
            # Dictionary to accumulate damage states and statuses across trials
            mc_accumulator = {
                'building_ds': [],
                'road_edges_ds': [],
                'road_nodes_ds': [],
                'power_nodes_ds': [],
                'power_edges_ds': []
            }

            for trial in range(1,max_trials+1):
                if trial == 1:
                    set_progress_message('Running...')
                else:
                    set_progress_message(f'Monte-Carlo trial {trial}/{max_trials}...')
                if 'power' in layers.value['infra'].value:
                    nodes, buildings, household = execute_power()
                    mc_accumulator['power_nodes_ds'].append(nodes['ds'])
                    # edges are not modified by execute_power but we need them below if applicable
                    layers.value['layers']['power nodes']['data'].set(nodes)
                    layers.value['layers']['building']['data'].set(buildings)
                    layers.value['layers']['household']['data'].set(household)
                    layers.value['layers']['power nodes']['df'].set(nodes.drop(columns=['geometry']))
                    layers.value['layers']['building']['df'].set(buildings.drop(columns=['geometry']))
                    layers.value['layers']['household']['df'].set(household)
                if 'road' in layers.value['infra'].value:
                    edges, buildings, household, individual = execute_road()
                    mc_accumulator['road_edges_ds'].append(edges['ds'])
                    layers.value['layers']['road edges']['data'].set(edges)
                    layers.value['layers']['building']['data'].set(buildings)
                    layers.value['layers']['household']['data'].set(household)
                    layers.value['layers']['individual']['data'].set(individual)
                    layers.value['layers']['road edges']['df'].set(edges.drop(columns=['geometry']))
                    layers.value['layers']['building']['df'].set(buildings.drop(columns=['geometry']))
                    layers.value['layers']['household']['df'].set(household)
                    layers.value['layers']['individual']['df'].set(individual)
                if 'building' in layers.value['infra'].value:
                    buildings = execute_building()
                    mc_accumulator['building_ds'].append(buildings['ds'])
                    layers.value['layers']['building']['data'].set(buildings)
                    layers.value['layers']['building']['df'].set(buildings.drop(columns=['geometry']))

                tally, tally_geo = execute_metric()

                store_in_session_storage('tally', tally)
                store_in_session_storage('tally_geo', tally_geo)
                store_in_session_storage('tally_minimal', tally[lbl_2_str['tally_minimal'].keys()])
                store_info_to_session()
                layers.value['tally_is_available'].value = True
                tally_counter.value += 1

                metrics_result = generate_metrics(tally_geo, tally_geo, 
                                           layers.value['hazard'].value, 
                                           population_displacement_consensus.value)
                metrics_results.append(metrics_result)

            # --- Calculate Mode (Most Frequent Damage State) after all trials ---
            if max_trials > 1:
                if 'building' in layers.value['infra'].value and len(mc_accumulator['building_ds']) > 0:
                    df_modes = pd.DataFrame(mc_accumulator['building_ds']).mode(axis=0)
                    mode_ds = df_modes.iloc[0].astype(int)
                    
                    bld_data = layers.value['layers']['building']['data'].value
                    bld_df = layers.value['layers']['building']['df'].value
                    bld_data['ds'] = mode_ds
                    bld_df['ds'] = mode_ds
                    
                    layers.value['layers']['building']['data'].set(bld_data)
                    layers.value['layers']['building']['df'].set(bld_df)
                
                if 'road' in layers.value['infra'].value and len(mc_accumulator['road_edges_ds']) > 0:
                    df_modes = pd.DataFrame(mc_accumulator['road_edges_ds']).mode(axis=0)
                    mode_ds = df_modes.iloc[0].astype(int)
                    
                    road_edges_data = layers.value['layers']['road edges']['data'].value
                    road_edges_df = layers.value['layers']['road edges']['df'].value
                    road_edges_data['ds'] = mode_ds
                    road_edges_df['ds'] = mode_ds
                    
                    # Update is_damaged based on mode_ds > 0 (or specific threshold if needed)
                    road_edges_data['is_damaged'] = mode_ds > 0
                    road_edges_df['is_damaged'] = mode_ds > 0

                    layers.value['layers']['road edges']['data'].set(road_edges_data)
                    layers.value['layers']['road edges']['df'].set(road_edges_df)
                    
                if 'power' in layers.value['infra'].value and len(mc_accumulator['power_nodes_ds']) > 0:
                    df_modes = pd.DataFrame(mc_accumulator['power_nodes_ds']).mode(axis=0)
                    mode_ds = df_modes.iloc[0].astype(int)
                    
                    power_nodes_data = layers.value['layers']['power nodes']['data'].value
                    power_nodes_df = layers.value['layers']['power nodes']['df'].value
                    power_nodes_data['ds'] = mode_ds
                    power_nodes_df['ds'] = mode_ds
                    
                    power_nodes_data['is_damaged'] = mode_ds > 2 # DS_MODERATE = 2
                    power_nodes_df['is_damaged'] = mode_ds > 2 # DS_MODERATE = 2
                    
                    layers.value['layers']['power nodes']['data'].set(power_nodes_data)
                    layers.value['layers']['power nodes']['df'].set(power_nodes_df)

            layers.value['metrics_realized'].set(metrics_results)
            set_progress_message('')
            # trigger render event
            layers.value['render_count'].set(layers.value['render_count'].value + 1)

            layers.value['datetime_analysis'] =  datetime.datetime.utcnow()

    # Execute the thread only when the depencency is changed
    result = solara.use_thread(execute_engine, dependencies=[execute_counter], intrusive_cancel=False)

    with solara.GridFixed(columns=1):
        solara.Markdown("#### Assets at Risk")
        with solara.Row(justify="left"):
            solara.ToggleButtonsMultiple(value=layers.value['infra'].value, on_value=layers.value['infra'].set, values=["building","power","road"])
        # preserve_edge_directions is only used for graph-based inputs (power and road)
        if set(layers.value['infra'].value) & set(['power','road']):
            with solara.Row(justify="left", style="min-height: 0px"):
                with solara.Tooltip('Obey the edge directions in road/power networks (default: False)'):
                    solara.Checkbox(label='Preserve directions', value=layers.value['preserve_edge_directions'])
                solara.Button(icon_name="mdi-help-box", attributes={"href": "https://github.com/TomorrowsCities/tomorrowscities/wiki/4%E2%80%90Engine#parameters", "target": "_blank"}, text=True, outlined=False)
        solara.Markdown("#### Hazard")
        with solara.Row(justify="left"):
            solara.ToggleButtonsSingle(value=layers.value['hazard'].value, on_value=layers.value['hazard'].set, values=layers.value['hazard_list'])
        if layers.value['hazard'].value == 'landslide':
            solara.Markdown("#### Landslide trigger level")
            with solara.Row(justify="left"):
                solara.ToggleButtonsSingle(value=layers.value['landslide_trigger_level'].value,
                    on_value=layers.value['landslide_trigger_level'].set,
                    values=layers.value['landslide_trigger_level_list'])
        # with solara.Tooltip("Building-level metrics will be increased by 25% and 50% for medium and low"):
            # solara.Markdown("#### Implementation Capacity Score")
        # with solara.Row(justify="left"):
            # solara.ToggleButtonsSingle(value=layers.value['implementation_capacity_score'].value, 
                                # values=['low','medium','high'],
                                # on_value=layers.value['implementation_capacity_score'].set,
                                # )
        MetricParameters()

    solara.ProgressLinear(value=False)
    with solara.Column(style={"width": "100%", "gap": "8px"}):
        solara.Button("Calculate", on_click=on_click, outlined=True,
            disabled=execute_btn_disabled, style={"width": "100%"})
        solara.Button("Reset", on_click=on_reset, outlined=True,
            disabled=False, style={"width": "100%"})
    solara.use_effect(lambda: save_status.set(""), [scenario_name.value])

    if storage.value is not None:        
        solara.InputText(label="Scenario name", value=scenario_name, continuous_update=True)
        if layers.value['tally_is_available'].value and user.value is not None:
            solara.Checkbox(label="Public Scenario", value=is_public)
            solara.Button("Save Scenario",on_click=save_app_state, disabled=False)
        else:
            solara.Button("Save Scenario", disabled=True)
        solara.ProgressLinear(save_app_state.pending)
        if save_status.value == "success":
            solara.Success("Scenario saved successfully!")
        elif save_status.value.startswith("error:"):
            err_msg = save_status.value[len("error:"):].strip()
            solara.Error(f"Failed to save scenario: {err_msg}")
    # The statements in this block are passed several times during thread execution
    # The statements in this block are passed several times during thread execution
    # if result.error is not None:
    #     execute_error.set(execute_error.value + str(result.error))

    if execute_error.value != "":
        solara.Text(f'{execute_error}', style={"color":"red"})
    elif result.error:
        solara.Text(f'{result.error}', style={"color":"red"})
    else:
        solara.Text("Spacer", style={"visibility": "hidden"})

    if result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
        set_execute_btn_disabled(True)
        solara.Text(progress_message)
        solara.ProgressLinear(value=True)
    else:
        solara.Text("Spacer", style={"visibility": "hidden"})
        set_execute_btn_disabled(False)
        solara.ProgressLinear(value=False)
        
@solara.component
def MapInfo():
    print(f'{layers.value["bounds"].value}')
    version = layers.value["version"]
    print(layers.value['map_info_button'].value)
    solara.Div(style={"height": "2px"})
    with solara.Row(justify="center"):
        solara.ToggleButtonsSingle(value=layers.value['map_info_button'].value, 
                               on_value=layers.value['map_info_button'].set, 
                               values=["summary","detail"])

    if layers.value['map_info_button'].value == "summary":
        with solara.GridFixed(columns=2,row_gap="1px"):
            for layer_name,layer in layers.value['layers'].items():
                data = layer['data'].value
                with solara.Tooltip(layer['map_info_tooltip']):
                    solara.Text(f'{layer_name}')
                with solara.Row(justify="right"):
                    if data is None:
                        solara.Text('0')
                    else:
                        if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
                            solara.Text(f"{len(data)}")
                        elif isinstance(data, dict) and layer_name == 'gem_vulnerability':
                            solara.Text(f"{len(data['vulnerabilityFunctions'])}")
                        elif isinstance(data, dict) and layer_name == 'gem_fragility':
                            solara.Text(f"{len(data['fragilityFunctions'])}")

    else:
        with solara.GridFixed(columns=2,row_gap="1px"):
            for key, value in layers.value['map_info_detail'].value.items():
                if key == 'style':
                    continue
                solara.Text(f'{key}')
                with solara.Row(justify="right"):
                    strvalue = str(value)
                    solara.Text(f'{strvalue}')

@solara.component
def ImportDataZone1():
    def s3_file_open(p):
        filename='aws.tmp'
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir,filename)
            storage.value.get_client().download_file(storage.value.bucket_name, str(p)[1:], filepath)
            with open(filepath, 'rb') as fileObj:
                fileContent = fileObj.read()
                file_info = solara.components.file_drop.FileInfo(name=os.path.basename(p),
                                                                size=len(fileContent),
                                                                data=fileContent)
                set_fileinfo([file_info])
            os.unlink(os.path.join(temp_dir, filename))


    def local_file_open(p):
        with open(p, 'rb') as fileObj:
            fileContent = fileObj.read()
            file_info = solara.components.file_drop.FileInfo(name=os.path.basename(p), 
                                                             size=len(fileContent),
                                                             data=fileContent)
            set_fileinfo([file_info])

    total_progress, set_total_progress = solara.use_state(-1)
    fileinfo, set_fileinfo = solara.use_state(None)
    result, set_result = solara.use_state(solara.Result(True))

    generate_message, set_generate_message = solara.use_state("")
    generate_counter, set_generate_counter = solara.use_state(0)
    generate_btn_disabled, set_generate_btn_disabled = solara.use_state(False)
    generate_error = solara.reactive("")

    def on_generate():
        set_generate_counter(generate_counter + 1)
        generate_error.set("")

    def load():
        if fileinfo is not None:
            unrecognized_file_exists = False
            # try not to trigger render inside loop
            updated_center = None
            for f in fileinfo:
                print(f'processing file {f["name"]}')
                name, data = import_data(f)
                if name is not None and data is not None:
                    if isinstance(data, gpd.GeoDataFrame):
                        data = data.set_crs("epsg:4326",allow_override=True)
                        layers.value['layers'][name]['df'].set(data.drop(columns=['geometry']))
                        layers.value['layers'][name]['data'].set(data)
                        # centroids in geometric coordinates (3857: Pseuod-Mercator in meters)
                        # Geographic --> geometric --> calculate centroid --> geographic
                        centroids = data.to_crs('epsg:3857').centroid.to_crs('epsg:4326')
                        #centroids = data.centroid
                        center_y = centroids.y.mean()
                        center_x = centroids.x.mean()
                        updated_center = (center_y, center_x)
                    elif isinstance(data, pd.DataFrame):
                        layers.value['layers'][name]['df'].set(data)
                        layers.value['layers'][name]['data'].set(data)
                    elif isinstance(data, ParameterFile):
                        layers.value['layers'][name]['data'].set(data)
                    elif isinstance(data, dict):
                        layers.value['layers'][name]['data'].set(data)
                else:
                    unrecognized_file_exists = True
            if updated_center:
                layers.value['center'].set(updated_center)
            layers.value['render_count'].set(layers.value['render_count'].value + 1)

            if unrecognized_file_exists:
                return "error"
            return "success"
        return "empty"
    
    def is_ready_to_generate():
        if layers.value['layers']['parameter']['data'].value is not None and \
           layers.value['layers']['landuse']['data'].value is not None:
            return True
        return False

    def handle_reset():
        set_fileinfo(None)
        set_total_progress(-1)
        set_generate_message("")
        set_generate_counter(0)
    solara.use_effect(handle_reset, [reset_counter.value])

    def generate():
        if generate_counter > 0 :
            set_generate_message('Generating exposure...')
            print('Generating exposure...')
            parameter_file = layers.value['layers']['parameter']['data'].value 
            land_use_file = layers.value['layers']['landuse']['data'].value 
            seed = layers.value['seed'].value
            building, household, individual = generate_exposure(parameter_file, land_use_file,
                                                                population_calculate=False, seed=seed)

            for name, data in zip(['building','household','individual'],[building, household, individual]):
                data = layers.value['layers'][name]['pre_processing'](data, layers.value['layers'][name]['extra_cols'])
                print('hkaya',name)
                #print(data)
                layers.value['layers'][name]['data'].set(data)
                if  "geometry" in list(data.columns):
                    center = (data.geometry.centroid.y.mean(), data.geometry.centroid.x.mean())
                    layers.value['center'].set(center)

            layers.value['render_count'].value += 1

    def progress(x):
        set_total_progress(x)

    def on_file_deneme(f):
        set_fileinfo(f)
        
    def open_file_dialog():
        print('entered open file dialog...')    
        
    def on_clear():
        reset_session()

    def load_sample_scenario():
        try:
            sample_dir = EXPOSURE_DATA_ASSET_DIR / "sample_scenario_input"
            sample_files = [
                "1_landuse.geojson",
                "2_building.geojson",
                "3_household.xlsx",
                "4_individual.xlsx",
                "5_flood_vulnerability_dummy.xlsx",
                "6_intensity_dummy.geojson",
            ]
            loaded_files = []
            for filename in sample_files:
                path = sample_dir / filename
                loaded_files.append({
                    "name": path.name,
                    "data": path.read_bytes(),
                    "size": path.stat().st_size,
                })
            set_fileinfo(loaded_files)
            notify_success("Sample scenario input loaded.")
        except Exception as exc:
            notify_error(f"Failed to load sample scenario input: {exc}")
    
    result = solara.use_thread(load, dependencies=[fileinfo], intrusive_cancel=False)
    generate_result = solara.use_thread(generate, dependencies=[generate_counter], intrusive_cancel=False)

    #with solara.Row(justify="center"):
    #    solara.ToggleButtonsSingle(value=layers.value['data_import_method'].value, 
    #                            on_value=layers.value['data_import_method'].set, 
    #                            values=["drag&drop","s3"], 
    #                            style={"align-items": "center"})
    with solara.Column(style={"width":"100%", "align":"stretch", "padding": "0 15px"}):
    #with solara.Card(title="Upload", subtitle="Drag & Drop from your local drive"):
        solara.Markdown('''<div style="text-align: justify">
                        Drag & drop your local files to 
                        the below area. Supported formats are Excel, GeoTIFF, JSON, GeoJSON, and GEM XML.
                        For more information, please refer to <a href="https://github.com/TomorrowsCities/tomorrowscities/wiki" target="_blank">Data Formats</a>.</br>
                        You can download and extract our <a href="https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view?usp=sharing" 
                        target="_blank">Sample Dataset</a> to your local drive and upload to the platform via drag & drop.
                        </div>
                        ''')
        FileDropMultiple(on_total_progress=progress,
                on_file=on_file_deneme, 
                lazy=False,
                label='Drop files here or click to browse',
                uid=str(reset_counter.value))
                
        #with solara.Column():
        def sample_data():
            with solara.Column() as main:
                solara.Markdown('''You can also choose sample data from our AWS S3 repository. 
                                Double click to load data into the platform.
                            ''')   
                print("..............",storage.value)
                S3FileBrowser(storage.value, "tcdse", can_select=True, on_file_open=s3_file_open, start_directory='/datastore')
            return main
        
        if storage.value is not None:        
            solara.Details(
            summary="Upload Data from Cloud",
            children=[sample_data()],
            expand=False
            )
            solara.Button("Load Sample Scenario", on_click=load_sample_scenario, outlined=True, style={"width": "100%"})
        
        with solara.Row(style={"width": "100%"}):
            solara.Button("Clear", on_click=on_clear, text=True, outlined=True, style={"width": "100%"})
        
    if total_progress > -1 and total_progress < 100:
        solara.Text(f"Uploading {total_progress}%")
        solara.ProgressLinear(value=total_progress)
    else:
        if result.state == solara.ResultState.FINISHED:
            if result.value == "success":
                solara.Success("Data is successfully loaded and ready for analysis.")
            elif result.value == "error":
                solara.Text("Unrecognized file")
            else:
                solara.Text("Spacer", style={'visibility':'hidden'})
            solara.ProgressLinear(value=False)
        elif result.state == solara.ResultState.INITIAL:
            solara.Text("Spacer", style={'visibility':'hidden'})
            solara.ProgressLinear(value=False)
        elif result.state == solara.ResultState.ERROR:
            solara.Text(f'{result.error}')
            solara.ProgressLinear(value=False)
        else:
            solara.Text("Please wait...")
            solara.ProgressLinear(value=True)

@solara.component
def ImportDataZone2():
    generation_mode, set_generation_mode = solara.use_state("Expert")
    basic_country, set_basic_country = solara.use_state("Kenya")
    parameter_fileinfo, set_parameter_fileinfo = solara.use_state(None)
    landuse_fileinfo, set_landuse_fileinfo = solara.use_state(None)
    landuse_file_name, set_landuse_file_name = solara.use_state("")
    parameter_file_name, set_parameter_file_name = solara.use_state("")
    constraint_file_names, set_constraint_file_names = solara.use_state([])
    generate_counter, set_generate_counter = solara.use_state(0)
    osm_counter, set_osm_counter = solara.use_state(0)
    basic_table_df, set_basic_table_df = solara.use_state(None)
    basic_page, set_basic_page = solara.use_state(0)
    basic_page_size = 8

    def handle_reset():
        set_generation_mode("Expert")
        set_basic_country("Kenya")
        set_parameter_fileinfo(None)
        set_landuse_fileinfo(None)
        set_landuse_file_name("")
        set_parameter_file_name("")
        set_constraint_file_names([])
        set_generate_counter(0)
        set_osm_counter(0)
        set_basic_table_df(None)
        set_basic_page(0)
    solara.use_effect(handle_reset, [reset_counter.value])

    def sync_basic_mode_state():
        landuse_gdf = layers.value["layers"]["landuse"]["data"].value
        if generation_mode == "Basic" and landuse_gdf is not None:
            if basic_table_df is None or len(basic_table_df) != len(landuse_gdf):
                set_basic_table_df(create_basic_mapping_table(landuse_gdf))
                set_basic_page(0)
        elif generation_mode != "Basic" and basic_table_df is not None:
            set_basic_table_df(None)
            set_basic_page(0)

    solara.use_effect(sync_basic_mode_state, [generation_mode, landuse_file_name, layers.value["render_count"].value])

    def load_constraint_bytes(files):
        constraint_gdf = read_multiple_geospatial_bytes(files)
        if constraint_gdf is None or constraint_gdf.empty:
            clear_layer_data("constraint")
            set_constraint_file_names([])
            notify_warning("No valid constraint features were found in the uploaded files.")
            return
        set_constraint_file_names([fileinfo["name"] for fileinfo in files])
        set_layer_data("constraint", constraint_gdf)
        layers.value["render_count"].set(layers.value["render_count"].value + 1)
        notify_success("Constraint layer loaded.")

    def update_basic_table(column_name, row_index, value):
        if basic_table_df is None:
            return
        updated = basic_table_df.copy()
        updated.at[row_index, column_name] = value
        updated = normalize_basic_mapping_table(updated)
        set_basic_table_df(updated)

    def sync_basic_landuse_preview():
        if generation_mode != "Basic" or basic_table_df is None:
            return
        landuse_gdf = layers.value["layers"]["landuse"]["data"].value
        if landuse_gdf is None or len(landuse_gdf) != len(basic_table_df):
            return

        preview_gdf = landuse_gdf.copy()
        if "mapped_luf" in basic_table_df.columns:
            preview_luf = basic_table_df["mapped_luf"].where(
                basic_table_df["mapped_luf"] != BASIC_LUF_PLACEHOLDER,
                preview_gdf["luf"] if "luf" in preview_gdf.columns else ""
            )
            preview_gdf["luf"] = preview_luf.values
        if "mapped_avgincome" in basic_table_df.columns:
            preview_income = basic_table_df["mapped_avgincome"].where(
                basic_table_df["mapped_avgincome"] != BASIC_INCOME_PLACEHOLDER,
                preview_gdf["avgincome"] if "avgincome" in preview_gdf.columns else ""
            )
            preview_gdf["avgincome"] = preview_income.values

        set_layer_data("landuse", preview_gdf, update_center=False)
        layers.value["render_count"].set(layers.value["render_count"].value + 1)

    solara.use_effect(sync_basic_landuse_preview, [generation_mode, basic_table_df])

    def load_sample_expert():
        try:
            parameter_path = EXPOSURE_DATA_ASSET_DIR / "sample_input_expert_mode" / "sample_distribution_file.xlsx"
            landuse_path = EXPOSURE_DATA_ASSET_DIR / "sample_input_expert_mode" / "sample_landuse_file.geojson"
            constraint_paths = [
                EXPOSURE_DATA_ASSET_DIR / "sample_input_expert_mode" / "exclusion_lines.geojson",
                EXPOSURE_DATA_ASSET_DIR / "sample_input_expert_mode" / "exclusion_points.geojson",
                EXPOSURE_DATA_ASSET_DIR / "sample_input_expert_mode" / "exclusion_polygons.geojson",
            ]

            parameter_bytes = parameter_path.read_bytes()
            landuse_bytes = landuse_path.read_bytes()
            constraint_files = [{"name": path.name, "data": path.read_bytes()} for path in constraint_paths]

            set_generation_mode("Expert")
            parameter_file = {"name": parameter_path.name, "data": parameter_bytes}
            landuse_file = {"name": landuse_path.name, "data": landuse_bytes}
            set_parameter_fileinfo(parameter_file)
            set_parameter_file_name(parameter_path.name)
            set_layer_data("parameter", ParameterFile(content=parameter_bytes))
            on_landuse_file(landuse_file)
            load_constraint_bytes(constraint_files)
            notify_success("Expert sample input loaded.")
        except Exception as exc:
            notify_error(f"Failed to load Expert sample input: {exc}")

    def load_sample_basic():
        try:
            landuse_path = EXPOSURE_DATA_ASSET_DIR / "sample_input_basic_mode" / "sample_landuse_file_basic.geojson"
            constraint_paths = [
                EXPOSURE_DATA_ASSET_DIR / "sample_input_basic_mode" / "exclusion_lines.geojson",
                EXPOSURE_DATA_ASSET_DIR / "sample_input_basic_mode" / "exclusion_points.geojson",
                EXPOSURE_DATA_ASSET_DIR / "sample_input_basic_mode" / "exclusion_polygons.geojson",
            ]

            landuse_bytes = landuse_path.read_bytes()
            constraint_files = [{"name": path.name, "data": path.read_bytes()} for path in constraint_paths]

            set_generation_mode("Basic")
            set_basic_country("Kenya")
            set_parameter_fileinfo(None)
            set_parameter_file_name("")
            clear_layer_data("parameter")
            on_landuse_file({"name": landuse_path.name, "data": landuse_bytes})
            load_constraint_bytes(constraint_files)
            notify_success("Basic sample input loaded.")
        except Exception as exc:
            notify_error(f"Failed to load Basic sample input: {exc}")

    def on_parameter_file(fileinfo):
        try:
            parameter_data = fileinfo["data"]
            set_parameter_fileinfo(fileinfo)
            set_parameter_file_name(fileinfo["name"])
            set_layer_data("parameter", ParameterFile(content=parameter_data))
            notify_success("Parameter file loaded.")
        except Exception as exc:
            clear_layer_data("parameter")
            notify_error(f"Failed to read parameter file: {exc}")

    def on_landuse_file(fileinfo):
        try:
            landuse_gdf = read_geospatial_bytes(fileinfo["name"], fileinfo["data"])
            set_landuse_fileinfo(fileinfo)
            set_landuse_file_name(fileinfo["name"])
            set_layer_data("landuse", landuse_gdf, update_center=True)
            if generation_mode == "Basic":
                set_basic_table_df(create_basic_mapping_table(landuse_gdf))
                set_basic_page(0)
            else:
                set_basic_table_df(None)
                set_basic_page(0)
            layers.value["render_count"].set(layers.value["render_count"].value + 1)
            notify_success("Land-use layer loaded.")
        except Exception as exc:
            clear_layer_data("landuse")
            set_landuse_fileinfo(None)
            set_landuse_file_name("")
            notify_error(f"Failed to read land-use layer: {exc}")

    def on_constraint_files(files):
        try:
            load_constraint_bytes(files)
        except Exception as exc:
            clear_layer_data("constraint")
            set_constraint_file_names([])
            notify_error(f"Failed to read constraint layers: {exc}")

    def on_generate():
        set_generate_counter(generate_counter + 1)

    def on_fetch_osm():
        set_osm_counter(osm_counter + 1)

    def generate():
        if generate_counter <= 0:
            return None
        if landuse_fileinfo is None:
            raise ValueError("Upload a land-use layer before generating data.")

        if generation_mode == "Basic":
            if basic_table_df is None:
                raise ValueError("Basic Mode mapping table is not ready yet.")
            parameter_source = BASIC_MODE_CONFIG[basic_country]["file"]
            landuse_gdf = prepare_basic_landuse(
                landuse_fileinfo["name"],
                landuse_fileinfo["data"],
                basic_country,
                basic_table_df,
            )
            set_layer_data("landuse", landuse_gdf, update_center=True)
        else:
            if parameter_fileinfo is None:
                raise ValueError("Upload a parameter file before generating data.")
            parameter_source = read_excel_bytes(parameter_fileinfo["data"])
            landuse_gdf = layers.value["layers"]["landuse"]["data"].value
            if landuse_gdf is None:
                raise ValueError("Upload a land-use layer before generating data.")

        clear_log_buffer()
        set_log_sink(lambda level, message: {
            "info": notify_info,
            "warning": notify_warning,
            "error": notify_error,
        }.get(level, notify_info)(message))
        try:
            final, household, individual = process_generated_exposure(
                parameter_source,
                landuse_gdf,
                layers.value["layers"]["constraint"]["data"].value,
                seed=layers.value["seed"].value,
            )
        finally:
            set_log_sink(None)

        for name, data in zip(["building", "household", "individual"], [final, household, individual]):
            prepared = layers.value["layers"][name]["pre_processing"](data, layers.value["layers"][name]["extra_cols"])
            set_layer_data(name, prepared, update_center=(name == "building"))

        layers.value["render_count"].set(layers.value["render_count"].value + 1)
        return config.get(
            "data_generation_complete_message",
            "Building, household, and individual layers are ready for analysis.",
        )

    def fetch_and_merge_osm():
        if osm_counter <= 0:
            return None
        landuse_gdf = layers.value["layers"]["landuse"]["data"].value
        if landuse_gdf is None:
            raise ValueError("Load a land-use layer before fetching OSM buildings and roads.")

        osm_constraints = fetch_osm_constraints(landuse_gdf)
        if osm_constraints.empty:
            return 0

        merged_constraints = merge_constraints(
            layers.value["layers"]["constraint"]["data"].value,
            osm_constraints,
        )
        set_layer_data("constraint", merged_constraints)
        layers.value["render_count"].set(layers.value["render_count"].value + 1)
        return len(osm_constraints)

    generate_result = solara.use_thread(generate, dependencies=[generate_counter], intrusive_cancel=False)
    osm_result = solara.use_thread(fetch_and_merge_osm, dependencies=[osm_counter], intrusive_cancel=False)

    ready_to_generate = (
        landuse_fileinfo is not None and
        ((generation_mode == "Expert" and parameter_fileinfo is not None) or (generation_mode == "Basic" and basic_table_df is not None))
    )
    page_count = max(1, int(np.ceil(len(basic_table_df) / basic_page_size))) if basic_table_df is not None and len(basic_table_df) > 0 else 1

    def handle_generate_notifications():
        if generate_counter <= 0:
            return
        if generate_result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
            notify_info("Generating exposure...")
        elif generate_result.state == solara.ResultState.FINISHED and generate_result.value is not None:
            notify_success(generate_result.value)
        elif generate_result.state == solara.ResultState.ERROR and generate_result.error is not None:
            notify_error(str(generate_result.error))

    def handle_osm_notifications():
        if osm_counter <= 0:
            return
        if osm_result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
            notify_info("Fetching OSM buildings and roads...")
        elif osm_result.state == solara.ResultState.FINISHED:
            if osm_result.value == 0:
                notify_warning("No OSM building or road geometries were found inside the loaded land-use extent.")
            elif osm_result.value is not None:
                notify_success(f"Added {osm_result.value} OSM geometries to the constraint layer.")
        elif osm_result.state == solara.ResultState.ERROR and osm_result.error is not None:
            notify_error(str(osm_result.error))

    solara.use_effect(handle_generate_notifications, [generate_counter, generate_result.state])
    solara.use_effect(handle_osm_notifications, [osm_counter, osm_result.state])

    with solara.Column(classes=["generate-data-panel"], style={"width": "100%", "max-width": "100%", "overflow-x": "hidden", "padding": "0 15px", "box-sizing": "border-box"}):
        solara.Markdown(
            """
            <div style="text-align: justify">
            Switch between Expert and Basic generation modes to produce building, household, and individual data directly inside Engine.
            You can optionally add exclusion or alignment layers, then enrich them with OSM buildings and roads before generation.
            </div>
            """
        )

        solara.ToggleButtonsSingle(
            value=generation_mode,
            on_value=set_generation_mode,
            values=["Expert", "Basic"],
            style={"width": "100%"},
        )

        with solara.Column(classes=["generate-data-actions"], style={"width": "100%", "max-width": "100%", "gap": "8px"}):
            if generation_mode == "Expert":
                solara.Button(
                    "Load Sample Input",
                    on_click=load_sample_expert,
                    outlined=True,
                    classes=["generate-data-action-button"],
                    style={"width": "100%"},
                )
                with solara.FileDownload(
                    (EXPOSURE_DATA_ASSET_DIR / "sample_input_expert_mode" / "sample_input_expert_mode.zip").read_bytes(),
                    "sample_input_expert_mode.zip",
                    mime_type="application/zip",
                ):
                    solara.Button(
                        "Download Sample Input",
                        outlined=True,
                        classes=["generate-data-action-button"],
                        style={"width": "100%"},
                    )
            else:
                solara.Button(
                    "Load Sample Input",
                    on_click=load_sample_basic,
                    outlined=True,
                    classes=["generate-data-action-button"],
                    style={"width": "100%"},
                )
                with solara.FileDownload(
                    (EXPOSURE_DATA_ASSET_DIR / "sample_input_basic_mode" / "sample_input_basic_mode.zip").read_bytes(),
                    "sample_input_basic_mode.zip",
                    mime_type="application/zip",
                ):
                    solara.Button(
                        "Download Sample Input",
                        outlined=True,
                        classes=["generate-data-action-button"],
                        style={"width": "100%"},
                    )

        if generation_mode == "Expert":
            solara.Markdown("**Parameter File (.xlsx)**")
            FileDrop(
                on_file=on_parameter_file,
                lazy=False,
                label="Drop parameter file here or click to browse",
                uid=f"parameter-{reset_counter.value}",
            )
            if parameter_file_name:
                solara.Text(f"Loaded: {parameter_file_name}")
        else:
            solara.Select(
                label="Country Distribution",
                value=basic_country,
                values=list(BASIC_MODE_CONFIG.keys()),
                on_value=set_basic_country,
            )
            solara.Info("Basic Mode uses predefined distribution catalogues. Upload land-use data and complete the mapping table below.")

        solara.Markdown("**Land-Use Layer (.geojson, .zip, .rar, .kml, .gpkg)**")
        FileDrop(
            on_file=on_landuse_file,
            lazy=False,
            label="Drop land-use layer here or click to browse",
            uid=f"landuse-{reset_counter.value}",
        )
        if landuse_file_name:
            solara.Text(f"Loaded: {landuse_file_name}")

        solara.Markdown("**Constraint Layers (optional)**")
        FileDropMultiple(
            on_file=on_constraint_files,
            lazy=False,
            label="Drop exclusion/alignment layers here or click to browse",
            uid=f"constraint-{reset_counter.value}",
        )
        if constraint_file_names:
            solara.Text(f"Loaded: {', '.join(constraint_file_names)}")

        with solara.Column(classes=["generate-data-actions"], style={"width": "100%", "max-width": "100%", "gap": "8px"}):
            solara.Button(
                "Add OSM Buildings/Roads",
                on_click=on_fetch_osm,
                outlined=True,
                disabled=layers.value["layers"]["landuse"]["data"].value is None,
                classes=["generate-data-action-button"],
                style={"width": "100%"},
            )
            solara.Button(
                "Generate",
                on_click=on_generate,
                outlined=True,
                disabled=not ready_to_generate,
                classes=["generate-data-action-button"],
                style={"width": "100%"},
            )
            solara.Button(
                "Clear",
                on_click=reset_session,
                text=True,
                outlined=True,
                classes=["generate-data-action-button"],
                style={"width": "100%"},
            )

        if generation_mode == "Basic" and basic_table_df is not None:
            solara.Markdown("**Land Use Configuration Table**")
            solara.Markdown(
                f"Detected **{len(basic_table_df)}** polygons in **{landuse_file_name}**. "
                "Enter `mapped_luf`, `mapped_avgincome`, `mapped_population`, and `mapped_setback` values."
            )
            solara.Markdown(
                f"`{BASIC_LUF_PLACEHOLDER}` ve `{BASIC_INCOME_PLACEHOLDER}` placeholder olarak kalmamalı."
            )
            solara.Markdown(
                "Allowed `mapped_avgincome` values: "
                + ", ".join(INCOME_OPTIONS)
            )
            with solara.Details(summary="Allowed Land Use Types", expand=False):
                for idx, label in enumerate(URBAN_ATLAS_CLASSES, start=1):
                    solara.Markdown(f"{idx}. {label}")

            start = basic_page * basic_page_size
            end = min(start + basic_page_size, len(basic_table_df))
            with solara.Row(style={"width": "100%", "flex-wrap": "wrap"}):
                solara.Button("Previous", on_click=lambda: set_basic_page(max(0, basic_page - 1)), disabled=basic_page == 0, text=True)
                solara.Text(f"Rows {start + 1}-{end} of {len(basic_table_df)}")
                solara.Button("Next", on_click=lambda: set_basic_page(min(page_count - 1, basic_page + 1)), disabled=basic_page >= page_count - 1, text=True)

            current_rows = basic_table_df.iloc[start:end]
            for row_index, row in current_rows.iterrows():
                with solara.Card(title=f"Polygon {row_index + 1}", elevation=1, classes=["generate-data-card"], style={"width": "100%", "max-width": "100%", "box-sizing": "border-box"}):
                    preview_cols = [col for col in basic_table_df.columns if col not in ["mapped_luf", "mapped_avgincome", "mapped_population", "mapped_setback"]][:4]
                    if preview_cols:
                        preview_parts = [f"{col}: {row[col]}" for col in preview_cols]
                        solara.Markdown(" | ".join(preview_parts))
                    with solara.GridFixed(columns=2):
                        solara.Select(
                            label="mapped_luf",
                            value=str(row["mapped_luf"]),
                            values=[BASIC_LUF_PLACEHOLDER] + URBAN_ATLAS_CLASSES,
                            on_value=lambda value, idx=row_index: update_basic_table("mapped_luf", idx, value),
                        )
                        solara.Select(
                            label="mapped_avgincome",
                            value=str(row["mapped_avgincome"]),
                            values=[BASIC_INCOME_PLACEHOLDER] + INCOME_OPTIONS,
                            on_value=lambda value, idx=row_index: update_basic_table("mapped_avgincome", idx, value),
                        )
                        solara.InputFloat(
                            label="mapped_population",
                            value=float(row["mapped_population"]),
                            on_value=lambda value, idx=row_index: update_basic_table("mapped_population", idx, value),
                        )
                        solara.InputFloat(
                            label="mapped_setback",
                            value=float(row["mapped_setback"]),
                            on_value=lambda value, idx=row_index: update_basic_table("mapped_setback", idx, value),
                        )

    if osm_result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
        solara.ProgressLinear(value=True)
    elif osm_result.state in [solara.ResultState.FINISHED, solara.ResultState.ERROR]:
        solara.ProgressLinear(value=False)

    if generate_result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
        solara.ProgressLinear(value=True)
    elif generate_result.state in [solara.ResultState.FINISHED, solara.ResultState.ERROR]:
        solara.ProgressLinear(value=False)

@solara.component
def EngineSidebarContent():
    with solara.lab.Tabs(value=selected_tab.value, on_value=selected_tab.set, grow=True, align="center"):
        with solara.lab.Tab("DATA IMPORT"):
            solara.Details(
                summary="Upload Data",
                children=[ImportDataZone1()],
                expand=False
            )
            solara.Details(
                summary="Generate Data",
                children=[ImportDataZone2()],
                expand=False
            )
        with solara.lab.Tab("SETTINGS"):
            ExecutePanel()
        with solara.lab.Tab("MAP INFO"):
            MapInfo()

@solara.component
def WebApp():
    solara.Title(" ")
    
    def on_load():
        session_data = read_from_session_storage('engine_initialized')
        if session_data is None:
            reset_session()
            store_in_session_storage('engine_initialized', True)
        else:
            reload_info_from_session()
            
    solara.use_effect(on_load, [])

    # Mobile View: Content at the top
    with solara.Column(classes=["d-block", "d-md-none"], style={"width": "100%"}):
        EngineSidebarContent()

    # Desktop View: Content in Sidebar
    with solara.Sidebar():
        with solara.Column(classes=["d-none", "d-md-block"]):
             EngineSidebarContent()

    NotificationCenter()

    # LayerController()
    MapViewer()
    with solara.Row(justify="center"):
        MetricPanel()
    #LayerDisplayer()
    solara.Details(
        summary="Metric Statistics",
        children=[MetricStatistics()],
        expand=False
    )
    solara.Details(
        summary="Layer Details",
        children=[LayerDisplayer()],
        expand=False
    )
    solara.Details(
        summary="Data Tables & Charts",
        children=[GeneratedDataTablesCharts()],
        expand=False
    )
    solara.Text("Spacer", style={"visibility": "hidden"})

    with ConfirmationDialog(
        layers.value['dialog_message_to_be_shown'].value is not None,
        on_close=clear_help_topic,
        ok="Close",
        title="Information Box",
        ):
        solara.Markdown(f'{layers.value["dialog_message_to_be_shown"].value}')

@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    css = """
    .v-menu__content {
        z-index: 2000 !important;
    }

    .v-application {
        line-height: 1;
    }
    .v-input {
        /* height: 10px; removed to fix overlap issue */
    }

    .v-btn-toggle:not(.v-btn-toggle--dense) .v-btn.v-btn.v-size--default {
        height: 24px;
        min-height: 0;
        min-width: 24px;
    }

    .leaflet-container {
        z-index: 1;
    }

    .map-shell {
        position: relative;
        width: 100%;
    }

    .map-filter-overlay {
        position: absolute;
        top: 130px;
        left: 14px;
        z-index: 1000;
        width: auto;
        max-width: calc(100% - 20px);
        pointer-events: auto;
    }

    .map-filter-content {
        max-height: 38vh;
        overflow-y: auto;
        padding-top: 8px;
        padding-right: 4px;
    }

    .map-filter-toggle,
    .map-filter-toggle:hover {
        width: 32px !important;
        min-width: 32px !important;
        height: 32px !important;
        line-height: 32px !important;
        padding: 0 !important;
        border-radius: 2px !important;
        background-color: var(--jp-layout-color1) !important;
        color: var(--jp-ui-font-color1) !important;
        border-width: calc(var(--jp-border-width) + 1px) !important;
        border-color: var(--jp-border-color1) !important;
        position: relative !important;
    }

    .map-filter-toggle.v-btn--disabled {
        opacity: 0.55 !important;
        pointer-events: none !important;
        background-color: var(--jp-layout-color1) !important;
        color: var(--jp-ui-font-color1) !important;
        border-color: var(--jp-border-color1) !important;
    }

    .map-filter-panel h4 {
        margin: 0 0 4px 0;
        font-size: 14px;
        line-height: 1.2;
    }

    .map-filter-panel .filter-section-button,
    .map-filter-panel .filter-section-button .v-btn {
        width: 100% !important;
        justify-content: flex-start !important;
        text-align: left !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        letter-spacing: 0.02em;
    }

    .filter-menu-body {
        background: linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(248,250,252,1) 100%);
        border: 1px solid rgba(31,42,51,0.08);
        border-radius: 10px;
        padding: 10px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
    }

    .v-tabs-bar {
        height: 36px;
    }

    .solara-file-browser {
        overflow: auto;
    }

    .generate-data-panel {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
        box-sizing: border-box !important;
    }

    .generate-data-panel .v-input,
    .generate-data-panel .v-select,
    .generate-data-panel .v-text-field,
    .generate-data-panel .v-btn-toggle,
    .generate-data-panel .v-card,
    .generate-data-panel .widget-image,
    .generate-data-panel .lm-Widget {
        max-width: 100% !important;
        min-width: 0 !important;
        box-sizing: border-box !important;
    }

    .generate-data-panel .v-card__text,
    .generate-data-panel .v-card__title,
    .generate-data-panel .v-card__subtitle {
        white-space: normal !important;
        word-break: break-word !important;
    }

    .generate-data-panel .v-application .row,
    .generate-data-panel .row,
    .generate-data-panel .widget-grid,
    .generate-data-panel .generate-data-grid {
        max-width: 100% !important;
        min-width: 0 !important;
    }

    .generate-data-actions {
        width: 100% !important;
        max-width: 100% !important;
    }

    .generate-data-action-button,
    .generate-data-action-button .v-btn {
        width: 100% !important;
        max-width: 100% !important;
    }

    .generate-data-panel .v-btn-toggle {
        width: 100% !important;
        display: flex !important;
    }

    .generate-data-panel .v-btn-toggle .v-btn {
        flex: 1 1 50% !important;
        max-width: 50% !important;
    }

    @media (max-width: 960px) {
        .v-app-bar__nav-icon {
            display: none !important;
        }
        .v-navigation-drawer {
            display: none !important;
        }
        .v-navigation-drawer__overlay, .v-overlay__scrim {
            display: none !important;
        }
        .v-navigation-drawer, .v-navigation-drawer__overlay, .v-overlay__scrim, .v-overlay {
            display: none !important;
            pointer-events: none !important;
        }
        html, body {
            overflow-y: auto !important;
            height: auto !important;
            position: relative !important;
            pointer-events: auto !important;
        }
        .v-application, .v-application--wrap, .v-main, .v-content {
            overflow: visible !important;
            height: auto !important;
            pointer-events: auto !important;
        }
    }
    """
    solara.Style(value=css)
    solara.Title(" ")

    WebApp()
