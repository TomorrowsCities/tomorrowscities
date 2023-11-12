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
    s3, bucket_name,
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
    """File/directory browser at the server side.

    There are two modes possible

     * `can_select=False`
        * `on_file_open`: Triggered when **single** clicking a file or directory.
        * `on_path_select`: Never triggered
        * `on_directory_change`: Triggered when clicking a directory
     * `can_select=True`
        * `on_file_open`: Triggered when **double** clicking a file or directory.
        * `on_path_select`: Triggered when clicking a file or directory
        * `on_directory_change`: Triggered when double clicking a directory

    ## Arguments

     * `directory`: The directory to start in. If `None` the current working directory is used.
     * `on_directory_change`: Depends on mode, see above.
     * `on_path_select`: Depends on mode, see above.
     * `on_file_open`: Depends on mode, see above.
     * `filter`: A function that takes a `Path` and returns `True` if the file/directory should be shown.
     * `directory_first`: If `True` directories are shown before files. Default: `False`.
     * `on_file_name`: (deprecated) Use on_file_open instead.
     * `start_directory`: (deprecated) Use directory instead.
    """
    

    def get_s3_file_list():
        file_list = []
        objects = s3.list_objects(Bucket=bucket_name)
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


