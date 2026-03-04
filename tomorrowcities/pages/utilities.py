import solara
import time
import random
import json
import pandas as pd
import os
import re
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
from ..components.file_drop import FileDrop, FileDropMultiple

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
        import io
        df = pd.read_excel(io.BytesIO(data))
    elif extension == 'csv':
        import io
        df = pd.read_csv(io.BytesIO(data))
    else:
        json_string = data.decode('utf-8')
        json_data = json.loads(json_string)
        if "features" in json_data.keys():
            df = gpd.GeoDataFrame.from_features(json_data['features'])
        else:
            import io
            df = pd.read_json(io.StringIO(json_string))

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
    FileDrop(on_total_progress=progress,
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

    with solara.Details("JSON → CSV Converter"):
        FileDrop(on_file=on_file, lazy=False)
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

    with solara.Details("CSV → JSON Converter"):
        FileDrop(on_file=on_file, lazy=False)
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
    with solara.Details("EXCEL → GEOJSON Converter"):
        with solara.Columns([30,80]):
            FileDropZone()
            FieldSelector()
        Downloader()

@solara.component
def FloodVulnerabilityTemplateGenerator():
    filename, set_filename = solara.use_state(None)
    df, set_df = solara.use_state(None)
    selected_col, set_selected_col = solara.use_state(None)
    error, set_error = solara.use_state(None)

    def natural_sort_key(s):
        parts = s.split('+')
        key = []
        
        # Custom mapping for LC, MC, HC order (LC < MC < HC)
        code_order = {'lc': '1_lc', 'mc': '2_mc', 'hc': '3_hc'}
        
        for part in parts:
            part_lower = part.lower()
            if part_lower in code_order and len(code_order[part_lower]) > 0:
                 key.append([code_order[part_lower]])
            else:
                 sub_parts = [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', part) if c]
                 key.append(sub_parts)
        
        # Prioritize 4th component (Occupancy) over 3rd (Height) if 4 components exist
        if len(key) >= 4:
            return key[:2] + [key[3]] + [key[2]] + key[4:]
        return key

    def on_file(f):
        set_filename(f["name"])
        set_error(None)
        set_df(None)
        set_selected_col(None)
        
        try:
            # Handle GeoJSON
            if f["name"].lower().endswith('.geojson') or f["name"].lower().endswith('.json'):
                json_string = f["data"].decode('utf-8')
                json_data = json.loads(json_string)
                if "features" in json_data.keys():
                    gdf = gpd.GeoDataFrame.from_features(json_data['features'])
                    set_df(gdf)
                else:
                    set_error("Invalid GeoJSON: 'features' key missing")
            # Handle Zip (Shapefile)
            elif f["name"].lower().endswith('.zip'):
                from io import BytesIO
                gdf = gpd.read_file(BytesIO(f["data"]))
                set_df(gdf)
            else:
                 set_error("Unsupported file format. Please upload GeoJSON or Zipped Shapefile.")
        except Exception as e:
            set_error(f"Error reading file: {e}")

    with solara.Details("Flood Vulnerability Template Generator"):
        solara.Markdown("Step 1: Drag and drop your building data in GeoJSON or Zipped Shapefile format.")
        FileDrop(on_file=on_file, lazy=False)
        if filename:
            solara.Text(f"Selected file: {filename}")
        
        if error:
            solara.Error(error)

        if df is not None:
             solara.Markdown("Step 2: Select the ‘Exposure string’ attribute.")
             cols = list(df.columns)
             solara.Select(label="Exposure String", value=selected_col, values=cols, on_value=set_selected_col)

             if selected_col:
                 try:
                     unique_vals = sorted(df[selected_col].astype(str).unique(), key=natural_sort_key)
                     target_cols = ['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5', 'hw6']
                     new_df = pd.DataFrame(columns=target_cols)
                     new_df['expstr'] = unique_vals
                     
                     from io import BytesIO
                     output = BytesIO()
                     new_df.to_excel(output, index=False)
                     excel_content = output.getvalue()
                     
                     solara.Div(style={"margin-top": "40px"})
                     solara.Markdown("Step 3: Download XLSX")
                     with solara.FileDownload(data=excel_content, filename="flood_vulnerability_template.xlsx", label="⬇️ Download XLSX"):
                        pass
                 except Exception as e:
                     solara.Error(f"Error processing data: {e}")
             
             solara.Div(style={"margin-bottom": "50px"})

        
def classify_dataset(df, filename):
    cols = set(df.columns)
    name = filename.lower()
    
    # Try filename heuristics first if distinct
    if 'landuse' in name or 'luf' in cols or 'densitycap' in cols: return 'landuse'
    
    # Building requires residents, nhouse, fptarea, etc.
    if 'building' in name or 'fptarea' in cols or ('expstr' in cols and 'nhouse' in cols) or ('residents' in cols): return 'building'
    
    # Household requires commfacid or nind
    if 'household' in name or 'commfacid' in cols or 'nind' in cols: return 'household'
    
    # Individual requires eduattstat or gender
    if 'individual' in name or 'eduattstat' in cols or 'gender' in cols: return 'individual'
    
    # fallback to column overlap
    rules = [
        ('landuse', {'zoneid', 'luf', 'densitycap', 'avgincome'}),
        ('building', {'residents', 'fptarea', 'repvalue', 'nhouse', 'expstr', 'bldid', 'specialfac'}),
        ('household', {'hhid', 'nind', 'income', 'bldid', 'commfacid'}),
        ('individual', {'individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid'})
    ]
    best_match = "unknown"
    max_overlap = 0
    for dtype, req_cols in rules:
        overlap = len(cols.intersection(req_cols))
        if overlap > max_overlap:
            max_overlap = overlap
            best_match = dtype
            
    if max_overlap < 2:
        return "unknown"
        
    return best_match

@solara.component
def LanduseExposureCheck():
    messages, set_messages = solara.use_state([])
    is_processing, set_is_processing = solara.use_state(False)
    file_drop_key, set_file_drop_key = solara.use_state(0)

    def process_files(files):
        set_is_processing(True)
        set_messages([])
        
        msgs = []
        datasets = {}
        
        for f in files:
            msgs.append(("info", f"Reading {f['name']}..."))
        set_messages(msgs.copy())
        
        msgs = [] # Reset to collect actual status
        for f in files:
            try:
                df = import_data(f)
                if df is None:
                    msgs.append(("error", f"Could not extract dataframe from {f['name']}."))
                    continue
                
                dtype = classify_dataset(df, f['name'])
                if dtype == "unknown":
                    msgs.append(("error", f"File '{f['name']}' does not contain required attributes for landuse, building, household, or individual data. Check attributes!"))
                elif dtype in datasets:
                    msgs.append(("warning", f"Multiple files detected for {dtype} ({f['name']}). Ignoring."))
                else:
                    datasets[dtype] = df
                    msgs.append(("success", f"Loaded '{f['name']}' successfully as {dtype}."))
            except Exception as e:
                msgs.append(("error", f"Error reading {f['name']}: {e}"))

        # Validate presence of 4 datasets
        required = ['landuse', 'building', 'household', 'individual']
        missing = [d for d in required if d not in datasets]
        if missing:
            msgs.append(("error", f"Missing datasets: {', '.join(missing)}."))

        if not missing:
            msgs.append(("success", "All 4 required datasets are loaded. Proceeding with validation..."))

        # LANDUSE
        if 'landuse' in datasets:
            lu_df = datasets['landuse']
            req_lu = {'geometry', 'zoneid', 'luf', 'population', 'densitycap', 'avgincome'}
            missing_cols = req_lu - set(lu_df.columns)
            if missing_cols:
                msgs.append(("error", f"Landuse is missing required attributes: {', '.join(missing_cols)}"))
            
            if 'zoneid' in lu_df.columns:
                if not lu_df['zoneid'].is_unique:
                    msgs.append(("error", "Landuse 'zoneid' values are not unique."))
                else:
                    msgs.append(("success", "Landuse 'zoneid' uniqueness verified."))
            
            if 'densitycap' in lu_df.columns and 'avgincome' in lu_df.columns:
                # convert densitycap to numeric
                lu_df['densitycap'] = pd.to_numeric(lu_df['densitycap'], errors='coerce')
                
                invalid_density = lu_df[lu_df['densitycap'] < 0]
                if not invalid_density.empty:
                    msgs.append(("error", "Landuse 'densitycap' contains negative values."))
                else:
                    msgs.append(("success", "Landuse 'densitycap' >= 0 verified."))
                    
                valid_incomes = {"lowIncomeA", "lowIncomeB", "midIncome", "highIncome"}
                mask = lu_df['densitycap'] > 0
                if mask.any():
                    invalid_incomes = lu_df[mask & (~lu_df['avgincome'].isin(valid_incomes))]
                    if not invalid_incomes.empty:
                        msgs.append(("error", f"Landuse rows with densitycap > 0 must have avgincome in {valid_incomes}. Found {len(invalid_incomes)} invalid rows."))
                    else:
                        msgs.append(("success", "Landuse 'avgincome' conditions verified for densitycap > 0."))

        # BUILDING
        if 'building' in datasets:
            bld_df = datasets['building']
            req_bld = {'geometry', 'residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'specialfac'}
            missing_cols = req_bld - set(bld_df.columns)
            if missing_cols:
                msgs.append(("error", f"Building is missing required attributes: {', '.join(missing_cols)}"))
            
            if 'zoneid' in bld_df.columns and 'landuse' in datasets and 'zoneid' in datasets['landuse'].columns:
                lu_zoneids = set(datasets['landuse']['zoneid'].dropna())
                bld_zoneids = set(bld_df['zoneid'].dropna())
                invalid_bld_zones = bld_zoneids - lu_zoneids
                if invalid_bld_zones:
                    l = list(invalid_bld_zones)
                    msgs.append(("error", f"Building 'zoneid' values not found in Landuse: {l[:5]}{'...' if len(l)>5 else ''}"))
                else:
                    msgs.append(("success", "Building to Landuse 'zoneid' linkage verified."))

        # HOUSEHOLD
        if 'household' in datasets:
            hh_df = datasets['household']
            req_hh = {'hhid', 'nind', 'income', 'bldid', 'commfacid'}
            missing_cols = req_hh - set(hh_df.columns)
            if missing_cols:
                msgs.append(("error", f"Household is missing required attributes: {', '.join(missing_cols)}"))
                
            if 'bldid' in hh_df.columns and 'building' in datasets and 'bldid' in datasets['building'].columns:
                bld_bldids = set(datasets['building']['bldid'].dropna())
                hh_bldids = set(hh_df['bldid'].dropna())
                invalid_hh_blds = hh_bldids - bld_bldids
                if invalid_hh_blds:
                    l = list(invalid_hh_blds)
                    msgs.append(("error", f"Household 'bldid' values not found in Building: {l[:5]}{'...' if len(l)>5 else ''}"))
                else:
                    msgs.append(("success", "Household to Building 'bldid' linkage verified."))

        # INDIVIDUAL
        if 'individual' in datasets:
            ind_df = datasets['individual']
            req_ind = {'individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid'}
            missing_cols = req_ind - set(ind_df.columns)
            if missing_cols:
                msgs.append(("error", f"Individual is missing required attributes: {', '.join(missing_cols)}"))
                
            if 'hhid' in ind_df.columns and 'household' in datasets and 'hhid' in datasets['household'].columns:
                hh_hhids = set(datasets['household']['hhid'].dropna())
                ind_hhids = set(ind_df['hhid'].dropna())
                invalid_ind_hhs = ind_hhids - hh_hhids
                if invalid_ind_hhs:
                    l = list(invalid_ind_hhs)
                    msgs.append(("error", f"Individual 'hhid' values not found in Household: {l[:5]}{'...' if len(l)>5 else ''}"))
                else:
                    msgs.append(("success", "Individual to Household 'hhid' linkage verified."))

        set_messages(msgs)
        set_is_processing(False)

    def clear():
        set_messages([])
        set_is_processing(False)
        set_file_drop_key(file_drop_key + 1)

    with solara.Details("Landuse + Exposure Data Check"):
        solara.Markdown("Full validation requires these 4 datasets: **landuse, building, household, individual**.")
        solara.Markdown("Drag and drop these 4 files below or click to browse.")
        
        FileDropMultiple(on_file=process_files, lazy=False, uid=str(file_drop_key))
        
        if is_processing:
            solara.ProgressLinear(value=True)
            solara.Text("Validating files, please wait...")
        else:
            if len(messages) > 0:
                solara.Button("Clear", on_click=clear, icon_name="mdi-delete", color="error", class_="mt-4 mb-4")

        for m_type, msg in messages:
            if m_type == "error":
                solara.Error(msg)
            elif m_type == "warning":
                solara.Warning(msg)
            elif m_type == "success":
                solara.Success(msg)
            elif m_type == "info":
                solara.Info(msg)

@solara.component
def HazardDataCheck():
    messages, set_messages = solara.use_state([])
    is_processing, set_is_processing = solara.use_state(False)
    file_drop_key, set_file_drop_key = solara.use_state(0)

    def process_file(file_info):
        set_is_processing(True)
        set_messages([])
        
        set_messages([("info", f"Reading {file_info['name']}...")])
        
        msgs = []
        try:
            df = import_data(file_info)
            if df is None:
                msgs.append(("error", f"Could not extract dataframe from {file_info['name']}."))
            else:
                req_cols = {'geometry', 'im'}
                missing_cols = req_cols - set(df.columns)
                
                if missing_cols:
                    msgs.append(("error", f"File '{file_info['name']}' does not contain required attribute(s) for a hazard data ({', '.join(missing_cols)}). Check attributes!"))
                else:
                    msgs.append(("success", f"Loaded '{file_info['name']}' successfully."))
                    msgs.append(("success", "Required attributes ('geometry', 'im') verified."))
                    
                    # Check 'im' is >= 0
                    df['im'] = pd.to_numeric(df['im'], errors='coerce')
                    invalid_im = df[df['im'] < 0]
                    if not invalid_im.empty:
                        msgs.append(("error", f"Hazard 'im' contains negative values. Found {len(invalid_im)} invalid rows."))
                    else:
                        msgs.append(("success", "Hazard 'im' >= 0 verified."))
                        
        except Exception as e:
            msgs.append(("error", f"Error reading {file_info['name']}: {e}"))
            
        set_messages(msgs)
        set_is_processing(False)

    def clear():
        set_messages([])
        set_is_processing(False)
        set_file_drop_key(file_drop_key + 1)

    with solara.Details("Hazard Data Check"):
        solara.Markdown("Validation requires a hazard dataset containing **geometry** and **im** attributes.")
        solara.Markdown("Drag and drop your file below or click to browse.")
        
        FileDrop(on_file=process_file, lazy=False, uid=str(file_drop_key))
        
        if is_processing:
            solara.ProgressLinear(value=True)
            solara.Text("Validating file, please wait...")
        else:
            if len(messages) > 0:
                solara.Button("Clear", on_click=clear, icon_name="mdi-delete", color="error", class_="mt-4 mb-4")

        for m_type, msg in messages:
            if m_type == "error":
                solara.Error(msg)
            elif m_type == "warning":
                solara.Warning(msg)
            elif m_type == "success":
                solara.Success(msg)
            elif m_type == "info":
                solara.Info(msg)

@solara.component
def VulnerabilityFragilityDataCheck():
    messages, set_messages = solara.use_state([])
    is_processing, set_is_processing = solara.use_state(False)
    file_drop_key, set_file_drop_key = solara.use_state(0)

    def process_files(files):
        set_is_processing(True)
        set_messages([])
        
        msgs = []
        for f in files:
            msgs.append(("info", f"Reading {f['name']}..."))
        set_messages(msgs.copy())
        
        msgs = []
        datasets = {}
        vuln_frag_df = None
        vuln_frag_name = ""
        vuln_frag_type = ""

        # Extract files
        for f in files:
            try:
                df = import_data(f)
                if df is None:
                    msgs.append(("error", f"Could not extract dataframe from {f['name']}."))
                    continue
                
                cols = set(df.columns)
                
                # Check for Vulnerability
                req_vuln = {'expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5', 'hw6'}
                # Check for Fragility
                req_frag = {'expstr', 'muds1_g', 'muds2_g', 'muds3_g', 'muds4_g', 'sigmads1', 'sigmads2', 'sigmads3', 'sigmads4'}
                # Check for Building
                req_building = {'residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac'}

                if req_vuln.issubset(cols):
                    if vuln_frag_df is not None:
                        msgs.append(("warning", f"Multiple vulnerability/fragility files detected. Ignoring '{f['name']}'."))
                    else:
                        vuln_frag_df = df
                        vuln_frag_name = f['name']
                        vuln_frag_type = "Vulnerability"
                        msgs.append(("success", f"Loaded '{f['name']}' successfully as Vulnerability data."))
                elif req_frag.issubset(cols):
                    if vuln_frag_df is not None:
                        msgs.append(("warning", f"Multiple vulnerability/fragility files detected. Ignoring '{f['name']}'."))
                    else:
                        vuln_frag_df = df
                        vuln_frag_name = f['name']
                        vuln_frag_type = "Earthquake Fragility"
                        msgs.append(("success", f"Loaded '{f['name']}' successfully as Earthquake Fragility data."))
                else:
                    is_building = False
                    if 'nhouse' in cols and 'fptarea' in cols and 'residents' in cols:
                        is_building = True
                    else:
                        dtype = classify_dataset(df, f['name'])
                        if dtype == 'building':
                            is_building = True

                    if is_building:
                        missing_bld = req_building - cols
                        if missing_bld:
                            msgs.append(("error", f"Building data '{f['name']}' is missing required attributes: {', '.join(missing_bld)}"))
                        else:
                            datasets['building'] = df
                            msgs.append(("success", f"Loaded '{f['name']}' successfully as Building data."))
                    else:
                        msgs.append(("error", f"File '{f['name']}' does not contain required attributes for building, vulnerability, or fragility data. Check attributes!"))

            except Exception as e:
                msgs.append(("error", f"Error reading {f['name']}: {e}"))

        if vuln_frag_df is None:
            msgs.append(("error", "Missing Vulnerability or Earthquake Fragility dataset. Please upload at least one."))
        else:
            # 3. Check for missing values in rows where expstr has a value
            # Only consider rows where 'expstr' is not empty
            valid_rows = vuln_frag_df[vuln_frag_df['expstr'].notna() & (vuln_frag_df['expstr'] != '')]
            
            if vuln_frag_type == "Vulnerability":
                cols_to_check = ['expstr', 'hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5', 'hw6']
            else:
                cols_to_check = ['expstr', 'muds1_g', 'muds2_g', 'muds3_g', 'muds4_g', 'sigmads1', 'sigmads2', 'sigmads3', 'sigmads4']
                
            missing_vals = valid_rows[cols_to_check].isnull().any(axis=1)
            num_invalid = missing_vals.sum()
            
            if num_invalid > 0:
                msgs.append(("error", f"{vuln_frag_type} data contains '{num_invalid}' rows with missing values where 'expstr' is provided."))
            else:
                msgs.append(("success", f"{vuln_frag_type} data missing values check passed."))

            # Check matching with building data if present
            vf_expstr_list = set(valid_rows['expstr'].astype(str).unique())
            
            if 'building' in datasets:
                bld_df = datasets['building']
                if 'expstr' in bld_df.columns:
                    bld_expstr_list = set(bld_df[bld_df['expstr'].notna()]['expstr'].astype(str).unique())
                    missing_in_vf = bld_expstr_list - vf_expstr_list
                    if missing_in_vf:
                        l = list(missing_in_vf)
                        msgs.append(("error", f"{vuln_frag_type} data is missing 'expstr' records found in building data: {l[:5]}{'...' if len(l)>5 else ''}"))
                    else:
                        msgs.append(("success", f"All 'expstr' records in building data are present in the {vuln_frag_type} data."))
                else:
                    msgs.append(("error", "Building data is missing the 'expstr' attribute for cross-checking."))
            else:
                msgs.append(("info", f"Provide a building dataset along with your {vuln_frag_type} data for a full cross-check of 'expstr' consistency."))

        set_messages(msgs)
        set_is_processing(False)

    def clear():
        set_messages([])
        set_is_processing(False)
        set_file_drop_key(file_drop_key + 1)

    with solara.Details("Vulnerability / Fragility Data Check"):
        solara.Markdown("Validation requires either a **Flood Vulnerability** or **Earthquake Fragility** dataset. You can also optionally upload your **Building** dataset for a full cross-check.")
        solara.Markdown("Drag and drop your file(s) below or click to browse.")
        
        FileDropMultiple(on_file=process_files, lazy=False, uid=str(file_drop_key))
        
        if is_processing:
            solara.ProgressLinear(value=True)
            solara.Text("Validating file(s), please wait...")
        else:
            if len(messages) > 0:
                solara.Button("Clear", on_click=clear, icon_name="mdi-delete", color="error", class_="mt-4 mb-4")

        for m_type, msg in messages:
            if m_type == "error":
                solara.Error(msg)
            elif m_type == "warning":
                solara.Warning(msg)
            elif m_type == "success":
                solara.Success(msg)
            elif m_type == "info":
                solara.Info(msg)


@solara.component
def DataValidator():
    with solara.Details("Data Validator"):
        with solara.Column(classes=["data-validator-subtools"]):
            LanduseExposureCheck()
            HazardDataCheck()
            VulnerabilityFragilityDataCheck()

@solara.component
def Utilities():
    
    with solara.Column():
        ExcelToGeoJsonConverter()
        JsonToCsvConverter()
        CsvToJsonConverter()
        FloodVulnerabilityTemplateGenerator()
        DataValidator()

    

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

    .v-expansion-panel-header {
        font-weight: bold;
        font-size: 1.1em;
        color: #424242;
    }
    
    .data-validator-subtools .v-expansion-panel-header {
        font-size: 1em; /* smaller than main heading which uses 1.1em or browser default larger */
        color: #757575; /* lighter gray */
        font-weight: 600;
        margin-left: 10px;
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
        'zoneid': {'name': 'Zone ID',
                'mapping': {}},
        'luf': {'name': 'Land Use Type',
                'mapping': {}},
        'avgincome': {'name': 'Average Income',
                'mapping': {'highIncome': 'High Income', 'lowIncomeA': 'Low Income', 'lowIncomeB': 'Low Income', 'midIncome': 'Moderate Income'}},
        },
    'building': {
        'zoneid': {'name': 'Zone ID',
                'mapping': {}},
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
        'zoneid': {'name': 'Zone ID',
                'mapping': {}},
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
    keys_intersection = [k for k in lbl_2_str[layer_name].keys() if k in data.columns]
    df = data[keys_intersection].copy()

    for col, colinfo in lbl_2_str[layer_name].items():
        if col in df.columns and len(colinfo['mapping']) > 0:
            df.replace({col: colinfo['mapping']}, inplace=True)

    renaming = {col: colinfo['name'] for col, colinfo in lbl_2_str[layer_name].items()}
    df.rename(columns=renaming, inplace=True)


    return df