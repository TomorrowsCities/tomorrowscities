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
import textwrap
from solara.lab import task
from solara.hooks.dataframe import cross_filter_context
import secrets
import tempfile
from html import escape

from . import storage, connect_storage, read_from_session_storage, store_in_session_storage
from ..backend.utils import building_preprocess, identity_preprocess, ParameterFile
from .engine import landuse_colors, generic_layer_colors, building_colors, road_edge_colors,\
                    power_edge_colors, ds_to_color, ds_to_color_approx, create_tally
from .engine import MetricWidget, create_new_app_state, ParameterFileWidget, VulnerabiliyDisplayer, FragilityDisplayer
from .utilities import PowerFragilityDisplayer
from ..backend.engine import generate_metrics

def get_session_list():
    if storage.value is not None:
        return sorted(storage.value.list_sessions(),reverse=True)
    return None

session_name = solara.reactive(None)
session_list = solara.reactive(get_session_list())
status_text = solara.reactive("")
selected_tab = solara.reactive(None)
MAP_INFO_TAB_INDEX = 2
render_count = solara.reactive(0)
zoom = solara.reactive(14)
tally_counter = solara.reactive(0)
tally_filter = solara.reactive(None)
building_filter = solara.reactive(None)
landuse_filter = solara.reactive(None)
population_displacement_consensus = solara.reactive(2)

layers = create_new_app_state()


last_click_time = solara.reactive(0.0)
last_click_render_order = solara.reactive(-1)

def ensure_map_info_state():
    if 'map_info_detail' not in layers.value:
        layers.value['map_info_detail'] = solara.reactive({})
    if 'map_info_button' not in layers.value:
        layers.value['map_info_button'] = solara.reactive("summary")

def open_map_info(properties, layer_name=""):
    ensure_map_info_state()
    import time
    current_time = time.time()
    if current_time - last_click_time.value > 0.2:
        last_click_time.set(current_time)
        last_click_render_order.set(-1)

    layer_render_order = layers.value['layers'].get(layer_name, {}).get('render_order', 0)
    
    if layer_render_order >= last_click_render_order.value:
        last_click_render_order.set(layer_render_order)
        layers.value['map_info_detail'].set(properties)
        layers.value['map_info_button'].set("detail")
        selected_tab.set(MAP_INFO_TAB_INDEX)

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
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()), name = name,
            style={'opacity': 1, 'dashArray': '0', 'fillOpacity': 1, 'weight': 1},
            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 1},
            style_callback=landuse_colors)
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

def road_node_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "road nodes")

def road_edge_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "road edges")

def power_edge_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "power edges")

def landuse_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "landuse")

def building_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "building")

def generic_layer_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "generic")

def intensity_click_handler(event=None, feature=None, id=None, properties=None, **kwargs):
    open_map_info(properties, "intensity")

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
        if not isinstance(dictionary, dict) or key not in dictionary:
            return (None, False)
        dictionary = dictionary[key]
    if isinstance(dictionary, dict) and keys[-1] in dictionary:
        return (dictionary[keys[-1]], True)
    return (None, False)

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

    # Update tally_filter_cols to include zoneid if missing (e.g. from old saved sessions)
    current_cols = layers.value['tally_filter_cols']
    if 'zoneid' not in current_cols:
        # Prepend to match engine page behavior
        layers.value['tally_filter_cols'] = ['zoneid'] + current_cols

    l = layers.value['layers']['landuse']['data'].value
    b = layers.value['layers']['building']['data'].value
    h = layers.value['layers']['household']['data'].value
    i = layers.value['layers']['individual']['data'].value
    
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
            zoom.set(calculated_zoom)

    _, tally_geo =  create_tally(l, b, h, i)
    store_in_session_storage('explore_tally_geo', tally_geo)
    store_in_session_storage('explore_tally_minimal', tally_geo[layers.value['tally_filter_cols']])
    if layers.value['metrics_realized'].value is None and tally_geo is not None:
        hazard_type = layers.value['hazard'].value
        fallback_metrics = generate_metrics(
            tally_geo,
            tally_geo,
            hazard_type,
            population_displacement_consensus.value
        )
        layers.value['metrics_realized'].set([fallback_metrics])
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
        
        # Define display mapping and order
        display_map = {
            'scenario_name': 'Scenario Name:',
            'hazard': 'Hazard Type:',
            'infra': 'Analysed Structure(s):',
            'datetime_analysis': 'Analysis Time:',
            'datetime_upload': 'Analysis Upload Time:',
            'user_id': 'Uploader User ID:'
        }

        with solara.Column(style={"margin-top": "10px"}):
            with solara.GridFixed(columns=2, row_gap="1px"):
                for key, label in display_map.items():
                    if key in metadata:
                        value = metadata[key]
                        
                        # Format value
                        if key == 'infra' and isinstance(value, list):
                            display_value = ", ".join(value)
                        elif value is None:
                            display_value = 'None'
                        else:
                            display_value = f'{value}'
                        
                        # Row with bold label and left-aligned value
                        solara.Text(f"{label}", style={"font-weight": "bold"})
                        with solara.Row(justify="start"):
                            solara.Text(display_value)
        # print(metadata)

def clear_session():
    layers.set(create_new_app_state().value)
    force_render()

def force_render():
    render_count.set(render_count.value + 1)

@solara.component
def StorageViewer():
    with solara.Card(title='Load Scenario', subtitle='Choose a scenario from storage'):
        solara.Select(label='Choose scenario',value=session_name.value, values=session_list.value,
                    on_value=session_name.set)
        solara.Button(style={"width":"48%","margin":"1%"},label="Refresh List", on_click=lambda: refresh_session_list(),
                      disabled = True if storage.value is None else False)
        solara.Button(style={"width":"48%","margin":"1%"},label="Revive Storage", on_click=lambda: revive_storage())
        solara.Button(style={"width":"48%","margin":"1%"},label="Load Scenario", on_click = load_session, 
                      disabled=True if session_name.value is None else False)
        solara.Button(style={"width":"48%","margin":"1%"},label='Clear Scenario', on_click=lambda: clear_session())
    solara.ProgressLinear(load_session.pending)
    solara.Text(text=status_text.value)
    MetaDataViewer(session_name)

@solara.component
def MapViewer():
    print('rendering mapviewer')
    filters_open, set_filters_open = solara.use_state(False)
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

    # Removed cleanup_cache as we no longer cache map layers

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

                print(f"Creating new layer for {l}, df_filtered size: {len(df_filtered)}")
                map_layer = create_map_layer(df_filtered, l)
                map_layers.append(map_layer)

        return map_layers

    map_layers = solara.use_memo(create_layers,
                    [building_filter.value, landuse_filter.value] +
                    [render_count.value])

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
            layers=base_layers + map_layers,
            controls = controls,
            layout = layout
            )
        with solara.Div(classes=["map-filter-overlay"]):
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
                with solara.Card(elevation=2, style={"padding": "0", "border-radius": "12px", "background": "rgba(255,255,255,0.98)", "min-width": "260px", "margin-top": "10px", "border": "1px solid rgba(0,0,0,0.08)", "box-shadow": "0 10px 26px rgba(0,0,0,0.16)"}):
                    with solara.Div(classes=["map-filter-content"]):
                        FilterPanel()
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

    print(f"render count {render_count.value}")

@solara.component
def MapInfo():
    print(f'{layers.value["bounds"].value}')
    # Add dependency on render_count to ensure updates after load
    _ = render_count.value
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
def FilterPanel():
    cross_filter_store = solara.use_context(cross_filter_context)
    with solara.Column(classes=["map-filter-panel"], gap="8px"):
        solara.Markdown("#### Filters")

        landuse = layers.value['layers']['landuse']['df'].value
        landuse_filter.value, set_landuse_cross_filter = solara.use_cross_filter(id(landuse), "landuse_filter")
        building = layers.value['layers']['building']['df'].value
        tc = tally_counter.value
        print('tally_counter', tc)
        tally_minimal = read_from_session_storage('explore_tally_minimal')
        tally_filter.value, set_tally_cross_filter = solara.use_cross_filter(id(tally_minimal), "tally_filter")
        if landuse is None and building is None and tally_minimal is None:
            solara.Text("Filters become available when analysis results are ready.")

        if landuse is not None:
            btn = solara.Button("LANDUSE FILTERS", classes=["filter-section-button"], style={"width":"100%"})
            with solara.Column(align="stretch"):
                with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"320px"}):
                    with solara.Div(classes=["filter-menu-body"]):
                        solara.Markdown("**Land Use Filters**")
                        solara.CrossFilterReport(landuse)
                        solara.CrossFilterSelect(landuse, "zoneid", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(landuse, "luf", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(landuse, "avgincome", multiple=True, max_unique=5000)

        building_filter.value, set_building_cross_filter = solara.use_cross_filter(id(building), "building_filter")
        if building is not None:
            btn = solara.Button("BUILDING FILTERS", classes=["filter-section-button"], style={"width":"100%"})
            with solara.Column(align="stretch"):
                with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"320px"}):
                    with solara.Div(classes=["filter-menu-body"]):
                        solara.Markdown("**Building Filters**")
                        solara.CrossFilterReport(building)
                        solara.CrossFilterSelect(building, "zoneid", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "ds", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "specialfac", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "nhouse", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "residents", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "occupancy", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "storeys", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "code_level", multiple=True, max_unique=5000)
                        solara.CrossFilterSelect(building, "material", multiple=True, max_unique=5000)

        if tally_minimal is not None:
            btn = solara.Button("METRIC FILTERS", classes=["filter-section-button"], style={"width":"100%"})
            with solara.Column(align="stretch"):
                with solara.lab.Menu(activator=btn, close_on_content_click=False, style={"width":"320px"}):
                    with solara.Div(classes=["filter-menu-body"]):
                        solara.Markdown("**Metric Filters**")
                        solara.CrossFilterReport(tally_minimal)
                        for col in layers.value['tally_filter_cols']:
                            solara.CrossFilterSelect(tally_minimal, col, multiple=True, max_unique=5000)
        def reset_filters():
            for data_key in [id(landuse), id(building), id(tally_minimal)]:
                if data_key in cross_filter_store.filters:
                    for key in list(cross_filter_store.filters[data_key].keys()):
                        cross_filter_store.filters[data_key][key] = None
            for listener in list(cross_filter_store.listeners):
                listener()
        solara.Button("Reset Filters", on_click=reset_filters, text=True, outlined=True, style={"width": "100%"})
    print(f"fiter panel render count {render_count.value}")


@solara.component
def LayerDisplayer():
    _ = render_count.value
    print(f'{layers.value["bounds"].value}')
    nonempty_layers = {
        name: layer for name, layer in layers.value['layers'].items()
        if layer['data'].value is not None or layer['df'].value is not None
    }
    nonempty_layer_names = list(nonempty_layers.keys())

    if len(nonempty_layer_names) == 0:
        solara.Info("There is no layer details data yet!")
        return

    selected = layers.value['selected_layer'].value

    def set_selected(s):
        layers.value['selected_layer'].set(s)

    solara.ToggleButtonsSingle(value=selected, on_value=set_selected, values=nonempty_layer_names)
    if selected is None and len(nonempty_layer_names) > 0:
        set_selected(nonempty_layer_names[0])
    if selected is not None:
        data = nonempty_layers[selected]['data'].value
        fallback_df = nonempty_layers[selected]['df'].value
        if data is None:
            data = fallback_df
        if isinstance(data, gpd.GeoDataFrame) or isinstance(data, pd.DataFrame):
            if "geometry" in data.columns:
                if layers.value['bounds'].value is not None:
                    ((ymin, xmin), (ymax, xmax)) = layers.value['bounds'].value
                    df_filtered = data.cx[xmin:xmax, ymin:ymax].drop(columns='geometry')
                    if df_filtered.empty:
                        df_filtered = data.drop(columns='geometry')
                else:
                    df_filtered = data.drop(columns='geometry')
                solara.DataFrame(df_filtered, items_per_page=5)
            else:
                if selected == "power fragility":
                    PowerFragilityDisplayer(data, items_per_page=5)
                else:
                    solara.DataFrame(data, items_per_page=5)
            if selected in ["landuse", "building", "road edges", "road nodes", "power nodes", "power edges", "intensity"]:
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


@solara.component
def MetricStatistics():
    _ = render_count.value
    if layers.value['metrics_realized'].value is None:
        solara.Info('There is no metrics statistics data yet!')
        return

    metrics = layers.value['metrics_realized'].value
    if metrics and not all('ds_breakdown' in metric_data for metric_group in metrics for metric_data in metric_group.values()):
        tally_geo = read_from_session_storage('explore_tally_geo')
        hazard_type = layers.value['hazard'].value
        if tally_geo is not None:
            rebuilt_metrics = generate_metrics(
                tally_geo,
                tally_geo,
                hazard_type,
                population_displacement_consensus.value
            )
            metrics = [
                {
                    metric_name: {
                        **metric_group[metric_name],
                        'ds_breakdown': rebuilt_metrics.get(metric_name, {}).get('ds_breakdown')
                    }
                    for metric_name in metric_group.keys()
                }
                for metric_group in metrics
            ]
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
                cells.append(f'<td style="text-align:{align};">{escape(display_value)}</td>')
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
            render_metric_table(df)
        with solara.lab.Tab("Stats"):
            stats_df = summary.reset_index().rename(columns={'index': 'Statistic'})
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
            render_metric_table(ds_df, first_column_left=True)


@solara.component
def ExploreSettingsPanel():
    with solara.Row(justify="left", style="min-height: 0px"):
        solara.Select(label='population displacement consensus (default:2)', values=[1,2,3,4], value=population_displacement_consensus)
        with solara.Tooltip('Minimum number of conditions to claim a population displacement. Click for more info.'):
            solara.Button(icon_name="mdi-help-box", attributes={"href": "https://github.com/TomorrowsCities/tomorrowscities/wiki/4%E2%80%90Engine#parameters", "target": "_blank"}, text=True, outlined=False)


@solara.component
def ExploreSidebarContent():
    with solara.lab.Tabs(value=selected_tab.value, on_value=selected_tab.set, grow=True, align="center"):
        with solara.lab.Tab("SCENARIOS"):
            StorageViewer()
        with solara.lab.Tab("SETTINGS"):              
            ExploreSettingsPanel()
        with solara.lab.Tab("MAP INFO"):
            MapInfo()

@solara.component
def Page():    
    css = """
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
    
    def on_load():
        session_data = read_from_session_storage('explore_initialized')
        if session_data is None:
            clear_session()
            store_in_session_storage('explore_initialized', True)
            
    solara.use_effect(on_load, [])

    # Mobile View: Content at the top
    with solara.Column(classes=["d-block", "d-md-none"], style={"width": "100%"}):
        ExploreSidebarContent()

    # Desktop View: Content in Sidebar
    with solara.Sidebar():
        with solara.Column(classes=["d-none", "d-md-block"]):
             ExploreSidebarContent()
      
    MapViewer()
    with solara.Row(justify="center"):
        MetricPanel()
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
