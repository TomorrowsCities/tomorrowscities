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
import tempfile

from . import storage, connect_storage, read_from_session_storage, store_in_session_storage
from ..backend.utils import building_preprocess, identity_preprocess, ParameterFile
from .engine import landuse_colors, generic_layer_colors, building_colors, road_edge_colors,\
                    power_edge_colors, ds_to_color, ds_to_color_approx, create_tally
from .engine import MetricWidget, create_new_app_state
from ..backend.engine import generate_metrics

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
tally_counter = solara.reactive(0)
tally_filter = solara.reactive(None)
building_filter = solara.reactive(None)
landuse_filter = solara.reactive(None)
population_displacement_consensus = solara.reactive(2)

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
            style={'opacity': 1, 'dashArray': '0', 'fillOpacity': 1, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 1},
            style_callback=landuse_colors)
        map_layer.on_click(landuse_click_handler)   
    elif name == "building":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '0', 'fillOpacity': 1, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 1},
            style_callback=building_colors)
        map_layer.on_click(building_click_handler)
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
            marker_color = ds_to_color_approx[node['ds']]
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

def road_node_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def road_edge_click_handler(event=None, feature=None, id=None, properties=None):
    #print(properties)
    layers.value['map_info_detail'].set(properties)
    layers.value['map_info_button'].set("detail")  

def power_edge_click_handler(event=None, feature=None, id=None, properties=None):
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
    if keys[-1] in dictionary.keys():
        is_available = True
        return (dictionary[keys[-1]], is_available)
    else:
        is_available = False
        return (None, is_available)

def load_from_state(source_dict):
    stack = [((), layers.value)]
    while stack:
        path, current_dict = stack.pop()
        for key, value in current_dict.items():
            if isinstance(value, dict):
                stack.append((path + (key,), value))
            else:
                keys = list(path + (key,))
                src_value, is_available = get_nested_value(source_dict, keys)
                if is_available:
                    if isinstance(value,solara.toestand.Reactive):
                        assign_nested_value(layers.value, keys, solara.reactive(src_value))
                    else:
                        assign_nested_value(layers.value, keys, src_value)



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

    l = layers.value['layers']['landuse']['data'].value
    b = layers.value['layers']['building']['data'].value
    h = layers.value['layers']['household']['data'].value
    i = layers.value['layers']['individual']['data'].value
    
    _, tally_geo =  create_tally(l, b, h, i)
    store_in_session_storage('explore_tally_geo', tally_geo)
    store_in_session_storage('explore_tally_minimal', tally_geo[layers.value['tally_filter_cols']])
    tally_counter.value += 1
    
@task
def load_session():
    tmp_file = tempfile.NamedTemporaryFile("wb", delete=False)
    storage.value.get_client().download_fileobj(storage.value.bucket_name, session_name.value + '.data', tmp_file)
    tmp_file.close()
    with open(tmp_file.name, 'rb') as obj_file:
        print('unpickle session..', session_name.value)
        loaded_state = pickle.load(obj_file)
        load_from_state(loaded_state)
    os.unlink(tmp_file.name)  
    post_processing_after_load()
    force_render()

def fetch_metadata(session_name):
    tmp_file = tempfile.NamedTemporaryFile("wb", delete=False)
    storage.value.get_client().download_fileobj(storage.value.bucket_name, session_name + '.metadata', tmp_file)
    tmp_file.close()
    # Read tmp_file in binary read
    with open(tmp_file.name, 'rb') as obj_file:
        print('Opening session.metadata...')
        metadata = pickle.load(obj_file)
    # Delete tmp_file
    os.unlink(tmp_file.name)
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
    layers.set(create_new_app_state().value)
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
    tool3 = ipyleaflet.LayersControl.element(position='topright', collapsed=False)
    tool4 = ipyleaflet.ScaleControl.element(position='bottomleft')

    def create_layers():
        map_layers = []
        for l in layers.value['layers'].keys():
            df = layers.value['layers'][l]['data'].value
            if df is not None and isinstance(df, gpd.GeoDataFrame):
                df_filtered = df
                if l == 'building':
                    if building_filter.value is not None:
                        df_filtered = df[building_filter.value]
                if l == 'landuse':
                    if landuse_filter.value is not None:
                        df_filtered = df[landuse_filter.value]

                map_layer = create_map_layer(df_filtered, l)
                map_layers.append(map_layer)

        set_map_layers(map_layers)

    solara.use_memo(create_layers,
                    [building_filter.value, landuse_filter.value] +
                    [render_count.value])

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
        controls = [tool1, tool2, tool3, tool4],
        layout = layout
        )
    print(f"MapViewer render count {render_count.value}")

metric_update_pending = solara.reactive(False)


@task
def generate_metrics_local():
    metric_update_pending.set(True)
    print("Emtering generate_metrics_local")
    metrics = {name: {'value':0, 'max_value':0, 'desc': metric['desc']} for name, metric in layers.value['metrics'].items()}

    tally_geo = read_from_session_storage('explore_tally_geo')
    print('population_displacement_consensus explore', population_displacement_consensus.value)
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
                    [tally_counter.value,
                     layers.value['bounds'].value,
                     population_displacement_consensus.value,
                     tally_filter.value], debug_name="generate_metrics_loca")
    if generate_metrics_local.finished:
        filtered_metrics = generate_metrics_local.value

    metric_icons = [metric_icon1,metric_icon2,metric_icon3,metric_icon4,metric_icon5,metric_icon6,metric_icon7,metric_icon8]
    with solara.Row(justify="center", style="align-items: center; margin-top: -25px; margin-bottom: -25px"):
        solara.Markdown('''<h2 style="font-weight: bold; margin: 0px; line-height: 1.1">IMPACTS</h2>''')
        with solara.Link("/docs/metrics"):
             with solara.Tooltip('Metric definitions. Click for more info.'):
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
    lbl = {'ds': 'Damage State',
           'material': 'Load-Resisting System (Material)',
            'code_level': 'Code Level',
            'storeys': 'Number of Floors',
            'occupancy': 'Occupancy Type',
            'specialfac': 'Special Facility'}
    building = layers.value['layers']['building']['df'].value
    building_filter.value, _ = solara.use_cross_filter(id(building), "building_filter")
    if building is not None:
        with solara.Row(): #spacer
            solara.Markdown('''<h5 style=""></h5>''') 
        btn = solara.Button("BUILDING FILTERS")
        with solara.Column(align="stretch"):
            with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"35vh", "align":"stretch"}): #"height":"60vh"
                solara.CrossFilterReport(building)
                solara.CrossFilterSelect(building, "ds", multiple=True)
                solara.CrossFilterSelect(building, "specialfac", multiple=True)
                solara.CrossFilterSelect(building, "nhouse", multiple=True)
                solara.CrossFilterSelect(building, "residents", multiple=True)
                solara.CrossFilterSelect(building, "occupancy", multiple=True)
                solara.CrossFilterSelect(building, "storeys", multiple=True)
                solara.CrossFilterSelect(building, "code_level", multiple=True)
                solara.CrossFilterSelect(building, "material", multiple=True)
                solara.CrossFilterSelect(building, "zoneid", multiple=True)

    landuse = layers.value['layers']['landuse']['df'].value
    landuse_filter.value, _ = solara.use_cross_filter(id(landuse), "landuse_filter")
    if landuse is not None:
        with solara.Row(): #spacer
            solara.Markdown('''<h5 style=""></h5>''') 
        btn = solara.Button("LANDUSE FILTERS")
        with solara.Column(align="stretch"):
            with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"35vh", "align":"stretch"}): #"height":"60vh"   
                solara.CrossFilterReport(landuse)
                solara.CrossFilterSelect(landuse, "luf", multiple=True)
                solara.CrossFilterSelect(landuse, "avgincome", multiple=True)      


    tc = tally_counter.value
    print('tally_counter', tc)
    tally_minimal = read_from_session_storage('explore_tally_minimal')
    tally_filter.value, _ = solara.use_cross_filter(id(tally_minimal), "tally_filter")
    if tally_minimal is not None:
        with solara.Row(): #spacer
            solara.Markdown('''<h5 style=""></h5>''') 
        btn = solara.Button("METRIC FILTERS")
        with solara.Column(align="stretch"):
            with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"35vh", "align":"stretch"}): #"height":"60vh"   
                solara.CrossFilterReport(tally_minimal)
                for col in layers.value['tally_filter_cols']:
                    solara.CrossFilterSelect(tally_minimal, col, multiple=True)    
    print(f"fiter panel render count {render_count.value}")

    # preserve_edge_directions is only used for graph-based inputs (power and road)
    solara.Text("Spacer", style={'visibility':'hidden'})
    with solara.Row(justify="left", style="min-height: 0px"):
        solara.Select(label='population displacement consensus (default:2)', values=[1,2,3,4], value=population_displacement_consensus)
        with solara.Tooltip('Minimum number of conditions to claim a population displacement. Click for more info.'):
            solara.Button(icon_name="mdi-help-box", attributes={"href": "https://github.com/TomorrowsCities/tomorrowscities/wiki/4%E2%80%90Engine#parameters", "target": "_blank"}, text=True, outlined=False)


@solara.component
def Page():    
    solara.Title(" ")
    with solara.Sidebar():
        with solara.lab.Tabs(value=selected_tab.value, on_value=selected_tab.set, grow=True, align="center"):
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