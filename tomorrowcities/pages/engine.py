import solara
import time
import random
import json
import pandas as pd
import os
os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
from typing import Tuple, Optional
import ipyleaflet
from ipyleaflet import AwesomeIcon, Marker
import numpy as np
import logging, sys
#logging.basicConfig(stream=sys.stderr, level=logging.INFO)

from ..backend.engine import compute, compute_power_infra, calculate_metrics

layers = solara.reactive({
    'layers' : {
        'building': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {'ds': 0, 'metric1': 0, 'metric2': 0, 'metric3': 0,'metric4': 0, 'metric5': 0,'metric6': 0,'metric7': 0},
            'cols_required': set(['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac']),
            'cols': set(['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac'])},
        'landuse': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['geometry', 'zoneid', 'luf', 'population', 'densitycap', 'avgincome']),
            'cols': set(['geometry', 'zoneid', 'luf', 'population', 'densitycap', 'floorarat', 'setback', 'avgincome'])},
        'household': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required':set(['hhid', 'nind', 'income', 'bldid', 'commfacid']),
            'cols':set(['hhid', 'nind', 'income', 'bldid', 'commfacid'])},
        'individual': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid']),
            'cols': set(['individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid'])},
        'intensity': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['geometry','im']),
            'cols': set(['geometry','im'])},
        'fragility': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['expstr','muds1_g','muds2_g','muds3_g','muds4_g','sigmads1','sigmads2','sigmads3','sigmads4']),
            'cols': set(['expstr','muds1_g','muds2_g','muds3_g','muds4_g','sigmads1','sigmads2','sigmads3','sigmads4'])},
        'vulnerability': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5','hw6']),
            'cols': set(['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5','hw6'])},
        'power nodes': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {'ds': 0, 'is_damaged': False, 'is_operational': True},
            'cols_required': set(['geometry', 'fltytype', 'strctype', 'utilfcltyc', 'indpnode', 'guid', 
                         'node_id', 'x_coord', 'y_coord', 'pwr_plant', 'serv_area', 'n_bldgs', 
                         'income', 'eq_vuln']),
            'cols': set(['geometry', 'fltytype', 'strctype', 'utilfcltyc', 'indpnode', 'guid', 
                         'node_id', 'x_coord', 'y_coord', 'pwr_plant', 'serv_area', 'n_bldgs', 
                         'income', 'eq_vuln'])},
        'power edges': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['from_node', 'direction', 'pipetype', 'edge_id', 'guid', 'capacity', 
                         'geometry', 'to_node', 'length']),
            'cols': set(['from_node', 'direction', 'pipetype', 'edge_id', 'guid', 'capacity', 
                         'geometry', 'to_node', 'length'])},
        'power fragility': {
            'df': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'extra_cols': {},
            'cols_required': set(['vuln_string', 'med_slight', 'med_moderate', 'med_extensive', 'med_complete', 
                         'beta_slight', 'beta_moderate', 'beta_extensive', 'beta_complete']),
            'cols': set(['vuln_string', 'med_slight', 'med_moderate', 'med_extensive', 'med_complete', 
                         'beta_slight', 'beta_moderate', 'beta_extensive', 'beta_complete', 'description'])}
            },
    'center': solara.reactive((41.01,28.98)),
    'selected_layer' : solara.reactive(None),
    'render_count': solara.reactive(0),
    'bounds': solara.reactive(None),
    'policies': {
        '1': {'id':1, 'label': 'Policy 1', 'description': 'Land and tenure security program', 'applied': solara.reactive(False)},
        '2': {'id':2, 'label': 'Policy 2', 'description': 'State-led upgrading/retrofitting of low-income/informal housing', 'applied': solara.reactive(False)},
    },
    'metrics': {
        "metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": 100},
        "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": 100},
        "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": 100},
        "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 100},
        "metric5": {"desc": "Number of households displaced", "value": 0, "max_value": 100},
        "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": 100},
        "metric7": {"desc": "Population displacement", "value": 0, "max_value":100},}})


def building_colors(feature):
    ds_to_color = {0: 'lavender', 1:'violet',2:'fuchsia',3:'indigo',4:'darkslateblue',5:'black'}
    ds = feature['properties']['ds'] 
    return {'fillColor': 'black', 'color': 'red' if ds > 0 else 'blue' }

def power_node_colors(feature):
    print(feature)
    ds_to_color = {0: 'lavender', 1:'violet',2:'fuchsia',3:'indigo',4:'darkslateblue',5:'black'}
    ds = random.randint(0,5) #feature['properties']['ds'] 
    return {'color': ds_to_color[ds], 'fillColor': ds_to_color[ds]}

def create_map_layer(df, name):
    if df is None:
        return None 
    if "geometry" not in list(df.columns):
        return None 
    
    if name not in layers.value['layers'].keys():
        return None
    
    existing_map_layer = layers.value['layers'][name]['map_layer'].value
    if existing_map_layer is not None and not layers.value['layers'][name]['force_render'].value:
        return existing_map_layer
    
    if name == "intensity":
        locs = np.array([df.geometry.y.to_list(), df.geometry.x.to_list(), df.im.to_list()]).transpose().tolist()
        map_layer = ipyleaflet.Heatmap(locations=locs, radius = 10) 
    elif name == "building":
        map_layer = ipyleaflet.GeoJSON(data = json.loads(df.to_json()),
                        style={'opacity': 1, 'fillOpacity': 0.5, 'weight': 1},
                        hover_style={'color': 'blue', 'dashArray': '0', 'fillOpacity': 0.5},
                        style_callback=building_colors)
        
    elif name == "power nodes":
        markers = []
        for index, node in df.iterrows():
            x = node.geometry.x
            y = node.geometry.y
            marker_color = 'blue' if node['is_operational'] else 'red'
            icon_name = 'fa-industry' if node['pwr_plant'] else 'bolt'
            icon_color = 'black'
            marker = Marker(icon=AwesomeIcon(
                        name=icon_name,
                        marker_color=marker_color,
                        icon_color=icon_color,
                        spin=False
                    ),location=(y,x),title=f'{node["node_id"]}')

            markers.append(marker)
        map_layer= ipyleaflet.MarkerCluster(markers=markers,
                                                   disable_clustering_at_zoom=5)
        
        
    else:
        map_layer = ipyleaflet.GeoData(geo_dataframe = df)
    layers.value['layers'][name]['map_layer'].set(map_layer)
    layers.value['layers'][name]['force_render'].set(False)
    return map_layer

@solara.component
def MetricWidget(name, description, value, max_value, render_count):
    value, set_value = solara.use_state_or_update(value)
    max_value, set_max_value = solara.use_state_or_update(max_value)
    options = { 
        "series": [ {
                "type": 'gauge',  
                "min": 0,
                "name": description,
                "max": max_value,
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
            solara.FigureEcharts(option=options, attributes={ "style": "height: 100px; width: 100px" })


def import_data(fileinfo: solara.components.file_drop.FileInfo):
    data = fileinfo['data']
    extension = fileinfo['name'].split('.')[-1]
    if extension == 'xlsx':
        df = pd.read_excel(data)
    else:
        json_string = data.decode('utf-8')
        json_data = json.loads(json_string)
        if "features" in json_data.keys():
            df = gpd.GeoDataFrame.from_features(json_data['features'])
        else:
            df = pd.read_json(json_string)

    df.columns = df.columns.str.lower()

    # in the first pass, look for exact column match
    name = None
    for layer_name, layer in layers.value['layers'].items():
        if layer['cols'] == set(df.columns):
            name = layer_name
            break
    # if not, check only the required columns
    if name is None:
        for layer_name, layer in layers.value['layers'].items():
            if layer['cols_required'].issubset(set(df.columns)):
                name = layer_name
                logging.debug('There are extra columns', set(df.columns) - layer['cols_required'])
                break
    

    # Inject columns
    if name is not None:
        for col, val in layers.value['layers'][name]['extra_cols'].items():
            df[col] = val
    return (name, df)


@solara.component
def FileDropZone():
    total_progress, set_total_progress = solara.use_state(-1)
    fileinfo, set_fileinfo = solara.use_state(None)
    result, set_result = solara.use_state(solara.Result(True))

    def load():
        if fileinfo is not None:
            print('processing file')
            name, df = import_data(fileinfo)
            if name is not None and df is not None:
                layers.value['layers'][name]['df'].set(df)
                layers.value['selected_layer'].set(name)
                layers.value['layers'][name]['visible'].set(True)
                layers.value['layers'][name]['force_render'].set(True)
                if  "geometry" in list(df.columns):
                    center = (df.geometry.centroid.y.mean(), df.geometry.centroid.x.mean())
                    layers.value['center'].set(center)
            else:
                return False
        return True
        
    def progress(x):
        set_total_progress(x)

    def on_file_deneme(f):
        set_fileinfo(f)
    
    result = solara.use_thread(load, dependencies=[fileinfo])

    solara.FileDrop(on_total_progress=progress,
                    on_file=on_file_deneme, 
                    lazy=False)
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
def LayerDisplayer():
    print(f'{layers.value["bounds"].value}')
    nonempty_layers = {name: layer for name, layer in layers.value['layers'].items() if layer['df'].value is not None}
    nonempty_layer_names = list(nonempty_layers.keys())
    selected = layers.value['selected_layer'].value
    def set_selected(s):
        layers.value['selected_layer'].set(s)

    solara.ToggleButtonsSingle(value=selected, on_value=set_selected, 
                               values=nonempty_layer_names)
    if selected is None and len(nonempty_layer_names) > 0:
        set_selected(nonempty_layer_names[0])
    if selected is not None:
        df = nonempty_layers[selected]['df'].value
        if "geometry" in df.columns:
            ((ymin,xmin),(ymax,xmax)) = layers.value['bounds'].value
            solara.DataFrame(df.cx[xmin:xmax,ymin:ymax].drop(columns='geometry'))
        else:
            solara.DataFrame(df)


@solara.component
def MetricPanel():
    building = layers.value['layers']['building']['df'].value
    filtered_metrics = {name: 0 for name in layers.value['metrics'].keys()}
    if building is not None and layers.value['bounds'].value is not None:
        ((ymin,xmin),(ymax,xmax)) = layers.value['bounds'].value
        filtered = building.cx[xmin:xmax,ymin:ymax]
        for metric in filtered_metrics.keys():
            filtered_metrics[metric] = int(filtered.cx[xmin:xmax,ymin:ymax][metric].sum())
    
    with solara.Row():
        for name, metric in layers.value['metrics'].items():
            MetricWidget(name, metric['desc'], 
                         filtered_metrics[name], 
                         metric['max_value'],
                         layers.value['render_count'].value)
        with solara.Link("/docs/metrics"):
            solara.Button(icon_name="mdi-help-circle-outline", icon=True)
  

@solara.component
def LayerController():
    with solara.Row(gap="0px"):
        for layer_name, layer in layers.value['layers'].items():
            if layer['map_layer'].value is not None:
                solara.Checkbox(label=layer_name, 
                                value=layer['visible'])

                    
@solara.component
def MapViewer():
    print('rendering mapviewer')
    default_zoom = 14
    #default_center = (-1.3, 36.80)
    zoom, set_zoom = solara.use_state(default_zoom)
    #center, set_center = solara.use_state(default_center)

    base_map = ipyleaflet.basemaps["Stamen"]["Watercolor"]
    base_layer = ipyleaflet.TileLayer.element(url=base_map.build_url())
    map_layers = [base_layer]

    for layer_name, layer in layers.value['layers'].items():
        df = layer['df'].value
        if df is None:
            continue
        # we have something to display on map
        if  "geometry" in list(df.columns) and layer['visible'].value:
            map_layer = create_map_layer(df, layer_name)
            if map_layer is not None:
                map_layers.append(map_layer)

     
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
        layers=map_layers
        )
        
@solara.component
def ExecutePanel():
    infra, set_infra = solara.use_state(["building"])
    hazard, set_hazard = solara.use_state("flood")


    execute_counter, set_execute_counter = solara.use_state(0)
    execute_btn_disabled, set_execute_btn_disabled = solara.use_state(False)
    execute_error = solara.reactive("")

    def on_click():
        set_execute_counter(execute_counter + 1)
        execute_error.set("")

    def is_ready_to_run(infra, hazard):
        existing_layers = set([name for name, l in layers.value['layers'].items() if l['df'].value is not None])
        missing = []

        if hazard == "earthquake":
            if "power" in  infra:
                missing += list(set(["power edges","power nodes","intensity","power fragility"]) - existing_layers)
            if "building" in infra:
                missing += list(set(["landuse","building","household","individual","intensity","fragility"]) - existing_layers)
        elif hazard == "flood":
            if "power" in  infra:
                missing += list(set(["power edges","power nodes","intensity","power vulnerability"]) - existing_layers)
            if "building" in infra:
                missing += list(set(["landuse","building","household","individual","intensity","vulnerability"]) - existing_layers)
 
        if infra == []:
            missing += ['You should select power and/or building']
        return missing == [], missing
    


    def execute_engine():


        def execute_infra():
            nodes = layers.value['layers']['power nodes']['df'].value
            edges = layers.value['layers']['power edges']['df'].value
            intensity = layers.value['layers']['intensity']['df'].value
            power_fragility = layers.value['layers']['power fragility']['df'].value


            eq_ds, is_damaged, is_operational = compute_power_infra(nodes, 
                                    edges,
                                    intensity,
                                    power_fragility)
            
            #power_node_df =  dfs['Power Nodes'].copy()                         
            nodes['ds'] = list(eq_ds)
            nodes['is_damaged'] = list(is_damaged)
            nodes['is_operational'] = list(is_operational)
            return nodes

        def execute_building():
            landuse = layers.value['layers']['landuse']['df'].value
            buildings = layers.value['layers']['building']['df'].value
            household = layers.value['layers']['household']['df'].value
            individual = layers.value['layers']['individual']['df'].value
            intensity = layers.value['layers']['intensity']['df'].value

            fragility = layers.value['layers']['fragility']['df'].value
            vulnerability = layers.value['layers']['vulnerability']['df'].value

            policies = [p['id'] for id, p in layers.value['policies'].items() if p['applied'].value]

            print('policies',policies)
            df_bld_hazard = compute(
                landuse,
                buildings, 
                household, 
                individual,
                intensity,
                fragility if hazard == "earthquake" else vulnerability, 
                hazard,policies=policies)
            buildings['ds'] = list(df_bld_hazard['ds'])
            computed_metrics, df_metrics = calculate_metrics(buildings, household, individual, hazard, policies=policies)
        
            print(computed_metrics)
            for metric in df_metrics.keys():
                buildings[metric] = list(df_metrics[metric][metric])
                layers.value['metrics'][metric]['value'] = computed_metrics[metric]['value']
                layers.value['metrics'][metric]['max_value'] = computed_metrics[metric]['max_value']
            
            return buildings

        if execute_counter > 0 :
            is_ready, missing = is_ready_to_run(infra, hazard)
            if not is_ready:
                raise Exception(f'Missing {missing}')
            
            if 'power' in infra:
                nodes = execute_infra()
                layers.value['layers']['power nodes']['df'].set(nodes)
            if 'building' in infra:
                buildings = execute_building()
                layers.value['layers']['building']['df'].set(buildings)

            # trigger render event
            layers.value['render_count'].set(layers.value['render_count'].value + 1)
            if 'power' in infra:
                layers.value['layers']['power nodes']['force_render'].set(True)
            if 'building' in infra:
                layers.value['layers']['building']['force_render'].set(True)

            

    # Execute the thread only when the depencency is changed
    result = solara.use_thread(execute_engine, dependencies=[execute_counter])

    with solara.Row(justify="center"):
        solara.ToggleButtonsMultiple(value=infra, on_value=set_infra, values=["building","power"])
    with solara.Row(justify="center"):
        solara.ToggleButtonsSingle(value=hazard, on_value=set_hazard, values=["earthquake","flood"])

    PolicyPanel()
    solara.ProgressLinear(value=False)
    solara.Button("Calculate", on_click=on_click, outlined=True,
                  disabled=execute_btn_disabled)
    # The statements in this block are passed several times during thread execution
    if result.error is not None:
        execute_error.set(execute_error.value + str(result.error))

    if execute_error.value != "":
        solara.Text(f'{execute_error}', style={"color":"red"})
    else:
        solara.Text("Spacer", style={"visibility": "hidden"})

    if result.state in [solara.ResultState.RUNNING, solara.ResultState.WAITING]:
        set_execute_btn_disabled(True)
        solara.ProgressLinear(value=True)
    else:
        set_execute_btn_disabled(False)
        solara.ProgressLinear(value=False)

@solara.component
def PolicyPanel():
    with solara.Row():
        for policy_key, policy in layers.value['policies'].items():
            with solara.Tooltip(tooltip=policy['description']):
                solara.Checkbox(label=policy['label'], 
                                value=policy['applied'])
        with solara.Link("/docs/policies"):
            solara.Button(icon_name="mdi-help-circle-outline", icon=True)


@solara.component
def WebApp():

    with solara.Columns([30,60]):
        with solara.Column():
            solara.Markdown('[Download Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing)')
            FileDropZone()
            ExecutePanel()
        with solara.Column():
            LayerController()
            MapViewer()
            MetricPanel()
            
    LayerDisplayer()

@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    css = """
    .v-input {
        height: 10px;
    }

    .v-btn-toggle:not(.v-btn-toggle--dense) .v-btn.v-btn.v-size--default {
        height: 24px;
        min-height: 0;
        min-width: 24px;
    }

    """
    solara.Style(value=css)
    solara.Title("TCDSE » Engine")

    WebApp()
