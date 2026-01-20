import solara
import time
import random
import json
import pandas as pd
import os
from scipy.stats import norm


import solara.lab
os.environ['USE_PYGEOS'] = '0'
import geopandas as gpd
from typing import Tuple, Optional
import ipyleaflet
from ipyleaflet import AwesomeIcon, Marker
import numpy as np
import logging, sys
#logging.basicConfig(stream=sys.stderr, level=logging.INFO)

from ..backend.engine import compute, compute_power_infra

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
        with solara.FileDownload(file_object, "converted.geojson", mime_type="application/geo+json"):
            solara.Button("Click to Downlaod genereated GeoJSON", icon_name="mdi-cloud-download-outline", color="primary")
            DataframeDisplayer()
@solara.component
def JsonToCsvConverter():
    content, set_content = solara.use_state(None)
    filename, set_filename = solara.use_state(None)
    error, set_error = solara.use_state(None)
    
    def on_file(f):
        set_filename(f["name"])
        set_content(f["data"])
        set_error(None)

    with solara.Details("🔁 JSON → CSV Converter"):
        solara.FileDrop(on_file=on_file, lazy=False)
        if filename:
            solara.Text(f"Selected file: {filename}")
        
        if content:
            try:
                from io import BytesIO
                df = pd.read_json(BytesIO(content))
                csv_content = df.to_csv(index=False)
                with solara.FileDownload(data=csv_content, filename="converted.csv", label="⬇️ Download CSV"):
                    pass
            except Exception as e:
                solara.Error(f"Error: {e}")

@solara.component
def CsvToJsonConverter():
    content, set_content = solara.use_state(None)
    filename, set_filename = solara.use_state(None)
    error, set_error = solara.use_state(None)
    
    def on_file(f):
        set_filename(f["name"])
        try:
            # Solara file drop returns bytes, so we might need to decode if read_csv expects string/buffer
            # pd.read_csv can accept bytes
            set_content(f["data"])
            set_error(None)
        except Exception as e:
            set_error(str(e))

    with solara.Details("🔁 CSV → JSON Converter"):
        solara.FileDrop(on_file=on_file, lazy=False)
        if filename:
            solara.Text(f"Selected file: {filename}")
        
        if content:
            try:
                # Assuming content is bytes
                from io import BytesIO
                df = pd.read_csv(BytesIO(content))
                json_content = df.to_json(orient="columns", force_ascii=False)
                with solara.FileDownload(data=json_content, filename="converted.json",  mime_type="application/json", label="⬇️ Download JSON"):
                    pass
            except Exception as e:
                solara.Error(f"Error: {e}")

@solara.component
def ExcelToGeoJsonConverter():
    with solara.Details("🔁 EXCEL → GEOJSON Converter"):
        with solara.Columns([30,80]):
            FileDropZone()
            FieldSelector()
        Downloader()
        
@solara.component
def Utilities():
    
    with solara.Column():
        ExcelToGeoJsonConverter()
        JsonToCsvConverter()
        CsvToJsonConverter()
    

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
    solara.Title(" ")

    Utilities()

import os
from pathlib import Path
from typing import Callable, List, Optional, Union, cast
import ipyvuetify as vy
import traitlets
import solara
from solara.components import Div

import boto3

extension_list = ['xls','xlsx','geojson','json','xml','tif','tiff']
extension_list_w_dots = [f'.{e}' for e in extension_list] 

class FileListWidget(vy.VuetifyTemplate):
    template_file = (__file__, "file_list_widget.vue")

    files = traitlets.List().tag(sync=True)
    clicked = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    double_clicked = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    scroll_pos = traitlets.Int(allow_none=True).tag(sync=True)

    def test_click(self, path: Union[Path, str], double_click=False):
        """Simulate a click or double click at the Python side"""
        matches = [k for k in self.files if k["name"] == str(path)]
        if len(matches) == 0:
            names = [k["name"] for k in self.files]
            raise NameError(f"Could not find {path}, possible filenames: {names}")
        item = matches[0]
        if double_click:
            self.double_clicked = item
        else:
            self.clicked = item

    def __contains__(self, name):
        """Test if filename/directory name is in the current directory."""
        return name in [k["name"] for k in self.files]

@solara.component
def S3FileBrowser(
    storage,
    directory: Union[None, str, Path, solara.Reactive[Path]] = None,
    on_directory_change: Callable[[Path], None] = None,
    on_path_select: Callable[[Optional[Path]], None] = None,
    on_file_open: Callable[[Path], None] = None,
    filter: Callable[[Path], bool] = lambda x: True,
    directory_first: bool = False,
    on_file_name: Callable[[str], None] = None,
    start_directory=None,
    can_select=False,
):  
    print("==================",storage)

    def get_s3_file_list():
        file_list = []
        print("==================....",storage)

        client = storage.get_client()
        objects = client.list_objects(Bucket=storage.bucket_name)
        for obj in objects.get('Contents', []):
            extension = obj["Key"].lower().split('.')[-1] 
            if extension in extension_list:
                file_list.append(obj["Key"])
        return [f'/{f}' for f in file_list]

    if start_directory is not None:
        directory = start_directory  # pragma: no cover
    if directory is None:
        directory = '/' # pragma: no cover
    if isinstance(directory, str):
        directory = Path(directory)
    current_dir = solara.use_reactive(directory)
    selected, set_selected = solara.use_state(None)
    double_clicked, set_double_clicked = solara.use_state(None)
    warning, set_warning = solara.use_state(cast(Optional[str], None))
    scroll_pos_stack, set_scroll_pos_stack = solara.use_state(cast(List[int], []))
    scroll_pos, set_scroll_pos = solara.use_state(0)
    selected, set_selected = solara.use_state(None)
    s3_file_list, set_s3_file_list = solara.use_state(get_s3_file_list())
    storage, set_storage = solara.use_state_or_update(storage)

    def s3_is_file(path):
        for extension in extension_list:
            if path.endswith(f'.{extension}'):
                return True
        return None

    def s3_list_dir(path, filter: Callable[[Path], bool] = lambda x: True, directory_first: bool = False) -> List[dict]:
        os_path = Path(path)
        matched_paths = [f for f in s3_file_list if f.startswith(str(path))]
        results = set()
        for p in matched_paths:
            parts = p.split('/')
            for i in range(len(parts)+1):
                candidate = Path("/".join(parts[:i]))
                if candidate.parent == os_path:
                    results.add(candidate.name)
        
        results_extended = [{'name': r, 'is_file': s3_is_file(r) } for r in results]
        sorted_files = sorted(results_extended, key=lambda item: (item["is_file"] == directory_first, item["name"].lower()))
        return sorted_files

    def change_dir(new_dir: str):
        has_access = False
        for f in s3_file_list:
            if f.startswith(new_dir):
                has_access = True
                break
        if has_access:
            current_dir.value = Path(new_dir)
            if on_directory_change:
                on_directory_change(Path(new_dir))
            set_warning(None)
            return True
        else:
            set_warning(f"[no read access to {new_dir}]")

    def on_item(item, double_click):
        if item is None:
            if can_select and on_path_select:
                on_path_select(None)
            return
        if item["name"] == "..":
            current_dir_str = str(current_dir.value)
            new_dir = current_dir_str[: current_dir_str.rfind('/')]
            if new_dir == "":
                new_dir = "/"
            action_change_directory = (can_select and double_click) or (not can_select and not double_click)
            if action_change_directory and change_dir(new_dir):
                if scroll_pos_stack:
                    last_pos = scroll_pos_stack[-1]
                    set_scroll_pos_stack(scroll_pos_stack[:-1])
                    set_scroll_pos(last_pos)
                set_selected(None)
                set_double_clicked(None)
                if on_path_select and can_select:
                    on_path_select(None)
            if can_select and not double_click:
                if on_path_select:
                    on_path_select(Path(new_dir))
            return

        path = os.path.join(current_dir.value, item["name"])
        is_file = item["is_file"]
        if (can_select and double_click) or (not can_select and not double_click):
            if is_file:
                if on_file_open:
                    on_file_open(Path(path))
                if on_file_name is not None:
                    on_file_name(path)
            else:
                if change_dir(path):
                    set_scroll_pos_stack(scroll_pos_stack + [scroll_pos])
                    set_scroll_pos(0)
                set_selected(None)
            set_double_clicked(None)
            if on_path_select and can_select:
                on_path_select(None)
        elif can_select and not double_click:
            if on_path_select:
                on_path_select(Path(path))
        else:  # not can_select and double_click is ignored
            raise RuntimeError("Combination should not happen")  # pragma: no cover

    def on_click(item):
        set_selected(item)
        on_item(item, False)

    def on_double_click(item):
        set_double_clicked(item)
        if can_select:
            on_item(item, True)
        # otherwise we can ignore it, single click will handle it

    files = [{"name": "..", "is_file": False}] + s3_list_dir(current_dir.value, filter=filter, directory_first=directory_first)
    with Div(class_="solara-file-browser") as main:
        Div(children=['aws s3:'+str(current_dir.value)])
        FileListWidget.element(
            files=files,
            selected=selected,
            clicked=selected,
            on_clicked=on_click,
            double_clicked=double_clicked,
            on_double_clicked=on_double_click,
            scroll_pos=scroll_pos,
            on_scroll_pos=set_scroll_pos,
        ).key("FileList")
        if warning:
            Div(style_="font-weight: bold; color: red", children=[warning])

    return main

@solara.component
def FragilityFunctionDisplayer(vuln_func):
    vuln_func, _ = solara.use_state_or_update(vuln_func)

    x = vuln_func['imls']
    y1 = vuln_func['slight']
    y2 = vuln_func['moderate']
    y3 = vuln_func['extensive']
    y4 = vuln_func['complete']

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
                'position': 'left',
                'alignTicks': True,
                'axisLine': {
                    'show': True,
                    'lineStyle': {'color': 'green'}}
            },
            {
                'type': 'value',
                'position': 'left',
                'alignTicks': True,
                'axisLine': {
                    'show': True,
                    'lineStyle': {'color': 'blue'}}
            },
            {
                'type': 'value',
                'position': 'left',
                'alignTicks': True,
                'axisLine': {
                    'show': True,
                    'lineStyle': {'color': 'yellow'}}
            },
            {
                'type': 'value',
                'position': 'left',
                'alignTicks': True,
                'axisLine': {
                    'show': True,
                    'lineStyle': {'color': 'purple'}}
            },
        ],
        'series': [
            {
            'name': 'slight',
            'data': list(y1),
            'type': 'line',
            'yAxisIndex': 0
            },
            {
            'name': 'moderate',
            'data': list(y2),
            'type': 'line',
            'yAxisIndex': 1
            },
            {
            'name': 'extensive',
            'data': list(y3),
            'type': 'line',
            'yAxisIndex': 2
            },
            {
            'name': 'complete',
            'data': list(y4),
            'type': 'line',
            'yAxisIndex': 3
            },
        ],
    }
    solara.FigureEcharts(option=options) 

@solara.component
def PowerFragilityDisplayer(data, items_per_page=5):
    vuln_strings = list(data['vuln_string'])
    vuln_string, set_vuln_string  = solara.use_state_or_update(vuln_strings[0])

    # Range barrowed from GEM fragility files
    im_range = np.array([0.05,0.0561725,0.0631069,0.0708974,0.0796497,0.0894824,0.100529,0.112939,0.126881,0.142545,0.160142,0.179911,0.202121,0.227073,0.255105,0.286598,0.321978,0.361726,0.406381,0.456548,0.512909,0.576227,0.647362,0.727278,0.81706,0.917925,1.03124,1.15855,1.30157,1.46225,1.64276,1.84556,2.07339,2.32935,2.61691,2.93997,3.3029,3.71064,4.16872,4.68335,5.2615,5.91103,6.64074,7.46054,8.38154,9.41623,10.5787,11.8846,13.3517,15])
    # Convert to in g units and take logarithm
    im_log_g_range = np.log(im_range)

    frgl_funcs = {}
    for i, row in data.iterrows():
        id = row['vuln_string']
        frgl_func = dict()
        frgl_func['id'] = id
        frgl_func['imt'] = 'pga (g)'
        frgl_func['imls'] = im_range
        frgl_func['slight'] = norm.cdf(im_log_g_range, np.log(row['med_slight']), row['beta_slight'])
        frgl_func['moderate'] = norm.cdf(im_log_g_range, np.log(row['med_moderate']), row['beta_moderate'])
        frgl_func['extensive'] = norm.cdf(im_log_g_range, np.log(row['med_extensive']), row['beta_extensive'])
        frgl_func['complete'] = norm.cdf(im_log_g_range, np.log(row['med_complete']), row['beta_complete'])
        frgl_funcs[id] = frgl_func

    with solara.lab.Tabs():
        with solara.lab.Tab(label="Table"):
            solara.DataFrame(data, items_per_page=items_per_page)
        with solara.lab.Tab(label="Plot"):
            with solara.Column():
                FragilityFunctionDisplayer(frgl_funcs[vuln_string])
                solara.Select(label='vuln_string',value=vuln_string, values=vuln_strings,
                                on_value=set_vuln_string)


lbl_2_str = {
    'landuse': {
        'luf': {'name': 'Land Use Type',
                'mapping': {}},
        'avgincome': {'name': 'Average Income',
                'mapping': {'highIncome': 'High Income', 'lowIncomeA': 'Low Income', 'lowIncomeB': 'Low Income', 'midIncome': 'Moderate Income'}},
        },
    'building': {
        'ds': {'name': 'Damage State',
                'mapping': {0: '0-No',1: '1-Slight', 2:'2-Moderate',3:'3-Extensive',4:'4-Complete'}},
        'specialfac': {'name': 'Special Facility',
                'mapping': {0: 'Residential', 1: 'Educational', 2:'Health'}},
        'nhouse': {'name': 'Number of Households',
                'mapping': {}},
        'residents': {'name': 'Number of Residents',
                'mapping': {}},
        'occupancy': {'name': 'Occupancy',
                'mapping': {'Com': 'Commercial','Res': 'Residential','Edu': 'Education', 'Hea': 'Hospital', 'Ind': 'Industrial'}},
        'storeys': {'name': 'Storeys',
                'mapping': {}},
        'code_level': {'name': 'Code Level',
                'mapping': {'HC': '1-High Code', 'MC': '2-Moderate Code', 'LC': '3-Low Code'}},
        'material': {'name': 'Material',
                'mapping': {}},
        },
    'tally_minimal': {
        'ds': {'name': 'Damage State',
                'mapping': {0: '0-No',1: '1-Slight', 2:'2-Moderate',3:'3-Extensive',4:'4-Complete'}},
        'income': {'name': 'Income Level',
                   'mapping': {'highIncome': 'High Income', 'lowIncomeA': 'Low Income A', 'lowIncomeB': 'Low Income', 'midIncome': 'Moderate Income'}},
        'material': {'name': 'Material',
                   'mapping': {}},
        'gender': {'name': 'Gender',
                   'mapping': {'1': 'Male', '2': 'Female'}},
        'age': {'name': 'Age',
                   'mapping': {'1': '0-3', '2': '4-6', '3': '7-10', '4': '11-14', '5': '15-18', '6': '19-22', '7': '23-26', '8': '27-30', '9': '31-35', '10': '32-36', '11': '36-40', '12': '40-44', '13': '45-49', '14': '50-54', '15': '55-59', '16': '60-64', '17': '65-69', '17': '70-74', '18': '75-79', '19': '80-84', '20': '85+'}},
        'head': {'name': 'Head of Household Status',
                   'mapping': {'0': 'No', '1':'Yes'}},
        'eduattstat': {'name': 'Education Status',
                   'mapping': {'1': '1-None', '2': '2-Primary', '3': '3-Elementary', '4': '4-High School', '5': '5-University'}},
        'luf': {'name': 'Land Use',
                   'mapping': {}},
        'occupancy': {'name': 'Occupancy',
                'mapping': {'Com': 'Commercial','Res': 'Residential', 'Edu': 'Education', 'Hea': 'Hospital', 'Ind': 'Industrial'}},
        },
    }


def convert_data_for_filter_view(data, layer_name):
    if data is None:
        return None
    
    if layer_name not in lbl_2_str.keys():
        return data
    
    # Take the columns
    df = data[lbl_2_str[layer_name].keys()]

    for col, colinfo in lbl_2_str[layer_name].items():
        if len(colinfo['mapping']) > 0:
            df.replace({col: colinfo['mapping']}, inplace=True)

    renaming = {col: colinfo['name'] for col, colinfo in lbl_2_str[layer_name].items()}
    df.rename(columns=renaming, inplace=True)


    return df