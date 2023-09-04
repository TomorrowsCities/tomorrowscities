import solara
from solara.components.file_drop import FileInfo
import os
os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
import pandas as pd
import json
import numpy as np
import ipyleaflet
from engine import compute_flood
import random
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import math

plt.switch_backend("agg")

# Static parameters
initial_building_columns = set(['zoneID', 'bldID', 'nHouse', 'residents', 'specialFac', 'expStr', 'fptarea', 'repValue'])
building_columns = set(['geometry','metric1','metric2','metric3','metric4','metric5','metric6','metric7','zoneID', 'bldID', 'nHouse', 'residents', 'specialFac', 'expStr', 'fptarea', 'repValue'])
landuse_columns = set(['geometry', 'zoneID', 'LuF', 'population', 'densityCap', 'floorARat', 'setback', 'avgIncome'])
household_columns = set(['hhID', 'nInd', 'income', 'bldID', 'CommFacID'])
individual_columns = set(['indivId', 'hhID', 'gender', 'age', 'eduAttStat', 'head', 'indivFacID'])
intensity_columns = set(['geometry','im'])
vulnerabillity_columns = set(['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5','hw6'])
all_layers = ["Landuse", "Buildings", "Household","Individual","Intensity","Vulnerability"]
metrics_template = {"metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": 0},
            "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": 0},
            "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": 0},
            "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 0},
            "metric5": {"desc": "Number of homeless households", "value": 0, "max_value": 0},
            "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": 0},
            "metric7": {"desc": "Population displacement", "value": 0, "max_value": 0},}

layers = solara.reactive([])

base_map = ipyleaflet.basemaps.OpenStreetMap.BZH

default_zoom = 14
default_radius = 10
default_center = (41.03,28.94)

center = solara.reactive(default_center)
zoom = solara.reactive(default_zoom)
bounds = solara.reactive(None)
radius = solara.reactive(default_radius)

building_df = solara.reactive(None)
landuse_geojson = solara.reactive(None)
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
        print(feature['properties'])
        #damage = 0
        #for metric in metrics_template.keys():
        #    damage += feature['properties'][metric]
        # metric5 is the number of damaged households
        if feature['properties']['metric5'] > 0:
            return {'fillColor': 'red', 'color': 'red'}
        else:
            return {'fillColor': 'gray', 'color': 'blue'}
         
@solara.component
def MapComponent():

    extra_layers = [l['geojson'] for l in layers.value if 'geojson' in l.keys()]

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
def DialWidget(desc, value, max_value=10000):
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

    ax.text(0,0.5,value,fontdict={'fontsize':20},verticalalignment="center",
        horizontalalignment="center",color="black")
    ax.set_xlim(-1.1,1.1)
    ax.set_ylim(-0.2,1.2)
    solara.FigureMatplotlib(fig)

@solara.component
def VisioningScenarioViewer():

    # State variables
    loading, set_loading = solara.use_state(-1)
    error_message, set_error_message = solara.use_state("")

    selected_layer, set_selected_layer = solara.use_state(None)
    metrics, set_metrics = solara.use_state(metrics_template)

    def load(file: FileInfo):
        try:
            json_string = file['data'].decode('utf-8')
            json_hash = hash(json_string)
            json_data = json.loads(json_string)
            print(json_data.keys())
            # Load into dataframes
            if "features" in json_data.keys():
                # Add zero metrics to building layer
                if set(json_data['features'][0]['properties'].keys()) == initial_building_columns:
                    for metric in metrics.keys():
                        for i in range(len(json_data['features'])):
                            json_data['features'][i]['properties'][metric] = 0 

                df = gpd.GeoDataFrame.from_features(json_data['features'])

                if set(df.columns) == building_columns:
                    building_df.set(df)

                if set(df.columns) == landuse_columns:
                    landuse_geojson.set(json_data)


                new_center = (df.geometry.centroid.y.mean(), df.geometry.centroid.x.mean())
                center.set(new_center)
                print(df.head())
                print(df.columns)
            else:
                df = pd.read_json(json_string)

            existing_hashes = [l['hash'] for l in layers.value]
            if json_hash in existing_hashes:
                set_error_message("File already uploaded")
                return
            else:
                new_layer = {'fileinfo': file, 'df': df, 'hash': json_hash}
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
                           
                layers.set(layers.value + [new_layer])
            print(file['name'], list(df.columns))

            #set_run_allowed(is_ready_to_run())
            set_error_message("")
        except UnicodeDecodeError:
            set_error_message(f'{file["name"]} is not a text file')
        except Exception as e:
            set_error_message(f'file: {file["name"]} Exception:{e}')
        

    def progress(ratio):
        print(f"loading {ratio}")
        set_loading(ratio)

    def is_ready_to_run():
        layer_names = set([l['name'] for l in layers.value])
        return set(all_layers) == layer_names

    def get_building_layer():
        dfs = {l['name']: l for l in layers.value}
        if 'Buildings' in dfs.keys():
            return dfs['Buildings']
        else:
            return None

    def compute():
        print("I'm computing")
        dfs = {l['name']: l['df'] for l in layers.value}
        print(dfs.keys())

        if is_ready_to_run():
            metrics, df_metrics = compute_flood(dfs['Buildings'], 
                      dfs['Household'], 
                      dfs['Individual'],
                      dfs['Intensity'],
                      dfs['Vulnerability'], 
                      "flood")
            print(metrics)
            set_metrics(metrics['metrics'])

            updated_df = building_df.value
            for metric in df_metrics.keys():
                updated_df[metric] = list(df_metrics[metric][metric])
            building_df.set(updated_df)

            #building_layer['geodata'] = ipyleaflet.GeoData(geo_dataframe=building_df,
            #                                                  hover_style={'color': 'red', 'dashArray': '0', 'fillOpacity': 0.5},
            #                                                  style_callback=building_colors)
            #layers.set(layers)

    with solara.Row():
        solara.FileDrop(label="Drop layers", on_total_progress=progress, on_file=load,lazy=False)
        solara.Info(f'Uploading {loading}%')
        if error_message != "":
            solara.Error(error_message)
        solara.Button(label="Compute", on_click=compute, outlined=True)
        
        building_layer = get_building_layer()
        for metric in metrics.keys():
            if building_df.value is not None and bounds is not None:
                ((ymin,xmin),(ymax,xmax)) = bounds.value
                value = int(building_df.value.cx[xmin:xmax,ymin:ymax][metric].sum())
            else:
                value = 0
            DialWidget(metric, value, max_value=10000)
            #solara.Info(label=f'{metric}: {value}', dense=True)

    with solara.Columns([80, 20]):
        MapComponent()
        solara.DataFrame(df=clicked_df.value, scrollable=True)

    with solara.Card("Dataframes"):
        solara.ToggleButtonsSingle(selected_layer, all_layers, on_value=set_selected_layer)
        solara.Markdown(f"**Selected**: {selected_layer}")
        found_layer = None
        for layer in layers.value:
            if layer['name'] == selected_layer:
                found_layer = layer
                break
        
        if found_layer:
            df = found_layer['df']

            # Generate new dataframe
            if 'geometry' in list(df.columns):
                df_new = gpd.GeoDataFrame(df)
            else:
                df_new = pd.DataFrame(df)

            # Filter geopandas
            if 'geometry' in list(df.columns):
                ((ymin,xmin),(ymax,xmax)) = bounds.value
                df_filtered = df_new.cx[xmin:xmax,ymin:ymax]
                if selected_layer == 'Intensity':
                    solara.DataFrame(df=pd.DataFrame(df_filtered))
                else:
                    solara.DataFrame(df=pd.DataFrame(df_filtered.drop(columns='geometry')))
            else:
                solara.DataFrame(df=df_new)
        else:
            solara.Info(f'No data uploaded yet for layer: {selected_layer}')
@solara.component
def Page():
    VisioningScenarioViewer()
