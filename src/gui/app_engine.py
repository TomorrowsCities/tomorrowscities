import solara
from solara.components.file_drop import FileInfo
import os
os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
import pandas as pd
import json
import numpy as np
import ipyleaflet
from ipyleaflet import AwesomeIcon, Marker
import engine
import random
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import math

css = """

"""
plt.switch_backend("agg")

# Static parameters
initial_building_columns = set(['zoneID', 'bldID', 'nHouse', 'residents', 'specialFac', 'expStr', 'fptarea', 'repValue'])
building_columns = set(['geometry','metric1','metric2','metric3','metric4','metric5','metric6','metric7','ds','zoneID', 'bldID', 'nHouse', 'residents', 'specialFac', 'expStr', 'fptarea', 'repValue'])
landuse_columns = set(['geometry', 'zoneID', 'LuF', 'population', 'densityCap', 'floorARat', 'setback', 'avgIncome'])
household_columns = set(['hhID', 'nInd', 'income', 'bldID', 'CommFacID'])
individual_columns = set(['indivId', 'hhID', 'gender', 'age', 'eduAttStat', 'head', 'indivFacID'])
intensity_columns = set(['geometry','im'])
power_edge_columns = set(['FROM_NODE', 'direction', 'pipetype', 'EDGE_ID', 'guid', 'capacity', 'geometry', 'TO_NODE', 'length'])
power_node_columns = set(['geometry', 'FLTYTYPE', 'STRCTYPE', 'UTILFCLTYC', 'INDPNODE', 'guid',
       'NODE_ID', 'x_coord', 'y_coord', 'pwr_plant', 'serv_area', 'n_bldgs',
       'income', 'eq_vuln'])
vulnerabillity_columns = set(['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5','hw6'])
fragility_columns = set(['expstr','muds1_g','muds2_g','muds3_g','muds4_g','sigmads1','sigmads2','sigmads3','sigmads4'])
power_fragility_columns = set(['vuln_string', 'med_Slight', 'med_Moderate', 'med_Extensive', 'med_Complete', 'beta_Slight', 'beta_Moderate', 'beta_Extensive', 'beta_Complete', 'description'])
all_layers = ["Landuse", "Buildings", "Household","Individual","Intensity","Vulnerability","Fragility","Power Links","Power Nodes", "Power Fragility"]
infra_options = ["power",'buildings']

metrics_template = {"metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": 0},
            "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": 0},
            "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": 0},
            "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 0},
            "metric5": {"desc": "Number of homeless households", "value": 0, "max_value": 0},
            "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": 0},
            "metric7": {"desc": "Population displacement", "value": 0, "max_value": 0},}

metrics = solara.reactive(metrics_template)


layers = solara.reactive([])

base_map = ipyleaflet.basemaps.OpenStreetMap.BZH

default_zoom = 14
default_radius = 10
default_center = (41.03,28.94)

center = solara.reactive(default_center)
zoom = solara.reactive(default_zoom)
bounds = solara.reactive(None)
radius = solara.reactive(default_radius)
hazard = solara.reactive("earthquake")
infra = solara.reactive([])

loading = solara.reactive(-1)

building_df = solara.reactive(None)
clicked_df = solara.reactive(pd.DataFrame(columns=['attribute','value']))


def building_click_handler(event=None, feature=None, id=None, properties=None):
    df = pd.DataFrame(columns=['attribute','value'])
    df['attribute'] = [k for k in properties.keys() if k != 'style']
    df['value']= [str(properties[k]) for k in properties.keys() if k != 'style']
    clicked_df.set(df)

def landuse_click_handler(event=None, feature=None, id=None, properties=None):
    df = pd.DataFrame(columns=['attribute','value'])
    df['attribute'] = [k for k in properties.keys() if k != 'style']
    df['value']= [str(properties[k]) for k in properties.keys() if k != 'style']
    clicked_df.set(df)

def power_node_click_handler(event=None, feature=None, properties=None):
    print(locals())
    df = pd.DataFrame(columns=['attribute','value'])
    df['attribute'] = [k for k in properties.keys() if k != 'style']
    df['value']= [str(properties[k]) for k in properties.keys() if k != 'style']
    clicked_df.set(df)

def landuse_colors(feature):
    luf_type = feature['properties']['LuF']
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

def building_colors(feature):
        ds_to_color = {0: 'lavender', 1:'violet',2:'fuchsia',3:'indigo',4:'darkslateblue',5:'black'}
        ds = feature['properties']['ds'] 

        return {'color': ds_to_color[ds], 'fillColor': ds_to_color[ds]}

def power_node_style(feature,):
    return dict(
        opacity=0.5,
        color='black',
        weight=0.9
    )


@solara.component
def MapComponent():

    extra_layers = [l['geojson'] for l in layers.value if 'geojson' in l.keys() and l['visible'].value]

    # MarkerGroup Layer
    dataframes = {l['name']:l['df'] for l in layers.value if l['visible'].value}
    if 'Power Nodes' in dataframes.keys():
        df = dataframes['Power Nodes'].value
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
                    ),location=(y,x),title=f'{node["NODE_ID"]}')

            markers.append(marker)
        power_node_layer= ipyleaflet.MarkerCluster(markers=markers,
                                                   disable_clustering_at_zoom=5)
        extra_layers.append(power_node_layer)

    



    if building_df.value is not None:               
        json_data = json.loads(building_df.value.to_json())
        building_layer = ipyleaflet.GeoJSON(data=json_data,
                                            style={'opacity': 1, 'fillOpacity': 0.5, 'weight': 1},
                                            hover_style={'color': 'red', 'dashArray': '0', 'fillOpacity': 0.5},
                                            style_callback=building_colors)
        building_layer.on_click(building_click_handler)
        extra_layers.append(building_layer)



        
    print('rendering map, number of extra layers',len(extra_layers))

    ipyleaflet.Map.element(
        zoom=zoom.value,
        on_zoom=zoom.set,
        on_bounds=bounds.set,
        center=center.value,
        on_center=center.set,
        scroll_wheel_zoom=True,
        dragging=True,
        double_click_zoom=True,
        touch_zoom=True,
        box_zoom=True,
        keyboard=True,
        layers=[ipyleaflet.TileLayer.element(url=base_map.build_url())]+extra_layers,
    )

@solara.component
def DialWidget(name, value, max_value=10000):
    print('value',value,'max_value',max_value)
    if max_value == 0:
        max_value = 10000
    fig = Figure(tight_layout=True,dpi=30,frameon=False)
    fig.set_size_inches(1.5,1)
    ax = fig.subplots()
    ax.axis('equal')
    ax.axis('off')

    ax.set_xticks([])
    ax.set_yticks([])

    t = np.linspace(0, math.pi, 100)

    cos = np.cos(t)
    sin = np.sin(t)

    ax.plot(cos,sin, linewidth=2)
    value_t = math.pi * (1 - (value / max_value))

    fill_color = 'red'
    if value_t >  math.pi / 2  :
        x1 = np.linspace(-1,np.cos(value_t),100)
        y1 = np.sqrt(1 - x1**2)
        ax.fill_between(x1,y1,color=fill_color)
        x1 = np.linspace(np.cos(value_t),0,100)
        y1 = np.tan(value_t) * x1
        ax.fill_between(x1,y1,color=fill_color)
    else:
        x = np.linspace(-1, np.cos(value_t),100)
        y1 = np.sqrt(1-x**2)
        y2a = np.zeros(100)
        y2b = np.tan(value_t) * x
        y2 = np.maximum(y2a,y2b)
        ax.fill_between(x,y1,y2,color=fill_color)

    ax.text(0,0.5,value,fontdict={'fontsize':18},verticalalignment="center",
        horizontalalignment="center",color="black")
    ax.text(1,0,max_value,fontdict={'fontsize':8},verticalalignment="center",
        horizontalalignment="right",color="black")
    ax.text(0,-0.1,name,fontdict={'fontsize':10},verticalalignment="top",
        horizontalalignment="center",color="black")
    ax.set_xlim(-1.1,1.1)
    ax.set_ylim(-0.2,1.2)
    solara.FigureMatplotlib(fig)

@solara.component
def ExistingLayers():
    with solara.Column(gap="0px"):
        for layer in layers.value:
            solara.Checkbox(label=layer['name'],
                            value=layer['visible'],
                            style="margin-top: 0px; padding-top: 0px; min-height: 0px;")
                
@solara.component
def VisioningScenarioViewer():

    # State variables
    error_message, set_error_message = solara.use_state("")

    selected_layer, set_selected_layer = solara.use_state("Landuse")

    def load(file: FileInfo):
        try:
            json_string = file['data'].decode('utf-8')
            json_hash = hash(json_string)
            json_data = json.loads(json_string)
            print('loaded json data keys',json_data.keys())
            # Load into dataframes
            if "features" in json_data.keys():
                # Add zero metrics to building layer
                if set(json_data['features'][0]['properties'].keys()) == initial_building_columns:
                    for metric in metrics.value.keys():
                        for i in range(len(json_data['features'])):
                            json_data['features'][i]['properties'][metric] = 0 
                    # initial damage states set to zero
                    for i in range(len(json_data['features'])):
                        json_data['features'][i]['properties']['ds'] = 0
 
                df = gpd.GeoDataFrame.from_features(json_data['features'])

                if set(df.columns) == building_columns:
                    building_df.set(df)

                new_center = (df.geometry.centroid.y.mean(), df.geometry.centroid.x.mean())
                center.set(new_center)

            else:
                df = pd.read_json(json_string)

            existing_hashes = [l['hash'] for l in layers.value]
            if json_hash in existing_hashes:
                set_error_message("File already uploaded")
                return
            else:
                new_layer = {'fileinfo': file, 'hash': json_hash, 'visible': solara.reactive(True)}
                df_columns = set(df.columns)
                if df_columns == building_columns:
                    new_layer['name'] = 'Buildings'
                elif df_columns == landuse_columns:
                    new_layer['name'] = 'Landuse'
                    new_layer['geojson'] = ipyleaflet.GeoJSON(data=json_data,
                                            style={'opacity': 1, 'dashArray': '9', 'fillOpacity': 0.5, 'weight': 1},
                                            hover_style={'color': 'white', 'dashArray': '0', 'fillOpacity': 0.5},
                                            style_callback=landuse_colors)    
                    new_layer['geojson'].on_click(landuse_click_handler)

                elif df_columns == intensity_columns:
                    locs = np.array([df.geometry.y.to_list(), df.geometry.x.to_list(), df.im.to_list()]).transpose().tolist()
                    new_layer['name'] = 'Intensity'
                    new_layer['geojson'] = ipyleaflet.Heatmap(locations=locs, radius=radius.value) 
                elif df_columns == household_columns:
                    new_layer['name'] = 'Household'
                elif df_columns == individual_columns:
                    new_layer['name'] = 'Individual'
                elif df_columns == vulnerabillity_columns:
                    new_layer['name'] = 'Vulnerability'
                elif df_columns == fragility_columns:
                    new_layer['name'] = 'Fragility'
                elif df_columns == power_fragility_columns:
                    new_layer['name'] = 'Power Fragility'
                elif df_columns == power_edge_columns:
                    new_layer['name'] = 'Power Links'
                    new_layer['geojson'] = ipyleaflet.GeoJSON(data=json_data)
                elif df_columns == power_node_columns:
                    new_layer['name'] = 'Power Nodes'
                    df['ds'] = 0
                    df['is_damaged'] = False
                    df['is_operational'] = True
                
                new_layer['df'] = solara.reactive(df)
                if new_layer['name'] in [l['name'] for l in layers.value]:
                    for i, l in enumerate(layers.value):
                        if l['name'] == new_layer['name']:
                            layers.value[i] = new_layer
                            break
                    #layers.set(layers.value)
                else:
                    layers.set(layers.value + [new_layer])

            #set_run_allowed(is_ready_to_run())
            set_error_message("")
        except UnicodeDecodeError:
            set_error_message(f'{file["name"]} is not a text file')
        except Exception as e:
            set_error_message(f'file: {file["name"]} Exception:{e}')
        

    def progress(ratio):
        print(f"loading {ratio}")
        loading.set(ratio)

    def is_ready_to_run():
        print('infra.value',infra.value)
        existing_layers = set([l['name'] for l in layers.value])
        missing = []


           
        if hazard.value == "earthquake":
            if "power" in  infra.value:
                missing += list(set(["Power Links","Power Nodes","Intensity","Power Fragility"]) - existing_layers)
            if "buildings" in infra.value:
                missing += list(set(["Buildings","Household","Individual","Intensity","Fragility"]) - existing_layers)
        elif hazard.value == "flood":
            if "power" in  infra.value:
                missing += list(set(["Power Links","Power Nodes","Intensity","Power Vulnerability"]) - existing_layers)
            if "buildings" in infra.value:
                missing += list(set(["Buildings","Household","Individual","Intensity","Vulnerability"]) - existing_layers)
 
        if infra.value == []:
            missing += ['You should select power and/or buildings']
        return missing == [], missing

    def compute():
        print("I'm computing")
        dfs = {l['name']: l['df'].value for l in layers.value}
        dfs_reactive = {l['name']: l['df'] for l in layers.value}

        is_ready, missing = is_ready_to_run()



        if is_ready:
            set_error_message("")

            if 'power' in infra.value:
                
                eq_ds, is_damaged, is_operational = engine.compute_power_infra(dfs['Power Nodes'], 
                                           dfs['Power Links'],
                                           dfs['Intensity'],
                                           dfs['Power Fragility'])
                
                power_node_df =  dfs['Power Nodes'].copy()                         
                power_node_df['ds'] = list(eq_ds)
                power_node_df['is_damaged'] = list(is_damaged)
                power_node_df['is_operational'] = list(is_operational)

                dfs_reactive['Power Nodes'].set(power_node_df)



            if 'buildings' in infra.value:
                computed_metrics, df_metrics, df_bld_hazard = engine.compute(dfs['Buildings'], 
                        dfs['Household'], 
                        dfs['Individual'],
                        dfs['Intensity'],
                        dfs['Fragility'] if hazard.value == "earthquake" else dfs['Vulnerability'], 
                        hazard.value)

                print(computed_metrics)
                updated_df = building_df.value
                for metric in df_metrics.keys():
                    updated_df[metric] = list(df_metrics[metric][metric])
                updated_df['ds'] = list(df_bld_hazard['ds'])
                building_df.set(updated_df)
                
                ((ymin,xmin),(ymax,xmax)) = bounds.value
                for metric in df_metrics.keys():
                    computed_metrics[metric]['value']  = int(updated_df.cx[xmin:xmax,ymin:ymax][metric].sum())

                metrics.set(computed_metrics)
        else:
            set_error_message(f'Layers {missing} are missing')

    with solara.Row():
        with solara.Column():
            solara.FileDrop(label="Drop layers", on_total_progress=progress, on_file=load,lazy=False)
            if loading.value > -1 and loading.value < 100:
                solara.Info(f'Uploading {loading.value}%')

        with solara.Column():
            solara.ToggleButtonsSingle(hazard.value, ["earthquake","flood"], on_value=hazard.set)
            solara.ToggleButtonsMultiple(infra.value,infra_options, on_value=infra.set)
            solara.Button(label="Compute", on_click=compute, outlined=True)
            
        #building_layer = get_building_layer()            
        with solara.GridFixed(columns=4):
            for metric_name, metric in metrics.value.items():
                metric_description = metric['desc']
                if building_df.value is not None and bounds.value is not None:
                    ((ymin,xmin),(ymax,xmax)) = bounds.value
                    value = int(building_df.value.cx[xmin:xmax,ymin:ymax][metric_name].sum())
                else:
                    value = 0
                #with solara.Column(gap="1px",classes=['metriccontainer'],align="center", margin="1"):
                with solara.Tooltip(metric_description):
                    with solara.Column():
                        DialWidget(metric_name, value, max_value=metric['max_value'])
                #solara.HTML(tag="div",unsafe_innerHTML=f'{metric_description}',
                    #            classes=["metricdescription"])
        if error_message != "":
            solara.Error(error_message)
    with solara.Columns([10, 70, 20]):
        ExistingLayers()
        MapComponent()
        solara.DataFrame(df=clicked_df.value, scrollable=True)

    solara.ToggleButtonsSingle(selected_layer, all_layers, on_value=set_selected_layer)
    found_layer = None
    for layer in layers.value:
        if layer['name'] == selected_layer and layer['visible'].value:
            found_layer = layer
            break
    
    if found_layer:
        df = found_layer['df'].value
        print('found layer', found_layer['name'])
        if 'geometry' in list(df.columns) and bounds.value is not None:
            ((ymin,xmin),(ymax,xmax)) = bounds.value
            solara.DataFrame(df=df.cx[xmin:xmax,ymin:ymax].drop(columns='geometry'))
        else:
            solara.DataFrame(df=df)
        
    else:
        solara.Info(f'{selected_layer} is not uploaded or set to invisible')
@solara.component
def Page():
    solara.Style(css)
    VisioningScenarioViewer()
