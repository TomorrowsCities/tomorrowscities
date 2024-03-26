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
from ipyleaflet import AwesomeIcon, CircleMarker, Marker
import numpy as np
import rasterio 
from rasterio.warp import calculate_default_transform, reproject, Resampling
import io
from shapely.geometry import Point, Polygon
import xml
import logging, sys
#logging.basicConfig(stream=sys.stderr, level=logging.INFO)
import pickle
import datetime
from .settings import storage, landslide_max_trials, revive_storage
from .settings import threshold_flood, threshold_flood_distance, threshold_road_water_height, threshold_culvert_water_height
from ..backend.engine import compute, compute_power_infra, compute_road_infra, calculate_metrics, generate_exposure
from ..backend.utils import building_preprocess, identity_preprocess, ParameterFile
from .utilities import S3FileBrowser, extension_list, extension_list_w_dots
from ..components.file_drop import FileDropMultiple
from .docs import data_import_help
import ipywidgets
import ipydatagrid

layers = solara.reactive({
    'infra': solara.reactive(["building"]),
    'hazard': solara.reactive("flood"),
    'hazard_list': ["earthquake","flood","landslide"],
    'datetime_analysis': datetime.datetime.utcnow(),
    'landslide_trigger_level': solara.reactive('moderate'),
    'landslide_trigger_level_list': ['minor','moderate','severe'],
    'dialog_message_to_be_shown': solara.reactive(None),
    'seed': solara.reactive(42),
    'version': '0.2.4_fix2',
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
        'building': {
            'render_order': 50,
            'map_info_tooltip': 'Number of buildings',
            'data': solara.reactive(None),
            'df': solara.reactive(None),
            'pre_processing': building_preprocess,
            'extra_cols': {'freqincome': '', 'ds': 0, 'metric1': 0, 'metric2': 0, 'metric3': 0,'metric4': 0, 'metric5': 0,'metric6': 0,'metric7': 0, 'metric8': 0,
                            'node_id': None,'hospital_access': True, 'has_power': True, 'casualty': 0},
            'filter_cols': ['expstr'],
            'attributes_required': [set(['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac'])],
            'attributes': [set(['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac'])]},
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
                         'income', 'eq_vuln'])]},
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
    'center': solara.reactive((41.01,28.98)),
    'render_count': solara.reactive(0),
    'bounds': solara.reactive(None),
    'selected_policies': solara.reactive([]),
    'policies': {
        '1': {'id':1, 'label': 'P1', 'description': 'Land and tenure security program', 'applied': solara.reactive(False)},
        '2': {'id':2, 'label': 'P2', 'description': 'State-led upgrading/retrofitting of low-income/informal housing', 'applied': solara.reactive(False)},
        '3': {'id':3, 'label': 'P3', 'description': 'Robust investment in WASH (water, sanitation and hygiene) and flood-control infrastructure', 'applied': solara.reactive(False)},
        '4': {'id':4, 'label': 'P4', 'description': 'Investments in road networks and public spaces through conventional paving', 'applied': solara.reactive(False)},
        '5': {'id':5, 'label': 'P5', 'description': 'Shelter Law - All low-income and informal settlements should have physical and free access to community centres and shelters', 'applied': solara.reactive(False)},
        '6': {'id':6, 'label': 'P6', 'description': 'Funding community-based networks in low-income areas (holistic approaches)', 'applied': solara.reactive(False)},
        '7': {'id':7, 'label': 'P7', 'description': 'Urban farming programs', 'applied': solara.reactive(False)},
        '8': {'id':8, 'label': 'P8', 'description': 'Emergency cash transfers to vulnerable households', 'applied': solara.reactive(False)},
        '9': {'id':9, 'label': 'P9', 'description': 'Waste collection and rivers cleaning program ', 'applied': solara.reactive(False)},
        '10': {'id':10, 'label': 'P10', 'description': 'Enforcement of environmental protection zones', 'applied': solara.reactive(False)},
        '11': {'id':11, 'label': 'I1', 'description': 'DRR-oriented zoning and urban transformation', 'applied': solara.reactive(False)},
        '12': {'id':12, 'label': 'I2', 'description': 'Increased monitoring and supervision on new constructions in terms of disaster-resilience', 'applied': solara.reactive(False)},
        '13': {'id':13, 'label': 'I3', 'description': 'Taking social equality into consideration in the making of urbanisation and DRR policies', 'applied': solara.reactive(False)},
        '14': {'id':14, 'label': 'I4', 'description': 'Establishing financial supports to incentivise the public, which can be referred to as "policy financing"', 'applied': solara.reactive(False)},
        '15': {'id':15, 'label': 'I5', 'description': 'Awareness raising on disasters and disaster risk reduction', 'applied': solara.reactive(False)},
        '16': {'id':16, 'label': 'I6', 'description': 'Strengthening of Büyükçekmece bridge against earthquake and tsunami risks', 'applied': solara.reactive(False)},
        '17': {'id':17, 'label': 'I7', 'description': 'Strengthening of public buildings (especially schools) against earthquake', 'applied': solara.reactive(False)},
        '18': {'id':18, 'label': 'I8', 'description': 'Increased financial assistance for people whose apartments are under urban transformation', 'applied': solara.reactive(False)},
        '19': {'id':19, 'label': 'I9', 'description': 'Increased monitoring and supervision of building stock', 'applied': solara.reactive(False)},
        '20': {'id':20, 'label': 'I10', 'description': 'Improvement of infrastructure', 'applied': solara.reactive(False)},
    },
    'implementation_capacity_score': solara.reactive("high"),
    'data_import_method': solara.reactive("drag&drop"),
    'map_info_button': solara.reactive("summary"),
    'map_info_detail': solara.reactive({}),
    'metrics': {
        "metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": 100},
        "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": 100},
        "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": 100},
        "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 100},
        "metric5": {"desc": "Number of households displaced", "value": 0, "max_value": 100},
        "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": 100},
        "metric7": {"desc": "Population displacement", "value": 0, "max_value":100},
        "metric8": {"desc": "Number of casualties", "value": 0, "max_value":100},}})

metric_icon1 = 'tomorrowcities/content/icons/metric1.png'
metric_icon2 = 'tomorrowcities/content/icons/metric2.png'
metric_icon3 = 'tomorrowcities/content/icons/metric3.png'
metric_icon4 = 'tomorrowcities/content/icons/metric4.png'
metric_icon5 = 'tomorrowcities/content/icons/metric5.png'
metric_icon6 = 'tomorrowcities/content/icons/metric6.png'
metric_icon7 = 'tomorrowcities/content/icons/metric7.png'
metric_icon8 = 'tomorrowcities/content/icons/metric8.png'

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
         
def create_metadata(data):
    m = dict()
    m['hazard'] = data['hazard']
    m['infra'] = data['infra']
    m['datetime_analysis'] = data['datetime_analysis']
    m['datetime_upload'] = datetime.datetime.utcnow()
    return m
    
def save_app_state():
    data = clone_app_state(layers.value)
    metadata = create_metadata(data)
    print('metadata', metadata)
    date_string = metadata['datetime_upload'].strftime('%Y%m%d%H%M%S')
    basename = f'TCDSE_SESSION_{date_string}_PKL'
    for ext, var in zip(['data','metadata'],[data,metadata]):
        filename = f'{basename}.{ext}'
        with open(filename, 'wb') as fileObj:
            pickle.dump(var, fileObj)
        if storage.value is not None:
            print('uploading file', filename)
            storage.value.upload_file(filename)
        
def load_app_state():
    with open('app_state.obj', 'rb') as fileObj:
        loaded_state = pickle.load(fileObj)
        load_from_state(loaded_state)

def generic_layer_colors(feature):
    return None

def generic_layer_click_handler(event=None, feature=None, id=None, properties=None):
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def building_colors(feature):
    ds_to_color = {0: 'lavender', 1:'violet',2:'fuchsia',3:'indigo',4:'darkslateblue',5:'black'}
    ds = feature['properties']['ds']
    hospital_access = feature['properties']['hospital_access']
    has_power = feature['properties']['has_power']

    occupancy = feature['properties']['occupancy']
    normal_color = 'green' if occupancy == 'Hea' else 'blue'
    #return {'fillColor': 'black', 'color': 'red' if hospital_access == False else normal_color}
    return {'fillColor': 'black', 'color': 'green' if ds == 0 else 'red'}

def building_click_handler(event=None, feature=None, id=None, properties=None):
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def road_node_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def road_edge_colors(feature):
    is_damaged = feature['properties']['is_damaged'] 
    if feature['properties']['bridge_type'] is not None:
        color = 'black'
    else:
        color = 'blue'
    return {'color': 'red' if is_damaged else color}

def road_edge_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def landuse_click_handler(event=None, feature=None, id=None, properties=None):
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

@solara.memoize(key=lambda feature: (feature['properties']['luf']))
def landuse_colors(feature):
    #print(feature)
    luf_type = feature['properties']['luf']
    if luf_type == 'RESIDENTIAL (HIGH DENSITY)':
        luf_color = {
        'color': 'black',
        'fillColor': '#A0522D', # sienna
        }    
    elif luf_type == 'HISTORICAL PRESERVATION AREA':
        luf_color = {
        'color': 'black',
        'fillColor': '#673147', # plum
        }    
    elif luf_type == 'RESIDENTIAL (MODERATE DENSITY)':
        luf_color = {
        'color': 'black',
        'fillColor': '#cd853f', # peru
        }   
    elif luf_type == 'COMMERCIAL AND RESIDENTIAL':
        luf_color = {
        'color': 'black',
        'fillColor': 'red',
        }   
    elif luf_type == 'CITY CENTER':
        luf_color = {
        'color': 'black',
        'fillColor': '#E6E6FA', # lavender
        }   
    elif luf_type == 'INDUSTRY':
        luf_color = {
        'color': 'black',
        'fillColor': 'grey',
        }   
    elif luf_type == 'RESIDENTIAL (LOW DENSITY)':
        luf_color= {
        'color': 'black',
        'fillColor': '#D2B48C', # tan
        }   
    elif luf_type == 'RESIDENTIAL (GATED NEIGHBORHOOD)':
        luf_color= {
        'color': 'black',
        'fillColor': 'orange',
        }   
    elif luf_type == 'AGRICULTURE':
        luf_color= {
        'color': 'black',
        'fillColor': 'yellow',
        }   
    elif luf_type == 'FOREST':
        luf_color= {
        'color': 'black',
        'fillColor': 'green',
        }   
    elif luf_type == 'VACANT ZONE':
        luf_color = {
        'color': 'black',
        'fillColor': '#90EE90', # lightgreen
        }   
    elif luf_type == 'RECREATION AREA':
        luf_color = {
        'color': 'black',
        'fillColor': '#32CD32', #lime
        }   
    else:
        luf_color = {
        'color': 'black',
        'fillColor': random.choice(['red', 'yellow', 'green', 'orange','blue']),
        } 
    return luf_color

def power_node_colors(feature):
    #print(feature)
    ds_to_color = {0: 'lavender', 1:'violet',2:'fuchsia',3:'indigo',4:'darkslateblue',5:'black'}
    ds = random.randint(0,5) #feature['properties']['ds'] 
    return {'color': ds_to_color[ds], 'fillColor': ds_to_color[ds]}

def create_map_layer(df, name):
    if name == "intensity":
        # Take the largest 500_000 values to display
        im_col = 'pga' if 'pga' in df.columns else 'im'
        df_non_zero = df[df[im_col] > 0]
        df_limited = df_non_zero.sample(min(len(df_non_zero),500_000))
        df_limited[im_col] = df_limited[im_col] / df_limited[im_col].max()
        #df_limited = df.sort_values(by=im_col,ascending=False).head(500_000)
        locs = np.array([df_limited.geometry.y.to_list(), df_limited.geometry.x.to_list(), df_limited[im_col].to_list()]).transpose().tolist()
        map_layer = ipyleaflet.Heatmap(locations=locs, radius = 5, blur = 1, name = name) 
    elif name == "landuse":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '9', 'fillOpacity': 0.5, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 0.5},
            style_callback=landuse_colors)
        map_layer.on_click(landuse_click_handler)   
    elif name == "building":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '9', 'fillOpacity': 0.5, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 0.5},
            style_callback=building_colors)
        map_layer.on_click(building_click_handler)
    elif name == "road edges":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            hover_style={'color': 'orange'},
            style_callback=road_edge_colors)
        map_layer.on_click(road_edge_click_handler)
    elif name == "road nodes":
        df_squares = df.copy()
        half_side = 0.0002
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
            marker_color = 'blue' if node['is_operational'] else 'red'
            icon_name = 'fa-industry' if node['pwr_plant'] == 1 else 'bolt'
            icon_color = 'black'
            marker = Marker(icon=AwesomeIcon(
                        name=icon_name,
                        marker_color=marker_color,
                        icon_color=icon_color,
                        spin=False
                    ),location=(y,x),title=f'{node["node_id"]}',draggable=False)

            markers.append(marker)
        map_layer= ipyleaflet.MarkerCluster(markers=markers, name = name,
                                                   disable_clustering_at_zoom=5)

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

def read_gem_xml(data: [bytes]):
    content_as_string = data.decode('utf-8')
    content_as_string = content_as_string.replace('\n','')
    dom = xml.dom.minidom.parseString(content_as_string)

    def getText(node):
        nodelist = node.childNodes
        rc = []
        for node in nodelist:
            if node.nodeType == node.TEXT_NODE:
                rc.append(node.data)
        return ''.join(rc)

    d = dict()
    node = dom.getElementsByTagName('vulnerabilityModel')[0]
    for i in range(node.attributes.length):
        d[node.attributes.item(i).name] = node.attributes.item(i).value 

    d['description'] = getText(dom.getElementsByTagName('description')[0])

    d['vulnerabilityFunctions'] = []
    for node in dom.getElementsByTagName('vulnerabilityFunction'):
        v = dict()
        for i in range(node.attributes.length):
            v[node.attributes.item(i).name] = node.attributes.item(i).value 
        imls = node.getElementsByTagName('imls')[0]
        v['imt'] = imls.getAttribute('imt')
        v['imls'] = np.fromstring(getText(imls),dtype=float, sep=' ')
        v['meanLRs'] = np.fromstring(getText(node.getElementsByTagName('meanLRs')[0]),dtype=float, sep=' ')
        v['covLRs'] = np.fromstring(getText(node.getElementsByTagName('covLRs')[0]),dtype=float, sep=' ')
        d['vulnerabilityFunctions'].append(v)

    return d

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
def MetricWidget(name, description, value, max_value, render_count):
    value, set_value = solara.use_state_or_update(value)
    max_value, set_max_value = solara.use_state_or_update(max_value)
    options = { 
        "series": [ {
                "type": 'gauge',  
                "min": 0,
                "name": description,
                "max": max(1,max_value), # workaround when max_value = 0
                "startAngle": 180,
                "endAngle": 0,
                "progress": {"show": True, "width": 8},
                "pointer": { "show": False},
                "axisLine": {"lineStyle": {"width": 8}},
                "axisTick": {"show": False},
                "splitLine": {"show": False},            
                "axisLabel": {"show": False},
                "anchor": {"show": False},
                "title": {"show": False},
                "detail": {
                    "valueAnimation": True,
                    "offsetCenter": [0, '-15%'],
                    "fontSize": 14,
                    "color": 'inherit'},
                "title": {"fontSize": 12},
                "data": [{"value": value, "name": name}]}]}
    print(f'value/max_value {value}:{max_value}')

    with solara.Tooltip(description):
        with solara.Column():
            solara.FigureEcharts(option=options, attributes={ "style": "height:100px; width:175px"})

def import_data(fileinfo: solara.components.file_drop.FileInfo):
    data_array = fileinfo['data']
    extension = fileinfo['name'].split('.')[-1]
    if extension == 'xlsx':
        data = pd.read_excel(data_array)
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
            data = pd.read_json(json_string)

    if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
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

@solara.component
def LayerDisplayer():
    print(f'{layers.value["bounds"].value}')
    nonempty_layers = {name: layer for name, layer in layers.value['layers'].items() if layer['data'].value is not None}
    with solara.lab.Tabs(background_color="#ebebeb"):
        for layer_name, layer in nonempty_layers.items():
            with solara.lab.Tab(layer_name):
                data = layer['data'].value
                if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
                    df = layer['df'].value
                    with solara.VBox():
                        if layer_name in ['intensity']:
                            solara.DataFrame(df)
                        else:
                            for filter_col in layer['filter_cols']:
                                solara.CrossFilterSelect(df, filter_col)
                            solara.CrossFilterDataFrame(df)
                    if layer_name in ["building","road edges","road nodes","power nodes","power edges"] :
                        with solara.Row():
                            file_object = data.to_json()
                            with solara.FileDownload(file_object, f"{layer_name}_export.geojson", mime_type="application/geo+json"):
                                solara.Button("Download GeoJSON", icon_name="mdi-cloud-download-outline", color="primary")
                            with solara.FileDownload(data.to_csv(), f"{layer_name}_export.csv", mime_type="text/csv"):
                                solara.Button("Download CSV", icon_name="mdi-cloud-download-outline", color="primary")
                elif isinstance(data, ParameterFile):
                    ParameterFileWidget(parameter_file=data)
                if layer_name == 'gem_vulnerability':
                    VulnerabiliyDisplayer(data)

@solara.component
def MetricPanel():
    building = layers.value['layers']['building']['data'].value
    filtered_metrics = {name: 0 for name in layers.value['metrics'].keys()}
    if building is not None and layers.value['bounds'].value is not None:
        ((ymin,xmin),(ymax,xmax)) = layers.value['bounds'].value
        filtered = building.cx[xmin:xmax,ymin:ymax]
        for metric in filtered_metrics.keys():
            filtered_metrics[metric] = int(filtered.cx[xmin:xmax,ymin:ymax][metric].sum())

    metric_icons = [metric_icon1,metric_icon2,metric_icon3,metric_icon4,metric_icon5,metric_icon6,metric_icon7,metric_icon8]
    with solara.Row():                     
        for i in range(len(metric_icons)):
            solara.Image(metric_icons[i])
    
    with solara.Row():
        for name, metric in layers.value['metrics'].items():
            MetricWidget(name, metric['desc'], 
                         filtered_metrics[name], 
                         metric['max_value'],
                         layers.value['render_count'].value)
        # with solara.Link("/docs/metrics"):
            # solara.Button(icon_name="mdi-help-circle-outline", icon=True)
                    
@solara.component
def MapViewer():
    print('rendering mapviewer')
    default_zoom = 14
    zoom, set_zoom = solara.use_state(default_zoom)
    base_layers, set_base_layers = solara.use_state_or_update([])
    map_layers, set_map_layers = solara.use_state_or_update([])

    def create_base_layers():
        base_layer1 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.OpenStreetMap.Mapnik.build_url(),name="OpenStreetMap",base = True)
        base_layer2 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.Esri.WorldStreetMap.build_url(),name="Esri WorldStreetMap",base = True)
        base_layer3 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.OpenTopoMap.build_url(),name="OpenTopoMap",base = True)
        base_layer4 = ipyleaflet.TileLayer.element(url=ipyleaflet.basemaps.CartoDB.Positron.build_url(),name="CartoDB",base = True)                                                                                                                                         
        set_base_layers([base_layer4, base_layer3, base_layer2, base_layer1])

    # create base layers only once
    solara.use_memo(create_base_layers,[])
    
    layout = ipywidgets.Layout.element(width='100%', height='55vh')

    tool1 = ipyleaflet.ZoomControl.element(position='topleft')
    tool2 = ipyleaflet.FullScreenControl.element(position='topleft')    
    tool3 = ipyleaflet.LayersControl.element(position='topright')
    tool4 = ipyleaflet.ScaleControl.element(position='bottomleft')                                                                                                                                              

    filters = dict()
    for l in layers.value['layers'].keys():
        filters[l], _ = solara.use_cross_filter(id(layers.value['layers'][l]['df'].value), "dataframe")

    def create_layers():
        map_layers = []
        for l in layers.value['layers'].keys():
            df = layers.value['layers'][l]['data'].value
            if df is not None and 'geometry' in df.columns:
                if filters[l] is not None:
                    map_layer = create_map_layer(df[filters[l]], l)
                else:
                    map_layer = create_map_layer(df, l)
                map_layers.append(map_layer)

        set_map_layers(map_layers)

    solara.use_memo(create_layers,[f for f in filters.values()] + [layers.value['layers'][l]['data'].value for l in layers.value['layers'].keys()])  

    ipyleaflet.Map.element(
        zoom=zoom,
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
        controls = [tool1, tool2, tool3, tool4],
        layout = layout
        )
        
@solara.component
def ExecutePanel(): 

    progress_message, set_progress_message = solara.use_state("")
    execute_counter, set_execute_counter = solara.use_state(0)
    execute_btn_disabled, set_execute_btn_disabled = solara.use_state(False)
    execute_error = solara.reactive("")

    def on_click():
        set_execute_counter(execute_counter + 1)
        execute_error.set("")

    def is_ready_to_run(infra, hazard):
        existing_layers = set([name for name, l in layers.value['layers'].items() if l['data'].value is not None])
        missing = []

        if hazard == "earthquake":
            if "power" in  infra:
                missing += list(set(["building","household","individual","power edges","power nodes","intensity","power fragility"]) - existing_layers)
            if "road" in  infra:
                missing += list(set(["building","household","individual","road edges","road nodes","intensity","road fragility"]) - existing_layers)
            if "building" in infra:
                missing += list(set(["landuse","building","household","individual","intensity","fragility"]) - existing_layers)
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

        missing_buildings = set(household['bldid']) - set(building['bldid'])
        print('missing buildings', missing_buildings)
        if len(missing_buildings) > 0:
            return False, f"There are {len(missing_buildings)} household without buildings. Please add buildings for these households."
        
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
            if layers.value['hazard'].value == 'landslide':
                fragility = layers.value['layers']['landslide fragility']['data'].value
                trigger_level= layers.value['landslide_trigger_level'].value
                fragility = fragility[['expstr','susceptibility',trigger_level]].rename(columns={trigger_level:'collapse_probability'})
            hazard = layers.value['hazard'].value

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
                threshold_flood_distance.value,
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
                                    hazard, threshold_flood.value, threshold_flood_distance.value)
            
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

            policies = [p['id'] for _, p in layers.value['policies'].items() if f"{p['label']}/{p['description']}" in layers.value['selected_policies'].value]

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
                    threshold_flood = threshold_flood.value,
                    threshold_flood_distance = threshold_flood_distance.value)
            else:
                df_bld_hazard = compute(
                    landuse,
                    buildings,
                    household,
                    individual,
                    intensity,
                    fragility if layers.value['hazard'].value == "earthquake" else vulnerability,
                    layers.value['hazard'].value, policies=policies,
                    threshold_flood = threshold_flood.value,
                    threshold_flood_distance = threshold_flood_distance.value)
            buildings['ds'] = list(df_bld_hazard['ds'])
            buildings['casualty'] = list(df_bld_hazard['casualty'])

            return buildings

        def execute_metric():
            buildings = layers.value['layers']['building']['data'].value
            household = layers.value['layers']['household']['data'].value
            individual = layers.value['layers']['individual']['data'].value
            policies = [p['id'] for _, p in layers.value['policies'].items() if f"{p['label']}/{p['description']}" in layers.value['selected_policies'].value]

            implementation_capacity_score = layers.value['implementation_capacity_score'].value
            if implementation_capacity_score == 'medium':
                capacity = 1.25
            elif implementation_capacity_score == 'low':
                capacity = 1.50
            else:
                capacity = 1
            computed_metrics, df_metrics = calculate_metrics(buildings, household, 
                                                             individual, layers.value['infra'].value,
                                                             layers.value['hazard'].value, policies=policies,capacity=capacity)
            print(computed_metrics)
            for metric in df_metrics.keys():
                buildings[metric] = list(df_metrics[metric][metric])
                layers.value['metrics'][metric]['value'] = computed_metrics[metric]['value']
                layers.value['metrics'][metric]['max_value'] = computed_metrics[metric]['max_value']
            return buildings

        if execute_counter > 0 :
            is_ready, missing = is_ready_to_run(layers.value['infra'].value, layers.value['hazard'].value)
            if not is_ready:
                raise Exception(f'Missing {missing}')
            #is_ready, message = pre_compute_checks()
            #if not is_ready:
            #    raise Exception(message)
            max_trials = landslide_max_trials.value  if layers.value['hazard'].value == "landslide" else 1
            for trial in range(1,max_trials+1):
                if trial == 1:
                    set_progress_message('Running...')
                else:
                    set_progress_message(f'Monte-Carlo trial {trial}/{max_trials}...')
                if 'power' in layers.value['infra'].value:
                    nodes, buildings, household = execute_power()
                    layers.value['layers']['power nodes']['data'].set(nodes)
                    layers.value['layers']['building']['data'].set(buildings)
                    layers.value['layers']['household']['data'].set(household)
                    layers.value['layers']['power nodes']['df'].set(nodes.drop(columns=['geometry']))
                    layers.value['layers']['building']['df'].set(buildings.drop(columns=['geometry']))
                    layers.value['layers']['household']['df'].set(household)
                if 'road' in layers.value['infra'].value:
                    edges, buildings, household, individual = execute_road()
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
                    layers.value['layers']['building']['data'].set(buildings)
                    layers.value['layers']['building']['df'].set(buildings.drop(columns=['geometry']))

                buildings = execute_metric()
                layers.value['layers']['building']['data'].set(buildings)
                layers.value['layers']['building']['df'].set(buildings.drop(columns=['geometry']))

                # Taking average without storing intermediate values
                # averaga_n = [(n-1)*average_(n-1) + value_n]/2
                if trial == 1:
                    avg_metrics = buildings[layers.value['metrics'].keys()]
                else:
                    avg_metrics = ((trial-1) * avg_metrics + buildings[layers.value['metrics'].keys()])/trial
                for metric in layers.value['metrics'].keys():
                    print('average', metric, avg_metrics[metric].sum())

            for metric in layers.value['metrics'].keys():
                buildings[metric] = list(avg_metrics[metric])
                layers.value['metrics'][metric]['value'] = avg_metrics[metric].sum()
            set_progress_message('')
            # trigger render event
            layers.value['render_count'].set(layers.value['render_count'].value + 1)

            layers.value['datetime_analysis'] =  datetime.datetime.utcnow()

    # Execute the thread only when the depencency is changed
    result = solara.use_thread(execute_engine, dependencies=[execute_counter], intrusive_cancel=False)

    with solara.GridFixed(columns=1):
        solara.Markdown("#### Infrastructure")
        with solara.Row(justify="left"):
            solara.ToggleButtonsMultiple(value=layers.value['infra'].value, on_value=layers.value['infra'].set, values=["building","power","road"])
        solara.Markdown("#### Hazard")
        with solara.Row(justify="left"):
            solara.ToggleButtonsSingle(value=layers.value['hazard'].value, on_value=layers.value['hazard'].set, values=layers.value['hazard_list'])
        if layers.value['hazard'].value == 'landslide':
            solara.Markdown("#### Landslide trigger level")
            with solara.Row(justify="left"):
                solara.ToggleButtonsSingle(value=layers.value['landslide_trigger_level'].value,
                    on_value=layers.value['landslide_trigger_level'].set,
                    values=layers.value['landslide_trigger_level_list'])
        with solara.Tooltip("Building-level metrics will be increased by 25% and 50% for medium and low"):
            solara.Markdown("#### Implementation Capacity Score")
        with solara.Row(justify="left"):
            solara.ToggleButtonsSingle(value=layers.value['implementation_capacity_score'].value, 
                                values=['low','medium','high'],
                                on_value=layers.value['implementation_capacity_score'].set,
                                )
    
    solara.ProgressLinear(value=False)
    solara.Button("Calculate", on_click=on_click, outlined=True,
                disabled=execute_btn_disabled)
    if storage.value is not None:
        solara.Button("Save Session",on_click=save_app_state)
    PolicyPanel()
    # The statements in this block are passed several times during thread execution
    if result.error is not None:
        execute_error.set(execute_error.value + str(result.error))

    if execute_error.value != "":
        solara.Text(f'{execute_error}', style={"color":"red"})
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
def PolicyPanel():
    all_policies = [f"{p['label']}/{p['description']}" for _, p in layers.value['policies'].items()]
    with solara.Row():
        solara.SelectMultiple("Policies", layers.value['selected_policies'].value, all_policies, on_value=layers.value['selected_policies'].set, dense=False, style={"max-width": "30vh", "height": "auto"})

@solara.component
def MapInfo():
    print(f'{layers.value["bounds"].value}')
    version = layers.value["version"]
    print(layers.value['map_info_button'].value)
    with solara.Row(justify="center"):
        solara.Markdown(f'Engine [v{version}](https://github.com/TomorrowsCities/tomorrowcities/releases/tag/v{version})')
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
    else:
        with solara.GridFixed(columns=2,row_gap="1px"):
            for key, value in layers.value['map_info_detail'].value.items():
                if key == 'style':
                    continue
                solara.Text(f'{key}')
                with solara.Row(justify="right"):
                    strvalue = str(value)
                    if len(strvalue) > 10:
                        with solara.Tooltip(f'{value}'):
                            solara.Text(f'{strvalue[:10]}...')
                    else:
                        solara.Text(f'{value}')

@solara.component
def ImportDataZone():
    def s3_file_open(p):
        #print(p)
        storage.value.s3.download_file(storage.value.bucket_name, str(p)[1:], f'/tmp/aws.tmp')

        with open(f'/tmp/aws.tmp', 'rb') as fileObj:
            fileContent = fileObj.read()
            file_info = solara.components.file_drop.FileInfo(name=os.path.basename(p), 
                                                             size=len(fileContent),
                                                             data=fileContent)
            set_fileinfo(file_info)

    def local_file_open(p):
        with open(p, 'rb') as fileObj:
            fileContent = fileObj.read()
            file_info = solara.components.file_drop.FileInfo(name=os.path.basename(p), 
                                                             size=len(fileContent),
                                                             data=fileContent)
            set_fileinfo(file_info)

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
                        layers.value['layers'][name]['df'].set(data.drop(columns=['geometry']))
                        layers.value['layers'][name]['data'].set(data)
                        updated_center = (data.geometry.centroid.y.mean(), data.geometry.centroid.x.mean())
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
                return False
        return True
    
    def is_ready_to_generate():
        if layers.value['layers']['parameter']['data'].value is not None and \
           layers.value['layers']['landuse']['data'].value is not None:
            return True
        return False

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
                print(data)
                layers.value['layers'][name]['data'].set(data)
                if  "geometry" in list(data.columns):
                    center = (data.geometry.centroid.y.mean(), data.geometry.centroid.x.mean())
                    layers.value['center'].set(center)

        
    def progress(x):
        set_total_progress(x)

    def on_file_deneme(f):
        set_fileinfo(f)
    
    result = solara.use_thread(load, dependencies=[fileinfo], intrusive_cancel=False)
    generate_result = solara.use_thread(generate, dependencies=[generate_counter], intrusive_cancel=False)

    #with solara.Row(justify="center"):
    #    solara.ToggleButtonsSingle(value=layers.value['data_import_method'].value, 
    #                            on_value=layers.value['data_import_method'].set, 
    #                            values=["drag&drop","s3"], 
    #                            style={"align-items": "center"})
    with solara.Card(title="Upload", subtitle="Drag & Drop from your local drive"):
        solara.Markdown('''Drag & drop your local files to 
                        the below area. Supported formats are Excel, GeoTIFF, JSON, GeoJSON, and GEM XML.
                        For more information, please refer to [Data Formats](/docs/data).
                        ''')
        FileDropMultiple(on_total_progress=progress,
                on_file=on_file_deneme, 
                lazy=False)
        
    with solara.Card(title="Data Generation", subtitle="Exposure generation"):
        solara.Markdown('''First, upload parameter file and land use, then click
                        generate to produce building/household/individual layers
                        ''')
        with solara.Row():
            solara.InputInt(label='Random seed',value=layers.value['seed'])
            solara.Button("Generate", on_click=on_generate, outlined=True,
                disabled=generate_btn_disabled)

    if generate_result.error is not None:
        generate_error.set(generate_error.value + str(generate_result.error))

    if generate_error.value != "":
        solara.Text(f'{generate_error}', style={"color":"red"})
    else:
        solara.Text("Spacer", style={"visibility": "hidden"})

    if generate_result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
        set_generate_btn_disabled(True)
        solara.Text(generate_message)
        solara.ProgressLinear(value=True)
    else:
        solara.Text("Spacer", style={"visibility": "hidden"})
        set_generate_btn_disabled(not is_ready_to_generate())
        solara.ProgressLinear(value=False)
    with solara.Card(title="Sample Dataset", subtitle="Use our sample data"): 
        if storage.value is None:
            solara.Markdown('''
                            You can download and extract our
                            [Sample Dataset](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view?usp=sharing)
                            to your local drive and upload to the platform via drag & drop''')
        else:
            solara.Markdown('''You can choose sample data from our AWS S3 repository. 
                            Double click to load data into the platform.
                        ''')   
            S3FileBrowser(storage.value, "tcdse", can_select=True, on_file_open=s3_file_open, start_directory='/datastore')

    #with solara.Card(title="Browse", subtitle="Import from your local drive"):
    #    solara.Markdown('''Locate the input files in your drive, and double click
    #                    the file that you want to upload.
    #                    ''')    
    #    solara.FileBrowser(can_select=True, on_file_open=local_file_open,
    #        filter=lambda p: True if p.is_dir() or p.suffix in extension_list_w_dots else False)

    if total_progress > -1 and total_progress < 100:
        solara.Text(f"Uploading {total_progress}%")
        solara.ProgressLinear(value=total_progress)
    else:
        if result.state == solara.ResultState.FINISHED:
            if result.value:
                solara.Text("Spacer", style={'visibility':'hidden'})
            else:
                solara.Text("Unrecognized file")
            solara.ProgressLinear(value=False)
        elif result.state == solara.ResultState.INITIAL:
            solara.Text("Spacer", style={'visibility':'hidden'})
            solara.ProgressLinear(value=False)
        elif result.state == solara.ResultState.ERROR:
            solara.Text(f'{result.error}')
            solara.ProgressLinear(value=False)
        else:
            solara.Text("Processing")
            solara.ProgressLinear(value=True)
            
@solara.component
def WebApp():
    if storage.value is None:
        storage.value = revive_storage()
    solara.Title(" ")
    with solara.Sidebar():
        with solara.lab.Tabs():
            with solara.lab.Tab("SETTINGS"):
                ExecutePanel()
            with solara.lab.Tab("DATA IMPORT"):
                ImportDataZone()
            with solara.lab.Tab("MAP INFO"):
                MapInfo()

    # LayerController()
    MapViewer()
    with solara.Row(justify="center"):
        MetricPanel()
    LayerDisplayer()

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
    .v-application {
        line-height: 1;
    }
    .v-input {
        height: 10px;
    }

    .v-btn-toggle:not(.v-btn-toggle--dense) .v-btn.v-btn.v-size--default {
        height: 24px;
        min-height: 0;
        min-width: 24px;
    }

    .leaflet-container {
        z-index: 1;
    }

    .v-tabs-bar {
        height: 36px;
    }
    """
    solara.Style(value=css)
    solara.Title(" ")

    WebApp()