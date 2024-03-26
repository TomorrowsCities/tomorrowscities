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
import pickle
import datetime
import ipywidgets
import ipydatagrid

from . import S3Storage
from ..backend.utils import building_preprocess, identity_preprocess, ParameterFile
from .engine import landuse_colors, generic_layer_colors, building_colors, road_edge_colors
from .engine import MetricWidget

storage = solara.reactive(None)  
session_name = solara.reactive(None)
session_list = solara.reactive([])
status_text = solara.reactive("")
selected_tab = solara.reactive(None)
render_count = solara.reactive(0)
zoom = solara.reactive(14)

def create_new_app_state():
    return {
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
            'filter_cols': ['occbld','specialfac'], # TODO: cols exist only after analysis
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
        "metric8": {"desc": "Number of casualties", "value": 0, "max_value":100},}}

layers = solara.reactive(create_new_app_state())

def create_map_layer(df, name):
    if name == "intensity":
        # Take the largest 500_000 values to display
        im_col = 'pga' if 'pga' in df.columns else 'im'
        df_non_zero = df[df[im_col] > 0]
        df_limited = df_non_zero.sample(min(len(df_non_zero),500_000))
        df_limited[im_col] = df_limited[im_col] / df_limited[im_col].max()
        #df_limited = df.sort_values(by=im_col,ascending=False).head(500_000)
        locs = np.array([df_limited.geometry.y.to_list(), df_limited.geometry.x.to_list(), df_limited[im_col].to_list()]).transpose().tolist()
        map_layer = ipyleaflet.Heatmap(locations=locs, radius = 3, blur = 2, name = name) 
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

def road_node_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def road_edge_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def landuse_click_handler(event=None, feature=None, id=None, properties=None):
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def building_click_handler(event=None, feature=None, id=None, properties=None):
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def generic_layer_click_handler(event=None, feature=None, id=None, properties=None):
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def road_edge_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def revive_storage():
    if 'aws_access_key_id' in os.environ:
        print('reviving storage from env')
        revived_storage = S3Storage(
                    os.environ['aws_access_key_id'],
                    os.environ['aws_secret_access_key'],
                    os.environ['region_name'],
                    os.environ['bucket_name'])
        if revive_storage is None:
            status_text.value = "Couldn't connect to datastore"
        else:
            storage.value = revived_storage
            status_text.value = "Connection to S3 is OK!"
    else:
        status_text.value = "No storage configuration!"
        

def refresh_session_list():
    if storage.value is not None:
        print('++++++++++++++',storage.value,'+++++++++')
        session_list.set(sorted(storage.value.list_sessions(),reverse=True))
        status_text.value = ""
    else:
        storage.value = revive_storage()
        status_text.value = "no connections to AWS"


def assign_nested_value(dictionary, keys, value):
    for key in keys[:-1]:
        dictionary = dictionary.setdefault(key, {})
    dictionary[keys[-1]] = value

def get_nested_value(dictionary, keys):
    for key in keys[:-1]:
        dictionary = dictionary[key]
    return dictionary[keys[-1]]

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

def load_app_state():

    with open('session.data', 'rb') as fileObj:
        print('Opening session.data...')
        loaded_state = pickle.load(fileObj)
        #layers.set(loaded_state)
        load_from_state(loaded_state)
    with open('session.metadata', 'rb') as fileObj:
        print('Opening session.metadata...')
        loaded_state = pickle.load(fileObj)
        #print(loaded_state)

def post_processing_after_load():
    # DF : no geometry
    building_df = layers.value['layers']['building']['df'].value 
    landuse_df = layers.value['layers']['landuse']['df'].value 
    if building_df is not None and landuse_df is not None:
        building_df = building_df.merge(landuse_df[['zoneid','avgincome']],on='zoneid',how='left')
        layers.value['layers']['building']['df'].set(building_df) 

    # data: geometry
    building_data = layers.value['layers']['building']['data'].value 
    landuse_data = layers.value['layers']['landuse']['data'].value 
    if building_data is not None and landuse_data is not None:
        building_data = building_data.merge(landuse_data[['zoneid','avgincome']],on='zoneid',how='left')
        layers.value['layers']['building']['data'].set(building_data) 

def load_session():

    #print('loading', session_name.value)
    storage.value.get_client().download_file(storage.value.bucket_name, session_name.value + '.data', f'session.data')
    storage.value.get_client().download_file(storage.value.bucket_name, session_name.value + '.metadata', f'session.metadata')

    load_app_state()
    post_processing_after_load()
    force_render()

def clear_session():
    layers.value = create_new_app_state()
    force_render()

def force_render():
    render_count.set(render_count.value + 1)

@solara.component
def StorageViewer():
    with solara.Card(title='Load Session', subtitle='Choose a session from storage'):
        solara.Select(label='Choose session',value=session_name.value, values=session_list.value,
                    on_value=session_name.set)
        solara.Button(label="Refresh List", on_click=lambda: refresh_session_list(),
                      disabled = True if storage.value is None else False)
        solara.Button(label="Revive Storage", on_click=lambda: revive_storage())
        solara.Button(label="Load session", on_click = lambda: load_session(), 
                      disabled=True if session_name.value is None else False)
        solara.Button(label='Clear Session', on_click=lambda: clear_session())
    solara.Text(text=status_text.value)


@solara.component
def MapViewer():
    print('rendering mapviewer')
    base_layers, set_base_layers = solara.use_state_or_update([])
    map_layers, set_map_layers = solara.use_state_or_update({})
    building_layer, set_building_layer = solara.use_state([])

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


    building_filter, _ = solara.use_cross_filter(id(layers.value['layers']['building']['df'].value), "building")


    #filters = dict()
    #for l in layers.value['layers'].keys():
        #print(l, type(layers.value['layers'][l]['df']), id(None))
        #print(layers.value['layers'])

        #filters[l], _ = solara.use_cross_filter(id(layers.value['layers'][l]['df'].value), "dataframe")
        #filters[l], _ = solara.use_cross_filter(id(None), "dataframe")


    def update_building_layer():
        print('update buildings')
        df = layers.value['layers']['building']['data'].value
        if df is None:
            set_building_layer([])
        else:
            set_building_layer([create_map_layer(df, 'building')])
            if building_filter is None:
                print('filter is none')
                set_building_layer([create_map_layer(df, 'building')])
            else:
                print(len(df[building_filter]))
                set_building_layer([create_map_layer(df[building_filter], 'building')])
        

    def create_layers():
        map_layer_dict = {}
        for l in layers.value['layers'].keys():
            if l == 'building':
                continue
            df = layers.value['layers'][l]['data'].value
            if df is not None:
                map_layer_dict[l] = create_map_layer(df, l)
        set_map_layers(map_layer_dict)

    solara.use_memo(create_layers, [layer['df'].value for name, layer in layers.value['layers'].items()])
    solara.use_memo(update_building_layer, [building_filter, layers.value['layers']['building']['df'].value])


    ipyleaflet.Map.element(
        zoom=zoom.value,
        on_zoom=zoom.set,
        on_bounds=layers.value['bounds'].set,
        center=layers.value['center'].value,
        on_center=layers.value['center'].set,
        scroll_wheel_zoom=True,
        dragging=True,
        double_click_zoom=True,
        touch_zoom=True,
        box_zoom=True,
        keyboard=True if random.random() > 0.5 else False,
        layers=base_layers + list(map_layers.values()) + building_layer,
        controls = [tool1, tool2, tool3, tool4],
        layout = layout
        )
    print(f"render count {render_count.value}")
    
@solara.component
def MetricPanel():
    metric_icon1 = 'tomorrowcities/content/icons/metric1.png'
    metric_icon2 = 'tomorrowcities/content/icons/metric2.png'
    metric_icon3 = 'tomorrowcities/content/icons/metric3.png'
    metric_icon4 = 'tomorrowcities/content/icons/metric4.png'
    metric_icon5 = 'tomorrowcities/content/icons/metric5.png'
    metric_icon6 = 'tomorrowcities/content/icons/metric6.png'
    metric_icon7 = 'tomorrowcities/content/icons/metric7.png'
    metric_icon8 = 'tomorrowcities/content/icons/metric8.png'
    solara.Markdown('''<h2 style="text-align: center; text-shadow: 2px 2px 10px; font-weight: bold">
                        &nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp
                        &nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp
                        &nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp
                        &nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp
                        &nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp
                        IMPACTS</h2>''')
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
                         render_count.value)
        # with solara.Link("/docs/metrics"):
            # solara.Button(icon_name="mdi-help-circle-outline", icon=True)
    print(f"render count {render_count.value}")

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
def FilterPanel():
    solara.Markdown('''<h2 style="text-align: left; text-shadow: 2px 2px 5px #1c4220; text-decoration:underline">FILTERS</h2>''')
    if layers.value['layers']['building']['df'].value is not None:
        solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        for filter_col in ['ds']:
            solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     filter_col)  
    else:
        solara.Info('No data to filter')
    print(f"fiter panel render count {render_count.value}")
 

@solara.component
def Page():    
    with solara.Sidebar():
        with solara.lab.Tabs(value=selected_tab.value, on_value=selected_tab.set):
            with solara.lab.Tab("SESSIONS"):
                StorageViewer()
            with solara.lab.Tab("MAP INFO"):
                MapInfo()
        FilterPanel()
        solara.Text(f'Selected tab {selected_tab}')

      
    MapViewer()
    MetricPanel()
      
      