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
from solara.lab import task
import secrets

from . import storage, connect_storage
from ..backend.utils import building_preprocess, identity_preprocess, ParameterFile
from .engine import landuse_colors, generic_layer_colors, building_colors, road_edge_colors
from .engine import MetricWidget, create_new_app_state
from ..backend.engine import generate_metrics
from .settings import population_displacement_consensus

def get_session_list():
    if storage.value is not None:
        return sorted(storage.value.list_sessions(),reverse=True)
    return None

session_name = solara.reactive(None)
session_list = solara.reactive(get_session_list())
status_text = solara.reactive("")
selected_tab = solara.reactive(None)
render_count = solara.reactive(0)
zoom = solara.reactive(14)
tally_filter = solara.reactive(None)
building_filter = solara.reactive(None)
landuse_filter = solara.reactive(None)

layers = create_new_app_state()

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
    if storage.value is None:
        revived_storage = connect_storage()
        if revive_storage is None:
            status_text.value = "Couldn't connect to datastore"
        else:
            storage.value = revived_storage
            status_text.value = "Connection to S3 is OK!"
    else:
        status_text.value = "No storage configuration!"   



def refresh_session_list():
    sess_list = get_session_list()
    if sess_list is not None:
        session_list.set(sess_list)
        status_text.value = ""
    else:
        session_list.set([])
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

@task
def load_session():

    #print('loading', session_name.value)
    storage.value.get_client().download_file(storage.value.bucket_name, session_name.value + '.data', f'session.data')
    storage.value.get_client().download_file(storage.value.bucket_name, session_name.value + '.metadata', f'session.metadata')

    load_app_state()
    post_processing_after_load()
    force_render()

def fetch_metadata(session_name):
    storage.value.get_client().download_file(storage.value.bucket_name, session_name + '.metadata', f'session.metadata')
    with open('session.metadata', 'rb') as fileObj:
        print('Opening session.metadata...')
        metadata = pickle.load(fileObj)
        return metadata

@solara.component
def MetaDataViewer(session_name):
    session_name, _ = solara.use_state_or_update(session_name.value)
    if session_name is not None:
        metadata = fetch_metadata(session_name)

        with solara.GridFixed(columns=2,row_gap="1px"):
            for key,value in metadata.items():

                solara.Text(f'{key}')
                with solara.Row(justify="right"):
                    if value is None:
                        solara.Text('None')
                    else:
                        solara.Text(f'{value}')
        print(metadata)

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
        solara.Button(style={"width":"48%","margin":"1%"},label="Refresh List", on_click=lambda: refresh_session_list(),
                      disabled = True if storage.value is None else False)
        solara.Button(style={"width":"48%","margin":"1%"},label="Revive Storage", on_click=lambda: revive_storage())
        solara.Button(style={"width":"48%","margin":"1%"},label="Load session", on_click = load_session, 
                      disabled=True if session_name.value is None else False)
        solara.Button(style={"width":"48%","margin":"1%"},label='Clear Session', on_click=lambda: clear_session())
    solara.ProgressLinear(load_session.pending)
    solara.Text(text=status_text.value)
    MetaDataViewer(session_name)

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
    tool3 = ipyleaflet.LayersControl.element(position='topright', collapsed=False)
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
            if df is not None and isinstance(df, gpd.GeoDataFrame):
                map_layer_dict[l] = create_map_layer(df, l)
        set_map_layers(map_layer_dict)

    solara.use_memo(create_layers, [layer['df'].value for name, layer in layers.value['layers'].items()])
    solara.use_memo(update_building_layer, [building_filter, layers.value['layers']['building']['df'].value])

    ipyleaflet.Map.element(
        zoom=zoom.value,
        max_zoom=23,        
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

metric_update_pending = solara.reactive(False)


@task
def generate_metrics_local():
    metric_update_pending.set(True)
    print("Emtering generate_metrics_local")
    metrics = {name: {'value':0, 'max_value':0, 'desc': metric['desc']} for name, metric in layers.value['metrics'].items()}

    tally = layers.value['tally'].value
    tally_geo = layers.value['tally_geo'].value
    if tally_geo is not None and layers.value['bounds'].value is not None:
        ((ymin,xmin),(ymax,xmax)) = layers.value['bounds'].value
        tally_filtered = tally_geo.cx[xmin:xmax,ymin:ymax]
        if tally_filter.value is not None:
            tally_filtered = tally_filtered[tally_filter.value]
        hazard_type = layers.value['hazard'].value
        print('Triggering generate_metrics')
        metrics = generate_metrics(tally_filtered, tally_geo, hazard_type, population_displacement_consensus.value)
        print('metrics', metrics)
    metric_update_pending.set(False)
    return metrics

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
    filtered_metrics = {name: {'value':0, 'max_value':0, 'desc': metric['desc']} for name, metric in layers.value['metrics'].items()}
    solara.use_memo(generate_metrics_local, 
                    [layers.value['tally_geo'].value,
                     layers.value['bounds'].value,
                     tally_filter.value], debug_name="generate_metrics_loca")
    if generate_metrics_local.finished:
        filtered_metrics = generate_metrics_local.value

    metric_icons = [metric_icon1,metric_icon2,metric_icon3,metric_icon4,metric_icon5,metric_icon6,metric_icon7,metric_icon8]
    with solara.Row(justify="space-around"):
        solara.Markdown('''<h2 style="font-weight: bold">IMPACTS</h2>''')
    solara.ProgressLinear(metric_update_pending.value)
    with solara.Row(justify="space-around"):                     
        for i in range(len(metric_icons)):
            solara.Image(metric_icons[i])
    
    with solara.Row(justify="space-around"):
        for name, metric in filtered_metrics.items():
            MetricWidget(name, metric['desc'], 
                        metric['value'],
                        metric['max_value'],
                        layers.value['render_count'].value)

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
    solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Damage State Filter</h4>''')
    if layers.value['layers']['building']['df'].value is not None:
        solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        for filter_col in ['ds']:
            solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     filter_col)  
    else:
        solara.Info('No data to filter')
    print(f"fiter panel render count {render_count.value}")

    solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Income Level Filter</h4>''')
    if layers.value['layers']['building']['df'].value is not None:
        solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        for filter_col in ['freqincome']:
            solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     filter_col)  
    else:
        solara.Info('No data to filter')
    print(f"fiter panel render count {render_count.value}")

    # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Load Resisting System Filter</h4>''')
    # if layers.value['layers']['building']['df'].value is not None:
        # solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        # for filter_col in ['lrstype']:
            # solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     # filter_col)  
    # else:
        # solara.Info('No data to filter')
    # print(f"fiter panel render count {render_count.value}")
    
    # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Code Level Filter</h4>''')
    # if layers.value['layers']['building']['df'].value is not None:
        # solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        # for filter_col in ['codelevel']:
            # solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     # filter_col)  
    # else:
        # solara.Info('No data to filter')
    # print(f"fiter panel render count {render_count.value}")
    
    # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Height Filter</h4>''')
    # if layers.value['layers']['building']['df'].value is not None:
        # solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        # for filter_col in ['nstoreys']:
            # solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     # filter_col)  
    # else:
        # solara.Info('No data to filter')
    # print(f"fiter panel render count {render_count.value}")

    # solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Occupation Type Filter</h4>''')
    # if layers.value['layers']['building']['df'].value is not None:
        # solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        # for filter_col in ['occbld']:
            # solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     # filter_col)  
    # else:
        # solara.Info('No data to filter')
    # print(f"fiter panel render count {render_count.value}")

    solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Special Facility Filter</h4>''')
    if layers.value['layers']['building']['df'].value is not None:
        solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        for filter_col in ['specialfac']:
            solara.CrossFilterSelect(layers.value['layers']['building']['df'].value, 
                                     filter_col)  
    else:
        solara.Info('No data to filter')
    print(f"fiter panel render count {render_count.value}")
    
    solara.Markdown('''<h4 style="text-align: left; text-decoration:underline">Polygon (ZoneID) Filter</h4>''')
    if layers.value['layers']['building']['df'].value is not None:
        solara.CrossFilterReport(layers.value['layers']['building']['df'].value, classes=["py-2"])
        for filter_col in ['zoneid']:
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
            with solara.lab.Tab("FILTERS"):              
                FilterPanel()
        #solara.Text(f'Selected tab {selected_tab}')
      
    MapViewer()
    with solara.Row(justify="center"):
        MetricPanel()