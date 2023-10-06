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

app_data = solara.reactive({'df': solara.reactive(None), 
                            'gdf': solara.reactive(None),
                            'selected_columns': solara.reactive([]),
                            'lat': solara.reactive(None),
                            'lon': solara.reactive(None),
                            'im': solara.reactive(None)})

def import_data(fileinfo: solara.components.file_drop.FileInfo):
    data = fileinfo['data']
    extension = fileinfo['name'].split('.')[-1]
    if extension == 'xlsx':
        df = pd.read_excel(data)
    elif extension == 'csv':
        df = pd.read_csv(data)
    else:
        json_string = data.decode('utf-8')
        json_data = json.loads(json_string)
        if "features" in json_data.keys():
            df = gpd.GeoDataFrame.from_features(json_data['features'])
        else:
            df = pd.read_json(json_string)

    df.columns = df.columns.str.lower()

    return df


@solara.component
def FileDropZone():
    total_progress, set_total_progress = solara.use_state(-1)
    fileinfo, set_fileinfo = solara.use_state(None)
    result, set_result = solara.use_state(solara.Result(True))

    def load():
        print('loading')
        if fileinfo is not None:
            print('processing file')
            df = import_data(fileinfo)
            print('importing done')
            if df is not None:
                app_data.value['df'].set(df)
            else:
                return False
        return True
        
    def progress(x):
        set_total_progress(x)

    def on_file_deneme(f):
        set_fileinfo(f)
    
    result = solara.use_thread(load, dependencies=[fileinfo])

    solara.Markdown("Step1: Drag and drop your Excel file to the below area.")
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
            solara.Text("Reading the contents")
            solara.ProgressLinear(value=True)

@solara.component
def DataframeDisplayer():
    if app_data.value['df'].value is not None:
        solara.DataFrame(app_data.value['df'].value)

@solara.component
def FieldSelector():
    solara.Markdown("Step 2: Select the field names")
    if app_data.value['df'].value is not None:
        solara.Text("lat")
        solara.ToggleButtonsSingle(value=app_data.value['lat'].value, values=list(app_data.value['df'].value.columns), on_value=app_data.value['lat'].set)
        solara.Text("lon")
        solara.ToggleButtonsSingle(value=app_data.value['lon'].value, values=list(app_data.value['df'].value.columns),on_value=app_data.value['lon'].set)
        solara.Text("im")
        solara.ToggleButtonsSingle(value=app_data.value['im'].value, values=list(app_data.value['df'].value.columns),on_value=app_data.value['im'].set)

@solara.component
def Downloader():
    error_msg, set_error_msg = solara.use_state(None)
    success_msg, set_success_msg = solara.use_state(None)
    def generate():
        set_error_msg(None)
        set_success_msg(None)
        if app_data.value['df'].value is not None:
            if app_data.value['lat'].value is not None:
                if app_data.value['lon'].value is not None:
                    if app_data.value['im'].value is not None:
                        try:
                            lat = app_data.value['lat'].value
                            lon = app_data.value['lon'].value
                            im = app_data.value['im'].value
                            df_conv = app_data.value['df'].value[[lat,lon,im]]
                            df_conv = df_conv.rename(columns={lat:'lat',lon:'lon',im:'im'})
                            gdf = gpd.GeoDataFrame(df_conv[['im']], 
                                geometry = gpd.points_from_xy(df_conv[lon], df_conv[lat], crs="EPSG:4326"))
                            app_data.value['gdf'].set(gdf)
                            set_success_msg("Your file is ready")
                            set_error_msg(None)
                        except Exception as e:
                            app_data.value['gdf'].set(None)
                            set_error_msg(repr(e))
                            set_success_msg(None)

    solara.Markdown("Step 3: Clict to generate GeoJSON")                    
    solara.Button("Generate GeoJSON", icon_name="mdi-cloud-download-outline", color="primary", on_click=generate)
    if error_msg is not None:
        solara.Error(error_msg)
    if success_msg is not None:
        solara.Success(success_msg)
    if app_data.value['gdf'].value is not None:
        file_object = app_data.value['gdf'].value .to_json()
        with solara.FileDownload(file_object, "intensity_blabla.geojson", mime_type="application/geo+json"):
            solara.Button("Click to Downlaod genereated GeoJSON", icon_name="mdi-cloud-download-outline", color="primary")
@solara.component
def Utilities():
    with solara.Columns([30,80]):
        FileDropZone()
        FieldSelector()
    Downloader()
    DataframeDisplayer()
    

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

    Utilities()
