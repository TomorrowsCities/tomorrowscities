import pandas as pd
import geopandas as gpd
import numpy as np
from numpy.random import multinomial, randint
import random
from random import sample
import sys
import uuid
import math
from math import ceil
from itertools import repeat, chain
import copy

from .utilities import read_zipshp, dist2vector
from .fpt_generator import *
from .logging_utils import log_info, log_warning, log_error


def _allocate_constraint_population_to_zones(landuse_gdf, constraint_gdf):
    """Distribute constraint-layer population into intersecting land-use zones."""
    zone_population = pd.Series(0.0, index=landuse_gdf.index, dtype=float)

    if constraint_gdf is None or constraint_gdf.empty or 'population' not in constraint_gdf.columns:
        return zone_population

    constraints = constraint_gdf.copy()
    constraints['population'] = pd.to_numeric(constraints['population'], errors='coerce').fillna(0.0).clip(lower=0.0)
    constraints = constraints[constraints['population'] > 0].copy()
    if constraints.empty:
        return zone_population

    landuse_lookup = landuse_gdf[['geometry']].copy()
    landuse_lookup['_landuse_idx'] = landuse_gdf.index

    def accumulate_measure_based(source_gdf, measure_kind):
        nonlocal zone_population

        if source_gdf.empty:
            return

        source = source_gdf.copy()
        source['_constraint_idx'] = np.arange(len(source), dtype=int)
        if measure_kind == 'area':
            source['feature_measure'] = source.geometry.area
        else:
            source['feature_measure'] = source.geometry.length

        source = source[source['feature_measure'] > 0].copy()
        if source.empty:
            return

        intersected = gpd.overlay(
            source[['_constraint_idx', 'population', 'feature_measure', 'geometry']],
            landuse_lookup[['_landuse_idx', 'geometry']],
            how='intersection'
        )
        if intersected.empty:
            return

        if measure_kind == 'area':
            intersected['intersection_measure'] = intersected.geometry.area
        else:
            intersected['intersection_measure'] = intersected.geometry.length

        valid = intersected['feature_measure'] > 0
        intersected.loc[valid, 'population_share'] = (
            intersected.loc[valid, 'population'] *
            intersected.loc[valid, 'intersection_measure'] /
            intersected.loc[valid, 'feature_measure']
        )
        zone_population = zone_population.add(
            intersected.groupby('_landuse_idx')['population_share'].sum(),
            fill_value=0.0
        )

    def accumulate_points(point_gdf):
        nonlocal zone_population

        if point_gdf.empty:
            return

        points = point_gdf.copy()
        points['_constraint_idx'] = np.arange(len(points), dtype=int)

        try:
            joined = gpd.sjoin(
                points[['_constraint_idx', 'population', 'geometry']],
                landuse_lookup[['_landuse_idx', 'geometry']],
                how='inner',
                predicate='intersects'
            )
        except TypeError:
            joined = gpd.sjoin(
                points[['_constraint_idx', 'population', 'geometry']],
                landuse_lookup[['_landuse_idx', 'geometry']],
                how='inner',
                op='intersects'
            )

        if joined.empty:
            return

        joined['match_count'] = joined.groupby('_constraint_idx')['_landuse_idx'].transform('count')
        joined['population_share'] = joined['population'] / joined['match_count']
        zone_population = zone_population.add(
            joined.groupby('_landuse_idx')['population_share'].sum(),
            fill_value=0.0
        )

    polygon_constraints = constraints[constraints.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])].copy()
    line_constraints = constraints[constraints.geometry.geom_type.isin(['LineString', 'MultiLineString'])].copy()
    point_constraints = constraints[constraints.geometry.geom_type.isin(['Point', 'MultiPoint'])].copy()

    accumulate_measure_based(polygon_constraints, 'area')
    accumulate_measure_based(line_constraints, 'length')
    accumulate_points(point_constraints)

    return zone_population

def process_data(input_spreadsheet, ipfile_landuse, constraint_gdf=None, seed=None):
    global final, household_df, individual_df
                 
    school_distr_method = 'landuse' # 'population' or 'landuse'
    hospital_distr_method = 'landuse' # 'population' or 'landuse'
    
    #%% Save seed
    seed = random.randint(0, 100000) if seed is None else int(seed)
      
    # To re-generate a desired state comment above line and use: rng = int(seed_value_in_result)
    random.seed(seed)
    np.random.seed(seed)
    
    debug_info = dict()
    debug_info["args"] = sys.argv
    debug_info["seed"] = seed  
    
    debug_info["seed"] = seed  
    
    #%% Read the 3 sheets in the dataframe
    if input_spreadsheet is None or ipfile_landuse is None:
        msg = "All input files have to be loaded! Please upload input spreadsheet and landuse file."
        log_error(msg)
        raise ValueError(msg)

    if input_spreadsheet is not None:
        df_nc = pd.read_excel(input_spreadsheet,sheet_name=1,header=None)
        ipdf = pd.read_excel(input_spreadsheet,sheet_name=2, header=None)
        df1 = pd.read_excel(input_spreadsheet,sheet_name=3, header=None)
        df2 = pd.read_excel(input_spreadsheet,sheet_name=4, header=None)
        df3 = pd.read_excel(input_spreadsheet,sheet_name=5, header=None)
            
    #%% Extract the nomenclature for load resisting system and land use types
    startmarker = '\['
    startidx = df_nc[df_nc.apply(lambda row: row.astype(str).str.contains(startmarker,case=False).any(), axis=1)]
        
    endmarker = '\]'
    endidx = df_nc[df_nc.apply(lambda row: row.astype(str).str.contains(endmarker,case=False).any(), axis=1)]
        
    # Load resisting system types
    lrs_types_temp = df_nc.loc[list(range(startidx.index[0]+1,endidx.index[0]))]
    lrs_types = lrs_types_temp[1].to_numpy().astype(str)
    lrsidx = {}
    count = 0
    for key in lrs_types:
        lrsidx[str(key)] = count
        count+=1
        
    # Landuse Types 
    lut_types_temp = df_nc.loc[list(range(startidx.index[1]+1,endidx.index[1]))]
    lut_types = lut_types_temp[1].astype(str)
    lutidx = {}
    count = 0
    for key in lut_types:
        lutidx[key] = count
        count+=1    
        
    #%% Inputs extracted from the excel input file
    
    opfile_building = 'building_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_household = 'household_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_individual = 'individual_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_landuse =  'landuse_layer_'+str(uuid.uuid4())+'.xlsx'
              
    # Income types is hardcoded
    avg_income_types =np.array(['lowIncomeA','lowIncomeB','midIncome','highIncome'])
    
    # Extract average dwelling area and footprint area             
    average_dwelling_area = np.array([ipdf.iloc[13,2],ipdf.iloc[13,3],\
                                      ipdf.iloc[13,4],ipdf.iloc[13,5]])
    
    fpt_area = {'lowIncomeA':np.fromstring(str(ipdf.iloc[14,2]),dtype=float,sep=','),
                'lowIncomeB':np.fromstring(str(ipdf.iloc[14,3]),dtype=float,sep=','),
                'midIncome':np.fromstring(str(ipdf.iloc[14,4]),dtype=float,sep=','),
                'highIncome':np.fromstring(str(ipdf.iloc[14,5]),dtype=float,sep=',')}
    
    # Extract storey definition
    storey_range = {0:np.fromstring(str(ipdf.iloc[17,2]),dtype=int,sep=','),
                    1:np.fromstring(str(ipdf.iloc[17,3]),dtype=int,sep=','),
                    2:np.fromstring(str(ipdf.iloc[17,4]),dtype=int,sep=',')}
    
    # Code Compliance Levels (Low, Medium, High): 1 - LC, 2 - MC, 3 - HC
    code_level = np.array(['LC','MC','HC'])
    
    # Nr of commercial buildings per 1000 individuals
    numb_com = ipdf.iloc[2,1]
    # Nr of industrial buildings per 1000 individuals
    numb_ind = ipdf.iloc[3,1]
    
    # Area constraints in percentage (AC) for residential and commercial zones. 
    # Total built-up areas in these zones cannot exceed (AC*available area)
    AC_com = ipdf.iloc[6,1] # in percent
    AC_ind = ipdf.iloc[7,1] # in percent
    
    # Assumption 14 and 15: Number of individuals per school and hospitals
    nsch_pi = ipdf.iloc[9,1]
    nhsp_pi = ipdf.iloc[10,1]
    
    # Unit price for replacement wrt occupancy type and special facility 
    # status of the building
    # Occupancy type is unchangeable, only replacement value is taken from user input
    Unit_price={'Res':ipdf.iloc[20,2],'Com':ipdf.iloc[20,3],'Ind':ipdf.iloc[20,4],
                'ResCom':ipdf.iloc[20,5],'Edu':ipdf.iloc[20,6],'Hea':ipdf.iloc[20,7]}
    
    #household_building_match = 'footprint' # 'footprint' or 'number_of_units'
    
    #%% Read the landuse shapefile
    if isinstance(ipfile_landuse, gpd.GeoDataFrame):
        landuse_shp = ipfile_landuse.copy()
    else:
        landuse_shp = gpd.read_file(ipfile_landuse)

    
    # Use lowercase for all columns   
    landuse_shp.columns = (
	    landuse_shp.columns
	    .str.strip()
	    .str.lower()
    )

    # Important to use equal-area projection!!!
    # for ending up exact same footprint values!!! However, angles are not preserved as the projection is not conformal!                
    # if landuse_shp.crs.is_projected is False:
        # initial_crs = landuse_shp.crs
        # landuse_shp = landuse_shp.to_crs("ESRI:54034") # World Cylindrical Equal Area
        
    # Use comprimise projection to obtain better look (Ne açı ne alan tam olarak korunur, ama ikisine yakın)
    if landuse_shp.crs is None:
        landuse_shp = landuse_shp.set_crs("EPSG:4326")
    initial_crs = landuse_shp.crs
    landuse_shp = landuse_shp.to_crs("ESRI:54030") # Robinson
        
    # Calculate areas even if they are included in the shapefile to avoid using miscalculated values!
    landuse_shp_cartesian = landuse_shp.copy()
    
    landuse_shp_cartesian['constraint_population'] = 0.0

    # If constraint_gdf is provided and has polygons, subtract their intersection area from landuse area.
    if constraint_gdf is not None:
        # Standardize column names to lowercase so 'setback' is consistently found
        constraint_gdf.columns = constraint_gdf.columns.str.strip().str.lower()
        
        if constraint_gdf.crs is None:
            constraint_gdf = constraint_gdf.set_crs("EPSG:4326")
        constraint_gdf = constraint_gdf.to_crs("ESRI:54030") # Same projection as landuse for area calc

        # If the exclusion/alignment layer carries existing population,
        # allocate it to intersecting land-use zones before synthetic generation.
        landuse_shp_cartesian['constraint_population'] = _allocate_constraint_population_to_zones(
            landuse_shp,
            constraint_gdf
        )
        
        # Buffer geometries for area subtraction if 'setback' is present
        area_constraint_gdf = constraint_gdf.copy()
        if 'setback' in area_constraint_gdf.columns:
            area_constraint_gdf['setback'] = pd.to_numeric(area_constraint_gdf['setback'], errors='coerce').fillna(0.0)
            buffered_geoms = [
                (g.buffer(dist) if dist > 0.0 else g) 
                for g, dist in zip(area_constraint_gdf.geometry, area_constraint_gdf['setback'])
            ]
            area_constraint_gdf['geometry'] = gpd.GeoSeries(buffered_geoms, crs=area_constraint_gdf.crs)
            
        poly_constraints = area_constraint_gdf[area_constraint_gdf.geometry.geom_type.isin(['Polygon', 'MultiPolygon'])]
        if not poly_constraints.empty:
            # Union all polygons to avoid double subtracting overlapping constraints
            union_poly = poly_constraints.geometry.union_all()
            
            # Calculate intersected area per landuse polygon
            intersection_areas = landuse_shp.geometry.intersection(union_poly).area / 10**4 # in Hectares
            
            # Base area
            base_area = landuse_shp.geometry.area / 10**4
            
            # Subtract
            landuse_shp_cartesian['area'] = base_area - intersection_areas
            # Prevent negative areas just in case
            landuse_shp_cartesian['area'] = landuse_shp_cartesian['area'].clip(lower=0)
        else:
            landuse_shp_cartesian['area'] = landuse_shp.geometry.area / 10**4 # m^2 to Hectares
    else:
        landuse_shp_cartesian['area'] = landuse_shp.geometry.area / 10**4 # m^2 to Hectares
        
    landuse_shp_cartesian = landuse_shp_cartesian.drop(columns=['geometry'])
    landuse = landuse_shp_cartesian.copy()
    
    # CRITICAL FIX: Ensure landuse_shp uses the correctly recalculated area (in hectares)
    # The input file might contain area in different units or incorrect values.
    landuse_shp['area'] = landuse_shp_cartesian['area']
        
    # In the landuse shape file, if avgincome = lowIncome, replace it by lowIncomeA
    
    # Ensure 'setback' column exists and is numeric (default to 0.0)
    if 'setback' not in landuse_shp.columns:
        landuse_shp['setback'] = 0.0
    else:
        landuse_shp['setback'] = pd.to_numeric(landuse_shp['setback'], errors='coerce').fillna(0.0)
    lowIncome_mask = landuse['avgincome'] == 'lowIncome'
    landuse.loc[lowIncome_mask,'avgincome'] = 'lowIncomeA'
    
    # Validate avgincome values if densitycap > 0
    # Because densitycap might not be numeric yet, cast safely for checking
    valid_income_types = list(avg_income_types)
    invalid_income_mask = (pd.to_numeric(landuse['densitycap'], errors='coerce') > 0) & (~landuse['avgincome'].isin(valid_income_types))
    if invalid_income_mask.any():
        invalid_zones = landuse.loc[invalid_income_mask, 'zoneid'].tolist()
        invalid_incomes = landuse.loc[invalid_income_mask, 'avgincome'].unique().tolist()
        raise ValueError(
            f"Input Landuse Error: Some records with densitycap > 0 have an invalid 'avgincome'. "
            f"Found: {invalid_incomes} in zones {invalid_zones}. "
            f"Expected one of: {valid_income_types}."
        )
    
    # Typecast the various fields in landuse shapefile
    landuse['population'] = landuse['population'].astype(int)
    landuse['densitycap'] = landuse['densitycap'].astype(float)
    landuse['area'] = landuse['area'].astype(float)
    landuse['zoneid'] = landuse['zoneid'].astype(int)
    if 'constraint_population' in landuse.columns:
        landuse['constraint_population'] = landuse['constraint_population'].astype(float)
    if 'floorarear' in landuse.columns:
        landuse['floorarear'] = landuse['floorarear'].astype(float)
    if 'setback' in landuse.columns:
        landuse['setback'] = landuse['setback'].astype(float)
    
    #%% Concatenate the dataframes and process the data
    try:
        tabledf = pd.concat([df1,df2,df3]).reset_index(drop=True)
    
        # Define a dictionary containing data distribution tables
        # Table names sorted according to the order in the excel input spreadsheet
        tables_temp = {
            't1':[],'t2':[],'t3':[],'t4':[],'t4a':[],'t4b':[],'t4c':[],'t5':[],'t5a':[],'t6':[],'t9':[],
            't12':[],'t13':[],'t7':[],'t8':[],'t11':[],'t10':[],'t14':[]   
            }
        
        # Explicit order to ensure correct mapping from spreadsheet regardless of dict iteration
        # Added t4a for dynamic labour force age limits, t4b for dynamic head of household age limits, t4c for school age
        tables_order = ['t1','t2','t3','t4','t4a','t4b','t4c','t5','t5a','t6','t9','t12','t13','t7','t8','t11','t10','t14']

        startmarker = '\['
        startidx = tabledf[tabledf.apply(lambda row: row.astype(str).str.contains(startmarker,case=False).any(), axis=1)]
            
        endmarker = '\]'
        endidx = tabledf[tabledf.apply(lambda row: row.astype(str).str.contains(endmarker,case=False).any(), axis=1)]
            
        count=0
        for key in tables_order:
            # log_info(f"Mapping Chunk {count} to Key {key}")
            tablepart = tabledf.loc[list(range(startidx.index[count]+1,endidx.index[count]))]
            tablepart = tablepart.drop(columns =0 )
            tablepart = tablepart.dropna(axis=1, how='all').reset_index(drop=True).values.tolist()
            tables_temp[key].append(tablepart)
            count+=1
        
        tables = tables_temp
        
        #%% Basic exception handling to check improper inputs in the spreadsheet
        input_error_flag = False
        input_error_flag_shp = False
         
        if numb_com ==0:
            log_error('The number of commercial buildings cannot be zero.')
            input_error_flag = True
            #pass
        if numb_ind == 0:
            log_error('The number of industrial buildings cannot be zero.')
            input_error_flag = True
            #pass
            
        # Validate Table 7
        if len(lutidx) != len(tables['t7'][0]):
            log_error(f"Table 7 Error: Number of rows ({len(tables['t7'][0])}) does not match the number of Land Use Types (LUT) in Nomenclature ({len(lutidx)}).")
            input_error_flag = True
        if len(lrsidx) != len(tables['t7'][0][0]):
            log_error(f"Table 7 Error: Number of columns ({len(tables['t7'][0][0])}) does not match the number of Load Resisting System (LRS) types in Nomenclature ({len(lrsidx)}).")
            input_error_flag = True
    
        # Validate Table 8
        if len(lutidx) != len(tables['t8'][0]):
            log_error(f"Table 8 Error: Number of rows ({len(tables['t8'][0])}) does not match the number of Land Use Types (LUT) in Nomenclature ({len(lutidx)}).")
            input_error_flag = True
        if len(lrsidx) != len(tables['t8'][0][0]):
            log_error(f"Table 8 Error: Number of columns ({len(tables['t8'][0][0])}) does not match the number of Load Resisting System (LRS) types in Nomenclature ({len(lrsidx)}).")
            input_error_flag = True
    
        # Validate Table 9
        if len(lutidx) != len(tables['t9'][0]):
            log_error(f"Table 9 Error: Number of rows ({len(tables['t9'][0])}) does not match the number of Land Use Types (LUT) in Nomenclature ({len(lutidx)}).")
            input_error_flag = True
        
        # Validate Table 11
        if len(lutidx) != len(tables['t11'][0]):
            log_error(f"Table 11 Error: Number of rows ({len(tables['t11'][0])}) does not match the number of Land Use Types (LUT) in Nomenclature ({len(lutidx)}).")
            input_error_flag = True
        if len(lrsidx) != len(tables['t11'][0][0]):
            log_error(f"Table 11 Error: Number of columns ({len(tables['t11'][0][0])}) does not match the number of Load Resisting System (LRS) types in Nomenclature ({len(lrsidx)}).")
            input_error_flag = True
        # Validate Table 7 and 11 Content (CSV distribution strings)
        # Validate Table 7 and 11 Content (CSV distribution strings)
        for table_name in ['t7', 't11', 't14', 't10']: # Added t14 and t10
            if table_name in tables and len(tables[table_name]) > 0:
                table_error = False
                for r_idx, row in enumerate(tables[table_name][0]):
                    if table_error: break
                    for c_idx, cell in enumerate(row):
                        try:
                            # Use plain python parsing
                            cell_str = str(cell).strip()
                            # It should be a comma separated list of numbers
                            parts = cell_str.split(',')
                            vals = [float(x) for x in parts]
                            
                            # Prob check only for t7 and t11
                            if table_name in ['t7', 't11']:
                                # Check Valid Probabilities
                                if any(x < 0 for x in vals) or any(math.isnan(x) for x in vals):
                                    table_error = True
                                    break
                                # Use slight tolerance for floating point sum > 1.0 (e.g. 1.01)
                                if sum(vals) > 1.01: 
                                    table_error = True
                                    break
                            else:
                                # For T14 (ranges), just check valid numbers
                                if any(math.isnan(x) for x in vals):
                                    table_error = True
                                    break
                                    
                        except:
                             table_error = True
                             break
                if table_error:
                    msg = "Invalid Probabilities" if table_name in ['t7', 't11'] else "Invalid Content"
                    log_error(f"Error detected in Table {table_name[1:]} ({msg}). Please check the input values.")
                    input_error_flag = True
        
        # Define numeric tables
        # t8, t9 have probability sum constraints
        # t1, t2, t3, t4, t5, t5a, t6, t10, t12, t13 are simple numeric
        
        prob_tables_numeric = ['t8', 't9']
        # Removed t10 from here, moved to csv group
        general_tables_numeric = ['t1', 't2', 't3', 't4', 't5', 't5a', 't6', 't12', 't13']
        
        # Validate Table 8 and 9 Content (Numeric values + Prob constraints)
        for table_name in prob_tables_numeric:
            if table_name in tables and len(tables[table_name]) > 0:
                table_error = False
                for r_idx, row in enumerate(tables[table_name][0]):
                    if table_error: break
                    
                    # Accumulate row sum for Table 8/9 since they are rows of probabilities
                    row_probs = [] 
                    for c_idx, cell in enumerate(row):
                         try:
                             val = float(cell)
                             if val < 0 or math.isnan(val):
                                 table_error = True
                                 break
                             row_probs.append(val)
                         except ValueError:
                             table_error = True
                             break
                    
                    if not table_error:
                        if sum(row_probs) > 1.01:
                            table_error = True
                            break
                            
                if table_error:
                    log_error(f"Error detected in Table {table_name[1:]} (Invalid Probabilities). Please check the input values.")
                    input_error_flag = True
                    
        # Validate all other numeric tables
        for table_name in general_tables_numeric:
             if table_name in tables and len(tables[table_name]) > 0:
                table_error = False
                for r_idx, row in enumerate(tables[table_name][0]):
                    if table_error: break
                    for c_idx, cell in enumerate(row):
                         try:
                             val = float(cell)
                             if math.isnan(val):
                                 table_error = True
                                 break
                         except ValueError:
                             table_error = True
                             break
                if table_error:
                    log_error(f"Error detected in Table {table_name[1:]} (Invalid Content). Please check the input values.")
                    input_error_flag = True
        
        # Check if avgincome values are missing for fields in the nomenclature list
        for val in lut_types:
            avgInc_mask = landuse['luf'] == val
            incomeval4lut = landuse.loc[avgInc_mask,'avgincome']
            if incomeval4lut.isnull().values.any(): 
                default_avgIncome = 'no_avgIncome'
                landuse.loc[avgInc_mask,'avgincome'] = default_avgIncome
                log_warning(f'avgincome field missing for {val}, value set to {default_avgIncome}')
                input_error_flag_shp = True        
                
        if input_error_flag:
            log_error('Please correct the faulty inputs in the input spreadsheet.\n')
            
        if input_error_flag_shp:
            log_warning('Please provide appropriate values in input landuse if necessary.\n')
            
        if input_error_flag:
            raise RuntimeError("Input validation failed. Please check the error messages above.")    
        
    except Exception as e:
        # If it is a known validation error, just re-raise it without logging "Critical Error" again
        if str(e) == "Input validation failed. Please check the error messages above.":
            raise e
        else:
            log_error(f"Critical Error: Unable to process the input spreadsheet. Please check if all tables contain valid data.\nDetails: {str(e)}")
            raise RuntimeError(f"Processing failed: {str(e)}")

    #%% Note on definition of data layers
    # The household layer is initialized as Pandas dataframe in Step 2
    # The individual layer is initialized as Pandas dataframe in Step 5
    # The building layer is initialized as Pandas dataframe in Step 12
    # landuse_res_df (residential zone landuse subdataframe) is defined in step 11
    # landuse_ic_df (commercial/industrial) is also defined in step 11
    
    #%% The data generation process begins here____________________________________
    
    #%% Step 1: Calculate maximum population (nPeople)
    # Utilise population value directly to generate individuals
    # landuse['population'] = landuse['population'].astype(int)
    # nPeople = landuse['population']
    
    # Calculate individuals to be generated using DC.
    # Existing population from the land-use layer and optional constraint layers
    # both reduce the synthetic population to be generated.
    nPeople = round(
        landuse['densitycap'] * landuse['area'] -
        landuse['population'] -
        landuse.get('constraint_population', 0.0)
    )
    nPeople[nPeople<0] = 0
    
    #%% Step 2: Calculate the number of households (nHouse), hhID
    # Assumption 1: Household size distribution is same for different income types
    # Question: How to ensure that there are no NaNs while assigning zone type?
    
    # Convert Table 1 to numpy array
    t1_list = tables['t1'][0]
     # No. of individuals
    t1_l1 = np.array(t1_list[0], dtype=int) 
    t1_l2 = np.array(t1_list[1], dtype=float) # Probabilities
    
    # Compute the probability of X number of people living in a household 
    household_prop = t1_l2/sum(t1_l2) 
    # Total number of households for all zones
    nHouse_all = round(nPeople/(sum(household_prop*t1_l1)))
    nHouse_all = nHouse_all.astype('int32')
    nHouse = nHouse_all[nHouse_all>0] # Exclude zones with zero households
    nHouseidx = nHouse.index
    #Preallocate a dataframe with nan to hold the household layer
    household_df = pd.DataFrame(np.nan, index = range(sum(nHouse)),
                                columns=['bldID','hhID','income','nIND','CommFacID',
                                         'income_numb','zoneType','zoneid',
                                         'approxFootprint'])
    # Fix future warning by setting object columns dtype
    for col in ['zoneType', 'income']:
        household_df[col] = household_df[col].astype('object')

    #Calculate a list of cumulative sum of nHouse
    nHouse_cuml = np.cumsum(nHouse)
     
    #  Assign household id (hhID) 
    a = 0
    for i in nHouseidx:
        b =  nHouse_cuml[i]
        household_df.loc[range(a,b),'hhID'] = np.arange(a + 1, b + 1, dtype=int) # First hhID index =1
        household_df.loc[range(a,b),'zoneid'] = landuse.loc[i,'zoneid']
        household_df.loc[range(a,b),'zoneType'] = landuse.loc[i,'avgincome']
        a = b
    
    del a,b
    household_df['hhID'] = household_df['hhID'].astype(int)
      
    #%% Step 3: Identify the household size and assign "nInd" values to each household
    a_g = 0
    for i in nHouseidx:
        b_g = nHouse_cuml[i]
        # Find Total of every different nInd number for households
        household_num = nHouse[i] * household_prop
        # Round the household numbers for various numbers of individuals 
        # without exceeding total household number
        cumsum_household_num = np.round(np.cumsum(household_num)).astype('int32')
        cumsum_household_num_diff = np.diff(cumsum_household_num)
        first_val = nHouse[i] - sum(cumsum_household_num_diff)
        household_num_round = np.insert(cumsum_household_num_diff,0,first_val)
        
        #Generate a column vector     
        d_value = t1_l1
        d_number = cumsum_household_num
        insert_vector = np.ones(d_number[-1])
        a, count =0, 0
        for value in d_value:
            b = d_number[count]
            #This works for numbers but not for strings
            subvector = np.empty(household_num_round[count]) #
            subvector.fill(value) #
            insert_vector[a:b] = subvector #
            a = b
            count+=1
        del a,b  
        insert_vector = np.random.permutation(insert_vector)
        
        household_df.loc[range(a_g,b_g), 'nIND'] = insert_vector 
        a_g = b_g
    
    del a_g, b_g, count,insert_vector,subvector
    
    household_df['nIND'] = household_df['nIND'].astype(int)
    
    #%% Step 4: Identify and assign income type of the households
    # Table 2 states the % of various income groups in different income zones
    # Convert Table 2 to numpy array
    # for row in range((len(tables['t2'][0]))):
    #     tables['t2'][0][row]=np.fromstring(tables['t2'][0][row],dtype=float,sep=',') 
    
    t2 = np.array(tables['t2'][0])
    
    count = 0
    
    for inc in avg_income_types:
        #Find indices corresponding to a zone type
        itidx = household_df['zoneType'] == inc
        if sum(itidx) ==0: #i.e. this income zone doesn't exist in the landuse data
            count+=1 
            continue
            
        income_entries = t2[count]*sum(itidx)    
        d_limit = sum(itidx) # Size of array to match after rounding off
        d_value = avg_income_types[income_entries!=0]
        d_number = income_entries[income_entries!=0] #ip
        
        insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle') 
        count+=1    
        household_df.loc[itidx, 'income'] = insert_vector 
    
    del count,insert_vector

    #%% Step 5: Identify and assign a unique ID for each  individual
    
    #Asumption 2: Gender distribution is same for different income types 
    
    #Preallocate a dataframe with nan to hold the individual layer
    nindiv = int(sum(household_df['nIND'])) # Total number of individuals
    individual_df = pd.DataFrame(np.nan, index = range(nindiv),
                            columns=['hhID', 'indivID', 'gender', 'age','head',
                                     'eduAttStat','indivFacID_1','indivFacID_2',
                                     'indivfacid',
                                     'schoolEnrollment','labourForce','employed'])
    individual_df['indivID'] = np.arange(1, nindiv + 1, dtype=int)
    
    #%% Step 6: Identify and assign gender for each individual
    #%% Step 6: Identify and assign gender for each individual
    # Convert the gender distribution table 3 to numpy array
    tables['t3'][0] = np.array(tables['t3'][0][0],dtype=float) 
    
    gender_probs = tables['t3'][0]
    
    if len(gender_probs) >= 3:
        # Dynamic handling for 3 or more genders (1=Female, 2=Male, 3=Other, etc.)
        gender_value = np.arange(1, len(gender_probs) + 1, dtype=int)
        # Normalize just in case, though validation checks sum approx 1.0
        gender_probs_norm = gender_probs / np.sum(gender_probs)
        gender_number = gender_probs_norm * nindiv
    else:
        # Fallback to original 2-gender logic if only 1 or 2 values provided (assumes Female, Male)
        if len(gender_probs) > 0:
             female_p = gender_probs[0]
        else:
             female_p = 0.5 # Default fallback
        male_p = 1.0 - female_p
        gender_value = np.array([1, 2], dtype=int) # 1=Female, 2=Male
        gender_number = np.array([female_p, male_p]) * nindiv
    
    d_limit = nindiv # Size of array to match after rounding off
    d_value = gender_value
    d_number = gender_number 
    
    insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
    individual_df.loc[range(nindiv),'gender'] = insert_vector
    individual_df['gender'] = individual_df['gender'].astype('int')
    
    #%% Step 7: Identify and assign age for each individual
    #Assumption 3: Age profile is same for different income types
    #Convert the age profile wrt gender distribution table 4 to numpy array
    # Determine age profile labels length from the first row of table 4
    if len(tables['t4'][0]) > 0:
        age_bins_count = len(np.array(tables['t4'][0][0], dtype=float))
    else:
        # Fallback default if table 4 is somehow empty
        age_bins_count = 1 
        
    ageprofile_value = np.arange(1, age_bins_count + 1, dtype=int)
    
    # Prepare distribution list for all genders
    t4_rows = tables['t4'][0]
    t4_distributions = []
    
    for i in range(len(gender_value)):
        if i < len(t4_rows):
            t4_distributions.append(np.array(t4_rows[i], dtype=float))
        else:
            # If not enough rows in Table 4, reuse the last available row
            log_warning(f"Age distribution missing for gender {gender_value[i]}. Using distribution from previous gender.")
            if len(t4_distributions) > 0:
                t4_distributions.append(t4_distributions[-1])
            else:
                t4_distributions.append(np.ones(age_bins_count) / age_bins_count)

    t4 = np.array(t4_distributions)
    
    for i in range(len(gender_value)):
        gidx = individual_df['gender'] == gender_value[i]
        count_g = sum(gidx)
        if count_g == 0: continue
            
        d_limit = count_g
        d_value = ageprofile_value
        d_number = t4[i] * count_g    
        insert_vector = dist2vector(d_value, d_number, d_limit, 'shuffle')
        individual_df.loc[gidx,'age'] = insert_vector
    
    individual_df['age'] = individual_df['age'].astype(int) 
    
    #%% Step 8: Identify and assign education attainment status for each individual
    
    # Assumption 4: Education Attainment status is same for different income types 
    # Education Attainment Status (Meta Data)
    # 1 - Only literate
    # 2 - Primary school
    # 3 - Elementary sch.
    # 4 - High school
    # 5 - University and above
    #Convert the educational status distribution table 5 to numpy array
    education_value = np.array([1,2,3,4,5], dtype=int)
    
    # Prepare distribution list for all genders
    t5_rows = tables['t5'][0]
    t5_distributions = []
    
    for i in range(len(gender_value)):
        if i < len(t5_rows):
            t5_distributions.append(np.array(t5_rows[i], dtype=float))
        else:
             # If not enough rows in Table 5, reuse the last available row
            log_warning(f"Education distribution missing for gender {gender_value[i]}. Using distribution from previous gender.")
            if len(t5_distributions) > 0:
                t5_distributions.append(t5_distributions[-1])
            else:
                t5_distributions.append(np.ones(len(education_value)) / len(education_value))

    t5 = np.array(t5_distributions)
    
    for i in range(len(gender_value)):
        gidx = individual_df['gender'] == gender_value[i]    
        count_g = sum(gidx)
        if count_g == 0: continue

        d_limit = count_g
        d_value = education_value
        d_number = t5[i] * count_g   
        insert_vector = dist2vector(d_value, d_number, d_limit, 'shuffle')
        individual_df.loc[gidx,'eduAttStat'] = insert_vector
    
    individual_df['eduAttStat'] = individual_df['eduAttStat'].astype(int)
    
    #%% Step 9: Identify and assign the head of household to corresponding hhID
    

    # Assumption 5: Head of household is dependent on gender
    # Assumption 6: Only (age>20) can be head of households
    
    # Determine Age Limits for Head of Household from Table 4b
    # Default values (Index of age bins): > 4 (so 5 to infinity)
    min_hh_age_idx = 5
    max_hh_age_idx = 999 

    if len(tables['t4b']) > 0 and len(tables['t4b'][0]) > 0:
        try:
             # Assuming single row with [min_age, max_age]
             t4b_row = np.array(tables['t4b'][0][0], dtype=float)
             if len(t4b_row) >= 2:
                 min_hh_age_idx = int(t4b_row[0])
                 max_hh_age_idx = int(t4b_row[1])
        except Exception as e:
            log_warning(f"Failed to parse Table 4b for Head of Household dynamic age limits. Using defaults (>4). Error: {e}")

    #Convert the head of houseold distribution table 6 to numpy array
    tables['t6'][0] = np.array(tables['t6'][0][0],dtype=float) 
    
    t6_probs = tables['t6'][0]
    hh_probs = []
    
    if len(gender_value) > 2:
         # Dealing with 3+ genders
         if len(t6_probs) >= len(gender_value):
              hh_probs = t6_probs[:len(gender_value)]
         else:
              # Start with provided probabilities
              hh_probs = list(t6_probs)
              # If only female probability provided (implied), calculate remainder
              if len(hh_probs) == 1:
                   remainder = 1.0 - hh_probs[0]
                   # Distribute remainder to other genders.
                   # Simplest assumption: Male (index 1) gets the remainder logic if available
                   if len(gender_value) >= 2:
                        hh_probs.append(remainder)
                   # Fill any remaining with 0 or split remainder? 
                   # Sticking to safe 0 for any unspecified extra genders if not explicitly provided
                   while len(hh_probs) < len(gender_value):
                        hh_probs.append(0.0)
              else:
                   # Fill missing with 0
                   while len(hh_probs) < len(gender_value):
                        hh_probs.append(0.0)
         
         hh_probs = np.array(hh_probs)
         # Re-normalize if sum != 1 (and not all zero)
         if np.sum(hh_probs) > 0:
              hh_probs = hh_probs / np.sum(hh_probs)
              
    else:
        # Fallback to original logic
        if len(t6_probs) > 0:
            female_hh = t6_probs[0]
        else:
            female_hh = 0.5 # Default
        male_hh = 1.0 - female_hh
        hh_probs = np.array([female_hh, male_hh])

    # Calculate the number of household heads by gender
    hh_number = hh_probs * sum(nHouse)
    hh_number = hh_number.astype(int)
    
    # Adjust for rounding errors: assign difference to the largest group
    diff = sum(nHouse) - np.sum(hh_number)
    if diff != 0:
        max_idx = np.argmax(hh_probs)
        hh_number[max_idx] += diff
        
    unassigned_heads = 0
    
    for i in range(len(gender_value)): #Assign female and male candidates
        # Using dynamic age limits from Table 4b (or defaults)
        gaidx= (individual_df['gender'] == gender_value[i]) & \
                (individual_df['age'] >= min_hh_age_idx) & (individual_df['age'] <= max_hh_age_idx)
        
        #Index of household head candidates in individual_df
        # Ensure we only pick passing candidates
        curr_candidates_idx =  list(individual_df.loc[gaidx].index)    
        
        target_count = hh_number[i] + unassigned_heads
        
        if len(curr_candidates_idx) >= target_count:
             ga_hh_idx = random.sample(curr_candidates_idx, target_count)
             unassigned_heads = 0
        else:
             # Not enough candidates! Take all available
             ga_hh_idx = curr_candidates_idx
             unassigned_heads = target_count - len(curr_candidates_idx)
             log_warning(f"Insufficient household head candidates for gender {gender_value[i]}. Taking all {len(curr_candidates_idx)} available. Excess needed: {unassigned_heads}")

        individual_df.loc[ga_hh_idx,'head'] = 1
        
    # Fallback Mechanism
    if unassigned_heads > 0:
        log_warning(f"Attempting to fill {unassigned_heads} remaining household head slots from general eligible population.")
        # Candidates: Age appropriate, not already head (NaN or not 1)
        # Note: individual_df['head'] contains 1s and NaNs at this stage usually
        # We simply exclude those we just set
        
        general_candidates_mask = (individual_df['age'] >= min_hh_age_idx) & (individual_df['head'] != 1)
        general_candidates_idx = list(individual_df.loc[general_candidates_mask].index)
        
        if len(general_candidates_idx) >= unassigned_heads:
            extra_heads_idx = random.sample(general_candidates_idx, unassigned_heads)
            individual_df.loc[extra_heads_idx, 'head'] = 1
            unassigned_heads = 0
            log_warning("Successfully filled remaining household head slots from backup candidates.")
        else:
            # Critical shortage - take everyone we can
            individual_df.loc[general_candidates_idx, 'head'] = 1
            remaining = unassigned_heads - len(general_candidates_idx)
            #log_error(f"CRITICAL: Could not find enough eligible household heads even after fallback! Missing {remaining} heads. Simulation may have unassigned households.")
        
    # 1= household head, 2= household members other than the head    
    individual_df.loc[individual_df['head'] != 1,'head'] =0
    
    #Assign household ID (hhID) randomly
    hhid_temp = household_df['hhID'].tolist()
    random.shuffle(hhid_temp)
    
    num_heads = sum(individual_df['head'] == 1)
    required_heads = len(hhid_temp)
    if num_heads != required_heads:
        if num_heads < required_heads:
            missing_heads = required_heads - num_heads
            error_msg = (
                f"Household Head Assignment Failed.\n"
                f"Required exactly {required_heads} household heads, but only assigned {num_heads}.\n"
                f"Missing {missing_heads} heads.\n\n"
                f"Likely causes:\n"
                f"1. Table 4 (Age Distribution) does not produce enough adults efficiently.\n"
                f"2. Table 4b (Head of Household Age Limits) is too restrictive.\n"
                f"3. Table 6 (Head of Household Gender Distribution) target is not feasible with the given population.\n\n"
                f"Please review your input tables (especially Table 4 and 4b) to ensure enough eligible adults exist."
            )
        else:
            excess_heads = num_heads - required_heads
            error_msg = (
                f"Household Head Assignment Failed.\n"
                f"Required exactly {required_heads} household heads, but assigned {num_heads}.\n"
                f"Excess heads: {excess_heads}.\n\n"
                f"This is not a shortage of eligible candidates. It means more than one individual was marked "
                f"as household head for some households before hhID assignment.\n"
                f"Please review the head-assignment inputs and logic, especially Table 6 "
                f"(Head of Household Gender Distribution) and any custom age-limit settings in Table 4b."
            )

        # Detailed logging is handled by the main application exception handler
        raise RuntimeError(error_msg)
        
    individual_df.loc[individual_df['head'] == 1,'hhID'] = hhid_temp
    
    #%% Step 10: Identify and assign the household that each individual belongs to
    # In relation with Assumption 6, no individuals under 20 years of age can live
    # alone in an household
    individual_df_temp = individual_df[individual_df['head']==0]
    individual_df_temp_idx = list(individual_df_temp.index)
    #hhidlist = household_df['hhID'].tolist()
    for i in range(1,len(t1_l1)): #Loop through household numbers >1
        hh_nind = t1_l1[i] # Number of individuals in households
        # Find hhID corresponding to household numbers
        hh_df_idx = household_df['nIND']== hh_nind
        hhidx = household_df.loc[hh_df_idx,'hhID'].tolist()
        #Random shuffle hhidx here
        amph = hh_nind -1 # additional member per household
        for j in range(amph):
            # Randomly select len(hhidx) number of indices from individual_df_temp_idx
            idtidx = random.sample(individual_df_temp_idx, len(hhidx))
            individual_df.loc[idtidx,'hhID'] = hhidx
            #Remove idtidx before next iteration
            individual_df_temp = individual_df_temp.drop(index=idtidx)
            individual_df_temp_idx = list(individual_df_temp.index)

    # FIX
    missing = individual_df["hhID"].isna()
    if missing.any():
        # İstersen fail-fast:
        # raise ValueError(f"{missing.sum()} individuals have no hhID after Step 10")

        # Ya da otomatik tamamla (en pratik):
        all_hhids = household_df["hhID"].astype(int).to_numpy()
        individual_df.loc[missing, "hhID"] = np.random.choice(all_hhids, size=missing.sum(), replace=True)

    # Artık güvenle int'e çevir            
    individual_df['hhID'] = individual_df['hhID'].astype(int)
    
    #%% Step 10a: Identify school enrollment for each individual
    # Final output 0 = not enrolled in school, 1 = enrolled in school 
    # Assumption 16: Schooling age limits- AP2 and AP3 ( 5 to 18 years old) 
    # can go to school
    # Convert distribution table 5a to numpy array
    # Table 5a contains school enrollment probability
    for row in range((len(tables['t5a'][0]))):
        tables['t5a'][0][row]=np.array(tables['t5a'][0][row],dtype=float) 
    t5a = np.array(tables['t5a'][0]) # Table 5a
    # Find individuals with age between 5-18 (these are students)
    # Also find individual Id of students and household Id of students
    
    # Determine Age Limits for School Enrollment from Table 4c
    # Default values (Index of age bins): 2, 3, 4 (so 5-9, 10-14, 15-19 typically)
    min_school_age_idx = 2
    max_school_age_idx = 4 

    if 't4c' in tables and len(tables['t4c']) > 0 and len(tables['t4c'][0]) > 0:
        try:
             # Assuming single row with [min_age_idx, max_age_idx]
             t4c_row = np.array(tables['t4c'][0][0], dtype=float)
             if len(t4c_row) >= 2:
                 min_school_age_idx = int(t4c_row[0])
                 max_school_age_idx = int(t4c_row[1])
        except Exception as e:
            log_warning(f"Failed to parse Table 4c for School Enrollment dynamic age limits. Using defaults (2-4). Error: {e}")

    agemask = (individual_df['age'] >= min_school_age_idx) & (individual_df['age'] <= max_school_age_idx) 
    school_df = pd.DataFrame(np.nan, index = range(sum(agemask)),
                    columns=['indivID','hhID','eduAttStatH','income','enrollment'])
    school_df_idx = individual_df.loc[agemask,'indivID'].index
    school_df.set_index(school_df_idx, inplace=True)
    school_df['indivID'] = individual_df.loc[agemask,'indivID']
    school_df['hhID'] = individual_df.loc[agemask,'hhID']
    # Then, pick a slice of individual_df corresponding to the household a student
    # belongs to. From there, Pick eduAtt status of head of household. To expedite
    # computation, dataframe columns have been converted to list
    school_df_hhid_list = list(school_df['hhID'])
    temp_df = individual_df[individual_df['hhID'].isin(school_df_hhid_list)]
    head4school_df = temp_df[temp_df['head'] == 1]
    head4school_df_hhID_list = list(head4school_df['hhID'])
    head4school_df_edus_list = list(head4school_df['eduAttStat'])
    school_df_edu_list = np.ones(len(school_df_hhid_list))*np.nan
    
    # Label 'lowIncomeA' and 'lowIncomeB' = 1, 'midIncome' =2, 'highIncome' =3
    household_df_hhid_list = list(household_df['hhID'])
    #Use .copy() to avoid SettingwithCopyWarning
    income4school_df=household_df[household_df['hhID'].\
                                  isin(school_df_hhid_list)].copy()
    li_mask = (income4school_df['income'] == avg_income_types[0]) |\
              (income4school_df['income'] == avg_income_types[1]) 
    lm_mask = income4school_df['income'] == avg_income_types[2]
    lh_mask = income4school_df['income'] == avg_income_types[3]
    income4school_df.loc[li_mask,'income'] = 1
    income4school_df.loc[lm_mask,'income'] = 2
    income4school_df.loc[lh_mask,'income'] = 3
    income4school_df_income_list = list(income4school_df['income'])
    income4school_df_hhID_list = list(income4school_df['hhID'])
    school_df_income_list = np.ones(len(school_df_hhid_list))*np.nan
    school_df_edu_list_df = school_df[['hhID']].merge(head4school_df[['hhID','eduAttStat']], how='left', on='hhID')
    school_df_edu_list= list(school_df_edu_list_df['eduAttStat'])
    school_df_income_list_df = school_df[['hhID']].merge(income4school_df[['hhID','income']], how='left', on='hhID')
    school_df_income_list= list(school_df_income_list_df['income'])
    school_df.loc[school_df.index, 'eduAttStatH'] = school_df_edu_list 
    
    # Fill possible NaNs before casting to integer
    school_df['eduAttStatH'] = school_df['eduAttStatH'].fillna(1).astype(int)
    
    school_df['income'] = school_df_income_list
    school_df['income'] = school_df['income'].fillna(1).astype(int)
      
    #assign school enrollment (1 = enrolled, 0 = not enrolled)
    for incomeclass in range(1,4): # Income class 1,2,3
        for head_eduAttStat in range(1,6): # Education attainment category 1 to 5
            enrmask = (school_df['income'] == incomeclass) &\
                      (school_df['eduAttStatH'] == head_eduAttStat)
            no_of_pstudents = sum(enrmask) # Number of potential students
            if no_of_pstudents ==0: #continue if no students exist for given case
                continue
            i,j = incomeclass-1, head_eduAttStat-1 # indices to access table 5a
            d_limit = no_of_pstudents # Size of array to match after rounding off
            d_value = [1,0] #1= enrolled, 0 = not enrolled
            d_number = np.array([t5a[i,j], 1-t5a[i,j]])*no_of_pstudents        
            insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle') 
            school_df.loc[enrmask,'enrollment'] = insert_vector
            
    school_df['enrollment']= school_df['enrollment'].astype(int)
    # Substitute the enrollment status back to individual_df dataframe
    individual_df.loc[school_df.index,'schoolEnrollment']=  school_df['enrollment']   
    
    
    #%% Step 11: Identify approximate total residential building area needed
    # (approxDwellingAreaNeeded_sqm) 
    # Assumption 7a on Average dwelling area (sqm) for different income types.
    
    # The output is stored in the column 'totalbldarea_res' in landuse_res_df,
    # which represents the total buildable area
    
    #Sub dataframe of landuse type containing only residential areas
    landuse_res_df = landuse.loc[nHouse.index].copy()
    landuse_res_df.loc[nHouse.index,'nHousehold'] = nHouse
    hh_temp_df = household_df.copy()
    
    # Create mapping for replacement
    income_map = {avg_income_types[i]: average_dwelling_area[i] for i in range(len(avg_income_types))}
    # Apply mapping using map() which is cleaner and avoids downcasting warnings
    # since we are transforming the entire column from string to float.
    # Apply mapping
    hh_temp_df['income'] = hh_temp_df['income'].map(income_map)
    for index in landuse_res_df.index: # Loop through each residential zone
        zoneid = landuse_res_df['zoneid'][index]
        sum_part = hh_temp_df.loc[hh_temp_df['zoneid']==zoneid,'income'].sum()
        landuse_res_df.loc[index, 'approxDwellingAreaNeeded_sqm'] = sum_part
    hh_temp_df.rename(columns={'income':'dwelling_area'}, inplace=True)   
    # Zones where no households live i.e. potential commercial or industrial zones    
    noHH = nHouse_all[nHouse_all<=0].index
    landuse_ic_df = landuse.loc[noHH].copy()
    landuse_ic_df['area'] = landuse_ic_df['area']*10000 # Convert hectare to sq m

    # --- PATCH: kolonlar her koşulda var olsun (empty df / tüm satırlar continue olsa bile) ---
    landuse_ic_df["AreaAvailableForInd"] = 0.0
    landuse_ic_df["AreaAvailableForCom"] = 0.0
    landuse_ic_df["No_of_ind_buildings"] = 0.0
    landuse_ic_df["No_of_com_buildings"] = 0.0
    # --- /PATCH ---

    
    #%% Steps 12,13,14,15: 
    #    Identify number of residential buildings and generate building layer 
    
    # Table 7 contains Number of storeys distribution for various LRS and LUT
    # Table 11 contains code compliance distribution for various LRS and LUT
    t7= tables['t7'][0]
    t11 = tables['t11'][0]

    # Convert Table 8 to numpy array
    for row in range((len(tables['t8'][0]))):
        tables['t8'][0][row]=np.array(tables['t8'][0][row],dtype=float) 
    t8 = np.array(tables['t8'][0]) # Table 8

    # VALIDATE SHAPES for Table 7, 8, 11
    for row_idx, row in enumerate(t8):
        if len(row) != len(lrs_types):
            raise ValueError(f"Table 8 Error: LRS distribution list ({len(row)}) at row {row_idx+1} does not match the expected number of LRS types ({len(lrs_types)}). Please check Table 8.")

    for lut_key, lut_val in lutidx.items():
        if lut_val < len(t7):
            for lrs_key, lrs_val in lrsidx.items():
                if lrs_val < len(t7[lut_val]):
                    t7dist = np.fromstring(str(t7[lut_val][lrs_val]), dtype=float, sep=',')
                    if len(t7dist) != len(storey_range):
                        raise ValueError(f"Table 7 Error: Storey distribution list ({len(t7dist)}) for LUT='{lut_key}' and LRS='{lrs_key}' does not match the expected number of Storey classes ({len(storey_range)}).")
                    
                    if lut_val < len(t11):
                        t11_row = t11[lut_val]
                        if len(t11_row) == len(code_level) and not any(',' in str(c) for c in t11_row):
                            t11dist = np.array(t11_row, dtype=float)
                        elif lrs_val < len(t11_row):
                            t11dist = np.fromstring(str(t11_row[lrs_val]), dtype=float, sep=',')
                        else:
                            t11dist = np.array([])

                        if len(t11dist) != len(code_level):
                            raise ValueError(f"Table 11 Error: Code Compliance distribution list ({len(t11dist)}) for LUT='{lut_key}' and LRS='{lrs_key}' does not match the expected number of levels ({len(code_level)}). Please check if Table 11 has {len(code_level)} columns or CSV strings.")
    
    no_of_resbldg = 0
    footprint_base_sum = 0
    footprint_base_L,storey_L,lrs_L,zoneid_L,codelevel_L = [],[],[],[],[]
    
    for i in landuse_res_df.index: #Loop through zones 
        zoneid = landuse_res_df['zoneid'][i]
        #totalbldarea_res = landuse_res_df['totalbldarea_res'][i]
        #totalbldarea_res is the total residential area that needs to be built
        totalbldarea_res = landuse_res_df.loc[i,'approxDwellingAreaNeeded_sqm']
        avgincome = landuse_res_df['avgincome'][i]
        lut_zone = landuse_res_df['luf'][i]
        fpt_range = fpt_area[avgincome]
        # Generate a vector of footprints such that sum of all the footprints in
        # lenmax equals maximum possible length of vector of building footprints
        lenmax = int(totalbldarea_res/np.min(fpt_range))
        footprints_temp = np.random.uniform(np.min(fpt_range),\
                                         np.max(fpt_range), size=(lenmax,1))
        footprints_temp = footprints_temp.reshape(len(footprints_temp),)
        # Select LRS using multinomial distribution and Table 8
        lrs_number=multinomial(len(footprints_temp), t8[lutidx[lut_zone]],size=1) 
        lrs_vector=np.array(dist2vector(lrs_types,lrs_number,\
                                                np.sum(lrs_number),'shuffle')) 
    
        # Select storeys in a zone for various LRS using multinomial distribution
        #storey_vector = np.array([],dtype=int)
        storey_vector = np.array(np.zeros(len(lrs_vector),dtype=int)) #must be assigned after loop
        for lrs in lrs_types: # Loop through LRS types in a zone
            t7row = t7[lutidx[lut_zone]] #Extract row for LUT
            #Extract storey distribution in row for LRS
            t7dist = np.fromstring(str(t7row[lrsidx[lrs]]),dtype=float, sep=',')
            lrs_pos = lrs_vector==lrs
            storey_number = multinomial(sum(lrs_pos),t7dist,size=1)
            storey_vector_part = np.array([],dtype=int)
            for idx,st_range in storey_range.items(): #Loop through storey classes
                sv_temp = \
                    randint(st_range[0],st_range[1]+1,storey_number[0][idx])
                storey_vector_part = \
                    np.concatenate((storey_vector_part,sv_temp),axis =0)
            # Need to shuffle storey_vector before multiplying and deleting
            #extra values, otherwise 100% of storeys will be low rise, resulting in 
            #larger number of buildings        
            np.random.shuffle(storey_vector_part)         
            storey_vector[lrs_pos] =storey_vector_part
        # Select code compliance level for various LRS using multinomial dist
        cc_vector = [] # code compliance vector for a zone
        for lrs in lrs_types: # for each LRS in a zone
            t11row = t11[lutidx[lut_zone]]
            # Support both single-cell CSV and multi-column formats
            if len(t11row) == len(code_level) and not any(',' in str(c) for c in t11row):
                t11dist = np.array(t11row, dtype=float)
            else:
                t11dist = np.fromstring(str(t11row[lrsidx[lrs]]), dtype=float, sep=',')
            lrs_pos = lrs_vector==lrs
            cc_number = multinomial(sum(lrs_pos),t11dist,size=1)
            cc_part = dist2vector(code_level, cc_number,sum(lrs_pos),'shuffle')
            cc_vector += cc_part
        random.shuffle(cc_vector)
        
        #If it is necessary to equalize number of storeys = number of households
        storey_vector_cs = np.cumsum(storey_vector)
        stmask = storey_vector_cs <= landuse_res_df.loc[i,'nHousehold']
        if sum(stmask)>0:
            stlimit_idx = np.max(np.where(stmask))+1
            stlimit_idx_range = range(stlimit_idx+1,len(footprints_temp))
        else:
            stlimit_idx_range = range(1,len(footprints_temp))
        
        footprints_base = footprints_temp   #Footprints without storey  
        dwellingArea_temp= footprints_temp*storey_vector
        dwellingArea_temp_cs = np.cumsum(dwellingArea_temp)
        
        #If it is necessary to equalize required footprint = provided footprint
        #OPTIONAL:Here, introduce a method to match total buildable area (dwelling)
        # fpmask = dwellingArea_temp_cs <= totalbldarea_res
        # #Indices of footprints whose sum <= dwelling area needed in a zone
        # # '+ 1' provides slightly more dwelling area than needed
        # footprints_idx = np.max(np.where(fpmask)) + 1 
        
        # Delete additional entries in the vectors for footprint, lrs and storeys
        # which do not fit into total buildable area
        #ftrange = range(footprints_idx+1,len(dwellingArea_temp))
        
        ftrange = stlimit_idx_range
        
        dwellingArea = np.delete(dwellingArea_temp,ftrange)
        footprints_base = np.delete(footprints_base,ftrange)
        lrs_vector_final = np.delete(lrs_vector,ftrange)
        storey_vector_final = np.delete(storey_vector,ftrange)
        cc_vector = np.array(cc_vector)
        cc_vector_final = np.delete(cc_vector,ftrange)
        no_of_resbldg += len(dwellingArea) 
        
        #footprint_base_sum+=np.sum(footprints_base)    
        # Store the vectors in lists for substitution in dataframe 
        footprint_base_L +=  list(footprints_base)
        storey_L += list(storey_vector_final)
        lrs_L += list(lrs_vector_final)
        zoneid_L += [zoneid]*len(dwellingArea) 
        codelevel_L += list(cc_vector_final)
        
        landuse_res_df.loc[i,'footprint_sqm'] = np.sum(footprints_base)
        landuse_res_df.loc[i,'dwellingAreaProvided_sqm'] = np.sum(dwellingArea)
        
        landuse_res_df.loc[i, 'Storey_units'] = sum(storey_vector_final)
        #'No_of_res_buildings' denotes total residential + ResCom buildings
        landuse_res_df.loc[i, 'No_of_res_buildings'] = len(footprints_base)
        # Check distribution after deletion (for debugging) by counting LR
        #print(sum(storey_vector_final<5)/len(storey_vector_final))
    
    # landuse_res_df['area'] denotes the total buildable area   
    landuse_res_df['area'] *= 10000 # Convert hectares to sq m, 1ha =10^4 sqm
    
    # landuse_res_df['builtArea_percent'] denotes the percentage of total 
    # buildable area that needs to be built to accomodate the projected population
    landuse_res_df['builtArea_percent'] =\
        landuse_res_df['footprint_sqm']/landuse_res_df['area']*100
    
    #ADD HERE : EXCEPTION HANDLING for built area exceeding available area
    
    #print(no_of_resbldg) 
    
    #ADD: Check if calculated footprint exceeds total buildable area (landuse.area)  
    
    #Create and populate the building layer, with unassigned values as NaN
    resbld_df = pd.DataFrame(np.nan, index = range(0, no_of_resbldg),
                            columns=['zoneid', 'bldID', 'specialFac', 'repValue',
                                      'nHouse', 'residents', 'expStr','fptarea',
                                      'occbld','lrstype','codelevel',
                                      'nstoreys'])
    # Fix future warning by setting object columns dtype
    for col in ['occbld', 'lrstype', 'codelevel', 'expStr']:
        resbld_df[col] = resbld_df[col].astype('object')
    resbld_range = range(0,no_of_resbldg)
    #resbld_df.loc[resbld_range,'bldID'] = list(range(1,no_of_resbldg+1))
    resbld_df.loc[resbld_range,'zoneid'] = zoneid_L
    resbld_df['zoneid'] = resbld_df['zoneid'].astype('int')
    resbld_df.loc[resbld_range,'occbld'] = 'Res'
    resbld_df.loc[resbld_range,'specialFac'] = 0
    resbld_df.loc[resbld_range,'fptarea'] = footprint_base_L
    resbld_df.loc[resbld_range,'nstoreys'] = storey_L
    resbld_df.loc[resbld_range,'lrstype'] = lrs_L
    resbld_df.loc[resbld_range,'codelevel'] = codelevel_L
    
    #%% Assign zoneIDs and building IDs for Res and ResCom
    # Assign 'ResCom' status based on Table 9
    # Assumption: Total residential buildings = Res + ResCom
    # Convert Table 9 to numpy array
    # Table 9 contains occupancy type with respect to various LUT
    # Occupancy types: Residential (Res), Industrial (Ind), Commercial (Com)
    # Residential and commercial mixed (ResCom)
    for row in range((len(tables['t9'][0]))):
        tables['t9'][0][row]=np.array(tables['t9'][0][row],dtype=float) 
    t9 = np.array(tables['t9'][0]) # Table 9
    
    #available_LUT = list(set(landuse_res_df['luf']))
    available_zoneID = list(set(resbld_df['zoneid']))
    for zoneid in available_zoneID: #Loop through zones
        zonemask = resbld_df['zoneid'] == zoneid
        zone_idx = list(zonemask.index.values[zonemask])
        lutlrdidx=landuse_res_df[landuse_res_df['zoneid']==zoneid].index.values[0]
        #Occupancy type distribution for a zone
        occtypedist = t9[lutidx[ landuse_res_df['luf'][lutlrdidx]]]
        no_of_resbld = sum(zonemask) # Number of residential buildings in a zone
        # if mixed residential+commercial buildings as well as residential buildings exist
        if occtypedist[3] !=0 and occtypedist[0] !=0: 
            # nrc = number of mixed res+com buildings in a zone
            nrc = int(occtypedist[3]/occtypedist[0]*no_of_resbld)
        elif occtypedist[3] !=0 and occtypedist[0] ==0:
            nrc = int(no_of_resbld)
        else: # if only residential buildings exist
            continue
        
        # Ensure nrc does not exceed the available building count in that zone
        nrc = min(nrc, len(zone_idx))
        nrc_idx = random.sample(zone_idx, nrc)
        resbld_df.loc[nrc_idx,'occbld'] = 'ResCom'
    
    #Assign building Ids for res and rescom buildings
    lenresbld = len(resbld_df)
    resbld_df.loc[range(0,lenresbld),'bldID'] = list(range(1,lenresbld+1))
    resbld_df['bldID'] = resbld_df['bldID'].astype('int')
    
    #%% STEP16: Identify and assign number of households and residents for each 
    #residential building
    # This part assigns multiple households to a single storey with adequate space.
    #Assign nHouse, residents. All the households and residents must be assigned
    #to this layer.
    
    hh_zid = np.unique(household_df['zoneid']).astype(int)
    household_df['dwelling_area'] = hh_temp_df['dwelling_area']
    
    # Match the dwellings needed to the dwellings available
    for zid in hh_zid:#zoneIDs between households and buildings must be consistent.
        zidmask_rdf = resbld_df['zoneid']==zid
        bldid_temp = resbld_df.loc[zidmask_rdf,'bldID'].copy()
        nstoreys_temp = resbld_df.loc[zidmask_rdf,'nstoreys'].copy()
        fptarea_temp = resbld_df.loc[zidmask_rdf,'fptarea']
    
        for ada in average_dwelling_area:
            if bldid_temp.empty:
                continue
            #This method keeps people of same income category in same building.
     
            #hh_per_storey = 3 # dwellings_fptarea
            hh_per_storey = round(fptarea_temp/ada,0)
            hh_per_storey[hh_per_storey==0]=1
            
            dwelling_multiplier = np.ones(len(bldid_temp))*hh_per_storey*nstoreys_temp
                         #resbld_df.loc[zidmask_rdf,'nstoreys']
            dwelling_multiplier = dwelling_multiplier.to_numpy(dtype=int)
            #dwelling_multiplier[dwelling_multiplier==0] = 1
            dwelling4zid = dist2vector(bldid_temp,dwelling_multiplier,\
                                       np.sum(dwelling_multiplier),'DoNotShuffle')
            dwelling4zid = list(map(int,dwelling4zid))
            
            #Assign these dwellings to households with ada in zid
            hhbid_mask = (household_df['zoneid']==zid)&(household_df['dwelling_area']==ada)
            if sum(hhbid_mask)>len(dwelling4zid):
                continue
            household_df.loc[hhbid_mask,'bldID'] = dwelling4zid[0:sum(hhbid_mask)]
              
            #Once a set of dwelling (bldid) have been assigned to an income group,
            #do not assign them again to another income group.
            dwelling2remove = set(dwelling4zid[0:sum(hhbid_mask)])
            bldid_temp = bldid_temp[~bldid_temp.isin(dwelling2remove)]
            nstoreys_temp = nstoreys_temp[bldid_temp.index]
            fptarea_temp = fptarea_temp[bldid_temp.index]  
     
    del household_df['dwelling_area']
    
    # Assign number of households and residents to residential buildings resbld_df
    
    resbld_df = resbld_df.drop(columns=['nHouse','residents'])
    # Get nind information from household table
    resbld_w_household = resbld_df[['bldID']].merge(household_df[['bldID','hhID','nIND']],\
                                                    how='inner', on='bldID')
    # Aggregate by bldid. nhouse: count of household, residents: number of individuals 
    resbld_w_household = resbld_w_household.groupby('bldID').agg({'hhID':'count',\
                          'nIND':'sum'}).reset_index().rename(columns={'hhID':'nHouse',\
                                                                    'nIND':'residents'})
    # Merge nhouse and residents columns back into building table
    resbld_df = resbld_df.merge(resbld_w_household,how='inner',on='bldID')
    
    
    #%% Step 17,18: Identify and generate commercial and industrial buildings
    # No household or individual lives in com, ind, hosp, sch zones
    # Assumption 10 and 11: Assume a certain number of commercial and industrial
    # buildings per 1000 individuals 
        
    # No commercial and industrial buildings in:recreational areas,agriculture,
    # residential (gated neighbourhood), residential (low-density)
    # But com an ind build can occur in any zone where permitted by table 9
    ncom = round(nindiv/1000*numb_com)
    nind = round(nindiv/1000*numb_ind)
    nci = np.array([ncom,nind])
    occbld_label = ['Com','Ind']
    nci_cs = np.cumsum(nci)
    indcom_df = pd.DataFrame(np.nan, index = range(0, ncom+nind),
                            columns=['zoneid', 'bldID', 'specialFac', 'repValue',
                                      'nHouse', 'residents', 'expStr','fptarea',
                                      'lut_number','occbld','lrstype','codelevel',
                                      'nstoreys'])
    # Fix future warning by setting object columns dtype
    for col in ['occbld', 'lrstype', 'expStr', 'codelevel']:
        indcom_df[col] = indcom_df[col].astype('object')
    
    t10= tables['t10'][0] # Extract Table 10
    a = 0
    for i in range(0,len(nci)): # First commercial, then industrial
        attr = t10[i]
        #Extract distributions for footprint, storeys, code compliance and LRS
        fpt_ic = np.fromstring(attr[0], dtype=float, sep=',')
        nstorey_ic = np.fromstring(attr[1], dtype=int, sep=',')
        codelevel_ic = np.fromstring(attr[2], dtype=float, sep=',')
        lrs_ic = np.fromstring(attr[3], dtype=float, sep=',')
        
        # VALIDATE SHAPES for Table 10
        if len(codelevel_ic) != len(code_level):
            raise ValueError(f"Table 10 Error: Code compliance distribution list does not match the expected size ({len(code_level)}). Please check Table 10 properties.")
        if len(lrs_ic) != len(lrs_types):
            raise ValueError(f"Table 10 Error: LRS distribution list does not match the expected number of LRS types ({len(lrs_types)}). Please check Table 10 properties.")
        range_ic = range(a,nci_cs[i])
        a = nci_cs[i]
        # Generate footprints
        indcom_df.loc[range_ic,'fptarea'] = np.random.uniform(\
                 np.min(fpt_ic),np.max(fpt_ic), size=(nci[i],1)).reshape(nci[i],)
        # Generate number of storeys
        indcom_df.loc[range_ic,'nstoreys'] =randint(np.min(nstorey_ic),\
                  np.max(nstorey_ic)+1,size=(nci[i],1)).reshape(nci[i],)
        # Generate code compliance
        cc_number_ic = multinomial(nci[i],codelevel_ic,size=1)
        indcom_df.loc[range_ic,'codelevel'] =\
                           dist2vector(code_level, cc_number_ic,nci[i],'shuffle')
        # Generate LRS
        lrs_number_ic = multinomial(nci[i],lrs_ic,size=1)
        indcom_df.loc[range_ic,'lrstype'] =\
                           dist2vector(lrs_types,lrs_number_ic,nci[i],'shuffle')
        indcom_df.loc[range_ic,'occbld']= occbld_label[i]                     
    
    # Assign number of households, Residents, special facility label
    range_all_ic = range(0,len(indcom_df))
    indcom_df.loc[range_all_ic,'nHouse'] = 0
    indcom_df.loc[range_all_ic,'residents'] = 0
    indcom_df.loc[range_all_ic,'specialFac'] = 0
    
    ind_df = indcom_df[indcom_df['occbld'] == 'Ind'].copy()
    com_df = indcom_df[indcom_df['occbld'] == 'Com'].copy()
    ind_df.reset_index(drop=True,inplace=True)
    com_df.reset_index(drop=True,inplace=True)
        
    #%% Step 19,20 Generate school and hospitals along with their attributes
    
    # Assumption 14 and 15: For example : 1 school per 10000 individuals,
    # 1 hospital per 25000 individuals
    nsch = round(nindiv/nsch_pi) # Number of schools
    nhsp = round(nindiv/nhsp_pi) # Number of hospitals
    
    if nsch == 0:
        log_warning(f"Total population {nindiv} is less than the user-specified "\
              f"number of individuals per school {nsch_pi}. So, total school for "\
              "this population = 1 (by default) \n")
        nsch = 1
    
    if nhsp == 0:
        log_warning(f"Total population {nindiv} is less than the user-specified "\
              f"number of individuals per hospital {nhsp_pi}. So, total hospital for "\
              "this population = 1 (by default) \n ")
        nhsp = 1
    
    nsh = np.array([nsch,nhsp])
    nsh_cs = np.cumsum(nsh)
    occbld_label_sh = ['Edu','Hea']
    specialFac = [1,2] # Special facility label
    schhsp_df = pd.DataFrame(np.nan, index = range(0, nsch+nhsp),
                            columns=['zoneid', 'bldID', 'specialFac', 'repValue',
                                      'nHouse', 'residents', 'expStr','fptarea',
                                      'lut_number','occbld','lrstype','codelevel',
                                      'nstoreys'])
    # Fix future warning by setting object columns dtype
    for col in ['occbld', 'lrstype', 'expStr', 'codelevel']:
        schhsp_df[col] = schhsp_df[col].astype('object')
    t14= tables['t14'][0] # Extract Table 14
    a=0
    for i in range(0,len(t14)): # First school, then hospital
        attr_sh = t14[i]
        #Extract distributions for footprint, storeys, code compliance and LRS
        if len(attr_sh) == 4:
            fpt_sh = np.fromstring(str(attr_sh[0]), dtype=float, sep=',')
            nstorey_sh = np.fromstring(str(attr_sh[1]), dtype=int, sep=',')
            codelevel_sh = np.fromstring(str(attr_sh[2]), dtype=float, sep=',')
            lrs_sh = np.fromstring(str(attr_sh[3]), dtype=float, sep=',')
        else:
            # Fallback if structure is unexpected
            fpt_sh = np.fromstring(str(attr_sh[0]), dtype=float, sep=',')
            nstorey_sh = np.fromstring(str(attr_sh[1]), dtype=int, sep=',')
            codelevel_sh = np.fromstring(str(attr_sh[2]), dtype=float, sep=',')
            lrs_sh = np.fromstring(str(attr_sh[3]), dtype=float, sep=',')
            
        # VALIDATE SHAPES for Table 14
        if len(codelevel_sh) != len(code_level):
            raise ValueError(f"Table 14 Error: Code compliance distribution list does not match the expected size ({len(code_level)}). Please check Table 14 properties.")
        if len(lrs_sh) != len(lrs_types):
            raise ValueError(f"Table 14 Error: LRS distribution list does not match the expected number of LRS types ({len(lrs_types)}). Please check Table 14 properties.")
            
        range_sh = range(a,nsh_cs[i])
        a = nsh_cs[i]
        # Generate footprints
        schhsp_df.loc[range_sh,'fptarea'] = np.random.uniform(\
                 np.min(fpt_sh),np.max(fpt_sh), size=(nsh[i],1)).reshape(nsh[i],)
        # Generate number of storeys
        schhsp_df.loc[range_sh,'nstoreys'] =randint(np.min(nstorey_sh),\
                  np.max(nstorey_sh)+1,size=(nsh[i],1)).reshape(nsh[i],)
        # Generate code compliance
        cc_number_sh = multinomial(nsh[i],codelevel_sh,size=1)
        schhsp_df.loc[range_sh,'codelevel'] =\
                           dist2vector(code_level, cc_number_sh,nsh[i],'shuffle')
        # Generate LRS
        lrs_number_sh = multinomial(nsh[i],lrs_sh,size=1)
        schhsp_df.loc[range_sh,'lrstype'] =\
                           dist2vector(lrs_types,lrs_number_sh,nsh[i],'shuffle')
        schhsp_df.loc[range_sh,'occbld']= occbld_label_sh[i] 
    
        # Assign special facility label  
        schhsp_df.loc[range_sh,'specialFac'] = specialFac[i]                 
    
    # Assign number of households, Residents, 
    range_all_sh = range(0,len(schhsp_df))
    schhsp_df.loc[range_all_sh,'nHouse'] = 0
    schhsp_df.loc[range_all_sh,'residents'] = 0
    
    #%% Assign zoneIds for Industrial and Commercial buildings
    
    # The number of industrial and commercial buildings are estimated using the
    # following 2 methods:
    # Method 1: Assumption of number of industrial or commercial building per
    #           1000 individuals. (Done in steps 17,18)
    # Method 2: Table 9 specifies what the occupancy type distribution should be 
    #           in different land use types. This gives a different estimate of the
    #           number of the buiildings as compared to Method 1. (Done here)
    # To make these two Methods compatible, the value from Method 1 is treated as 
    # the actual value of the buildings, and Method 2 is used to ensure that
    # these buildings are distributed in such a way that they follow Table 9.
    # 
    # The following method of assigning the ZoneIDs treats the mixed used zones
    # (residential, residential+commercial) and purely industrial or commercial
    # zones as 2 separate cases.
    #
    # For each of the following 2 cases, we need to first find the number of
    # industrial and commercial buildings in each zone
    
    # Case 1: For industrial/commercial buildings in residential areas_____________
    for i in landuse_res_df.index:
        #Occupancy type distribution for a zone
        otd = t9[lutidx[landuse_res_df.loc[i,'luf']]]
        if otd[1]==0 and otd[2]==0: 
            # If neither industrial nor commercial buildings exist
            landuse_res_df.loc[i,'ind_weightage'] = 0
            landuse_res_df.loc[i,'com_weightage'] = 0
            continue
        # Number of residential + rescom building
        Nrc = landuse_res_df.loc[i, 'No_of_res_buildings']
        
        # Tb = total possible number of buildings in a zone (all accupancy types)
        #      This is used as weightage factor to distribute the buildings 
        #      according to Method 2. 
        if otd[0] == 0 and otd[3]==0:
            Tb = Nrc # If neither residential nor res+com exist
            log_warning(f'If population exists, but neither residential nor '\
                  'residential+commercial buildings are allowed, there is '\
                  'inconsistency between population and current row in table 9.'\
                  'Therefore, it is assumed that total number of buildings in '\
                  f"zoneid {landuse_res_df.loc[i,'zoneid']} "\
                  '= no. of residential buildings in this zone.')
            log_info('Also, consider allowing residential and/or res+com building '\
                  'to this zone in Table 9, if it is assigned population.\n')
        else:  
            Tb = Nrc/(otd[0]+otd[3]) # If either residential or res+com exist  
    
        #Calculate the number of industrial buildings using Table 9   
        if otd[1]>0:
            landuse_res_df.loc[i,'ind_weightage'] = ceil(Tb * otd[1])
            #landuse_res_df.loc[i,'No_of_ind_buildings'] = ceil(Tb * otd[1])
        else:
           # landuse_res_df.loc[i,'No_of_ind_buildings'] = 0
           landuse_res_df.loc[i,'ind_weightage'] = 0
            
        #Calculate the number of commercial buildings using Table 9     
        if otd[2]>0:
            landuse_res_df.loc[i,'com_weightage'] = ceil(Tb * otd[2])
            #landuse_res_df.loc[i,'No_of_com_buildings'] = ceil(Tb * otd[2])
        else:
            landuse_res_df.loc[i,'com_weightage'] = 0
            #landuse_res_df.loc[i,'No_of_com_buildings'] = 0
            
    # If number of buildings (industrial/commercial) estimated from Method 2(in the
    # above steps of Case 1) exceeds the number of buildings estimated from 
    # Method 1, treat the value from Method 1 as the upper limit. 
    # Then, using the number of buildings from Method 2 as weightage factor,
    # distribute the number of  buildings from Method 1 proportionally to
    # all the mixed use zones. This situation arises if the number of 
    # industrial/commercial buildings per 1000 people is low.
    #
    # Otherwise, if the number of industrial/commercial buildings estimated from
    # Method 1 is larger than that estimated  from Method 2, it is assumed that the
    # number of buildings is large enough not to fit into the mixed use zones
    # being considered under Case 1, and the additional buildings not assigned into
    # mixed use zones is assigned under case 2 in the following section.
    # 
    # This method requires the area of industrial/commercial buildings in the 
    # mixed use zones to be checked separately to see if they fit into these zones.
    
    com_wt = landuse_res_df['com_weightage'].copy()   
    if com_wt.sum() > ncom:
        landuse_res_df['No_of_com_buildings'] = np.floor(ncom*com_wt/com_wt.sum())
    else:
        landuse_res_df['No_of_com_buildings'] = com_wt
    
    ind_wt = landuse_res_df['ind_weightage'].copy()   
    if ind_wt.sum() > nind:
        landuse_res_df['No_of_ind_buildings'] = np.floor(nind*ind_wt/ind_wt.sum())
    else:
        landuse_res_df['No_of_ind_buildings'] = ind_wt    
    
          
    landuse_res_df['No_of_ind_buildings'] =\
                        landuse_res_df['No_of_ind_buildings'].astype('int')
    landuse_res_df['No_of_com_buildings'] =\
                        landuse_res_df['No_of_com_buildings'].astype('int')
                        
    # Number and area of commercial buildings to be assigned    
    nCom_asgn = landuse_res_df['No_of_com_buildings'].sum()
    nCom_asgn_area = com_df.loc[range(0, nCom_asgn),'fptarea'].sum() 
    # Number and area of industrial buildings to be assigned
    nInd_asgn = landuse_res_df['No_of_ind_buildings'].sum()
    nInd_asgn_area = ind_df.loc[range(0,nInd_asgn),'fptarea'].sum()
    
    
    # Assign zoneid to industrial buildings (if any) in residential areas
    zoneID_r_i = dist2vector(list(landuse_res_df['zoneid']),\
                list(landuse_res_df['No_of_ind_buildings']),nInd_asgn,'shuffle')
    ind_df.loc[range(0,nInd_asgn),'zoneid'] = list(map(int,zoneID_r_i))
    
    # Assign zoneid to commercial buildings (if any) in residential areas
    zoneID_r_c = dist2vector(list(landuse_res_df['zoneid']),\
                list(landuse_res_df['No_of_com_buildings']),nCom_asgn,'shuffle')
    com_df.loc[range(0,nCom_asgn),'zoneid'] = list(map(int,zoneID_r_c))
    
    
    # Back-calculated number of commercial buildings per 1000 people        
    #nCom_asgn/(len(individual_df)/1000)
    
    # Case 2 For industrial/commercial buildings in non-residential areas__________
    
    # Number of industrial buildings that have not been assigned
    nInd_tba = int(len(ind_df) - nInd_asgn)
    # Number of commercial buildings that have not been assigned
    nCom_tba = int(len(com_df) - nCom_asgn)
    
    # Before assigning zones to buildings, find out the area available for buildings
    # in each zones. Since no population is assigned to residential and commercial
    # buildings, the number of buildings in a zone is controlled solely by area.
    for i in landuse_ic_df.index:
        #Occupancy type distribution for a zone
        try:
            otd = t9[lutidx[landuse_ic_df.loc[i,'luf']]]
        except KeyError:
            continue
        
        if otd[1]>0:
            landuse_ic_df.loc[i,'AreaAvailableForInd']=\
                                            AC_ind/100*landuse_ic_df.loc[i,'area']
        else:
            landuse_ic_df.loc[i,'AreaAvailableForInd']=0
     
        if otd[2]>0:
            landuse_ic_df.loc[i,'AreaAvailableForCom']=\
                                            AC_com/100*landuse_ic_df.loc[i,'area']
        else:
            landuse_ic_df.loc[i,'AreaAvailableForCom']=0
            
    # Check how many of the generated com/ind buildings fit into the available area
    ind_fptarea_cs = list(np.cumsum(ind_df['fptarea']))
    com_fptarea_cs = list(np.cumsum(com_df['fptarea']))
    
    # # Total areas available for commercial and industrial buildings in all zones
    # At_c= landuse_ic_df['AreaAvailableForCom'].sum()
    # At_i = landuse_ic_df['AreaAvailableForInd'].sum()
    # licidx = landuse_ic_df.index
    
    # #Assign number of industrial buildings to industrial zones____
    # # Unassigned area (c or i) = Total footprint (c or i) - area to be assigned(c or i) 
    # unassigned_ind_area = ind_fptarea_cs[-1]-nInd_asgn_area # Total - assigned
    
    # if unassigned_ind_area > At_i:
        # # Need to truncate excess industrial buildings
        # st.write('WARNING: Required industrial buildings do not fit into available '\
              # 'land area. So, excess industrial buildings have been removed.')
        # ind_df_unassignedArea = np.cumsum(ind_df.loc[range(nInd_asgn,len(ind_df)),\
                                                     # 'fptarea'])
        # ind_df_UAmask = ind_df_unassignedArea < At_i 
        # nInd_tba = sum(ind_df_UAmask)
    
    # landuse_ic_df.loc[licidx,'No_of_ind_buildings'] =\
        # landuse_ic_df['AreaAvailableForInd']/At_i*nInd_tba
    # landuse_ic_df['No_of_ind_buildings'] =\
        # landuse_ic_df['No_of_ind_buildings'].fillna(0)    
    # landuse_ic_df['No_of_ind_buildings']=\
        # landuse_ic_df['No_of_ind_buildings'].astype('int')

    # Check how many of the generated com/ind buildings fit into the available area
    ind_fptarea_cs = list(np.cumsum(ind_df["fptarea"])) if len(ind_df) else [0.0]
    com_fptarea_cs = list(np.cumsum(com_df["fptarea"])) if len(com_df) else [0.0]

    # Total areas available for commercial and industrial buildings in all zones
    At_c = float(landuse_ic_df["AreaAvailableForCom"].sum())
    At_i = float(landuse_ic_df["AreaAvailableForInd"].sum())
    licidx = landuse_ic_df.index

    # --- Industrial: only if there is available area ---
    if At_i > 0 and nInd_tba > 0:
        landuse_ic_df.loc[licidx, "No_of_ind_buildings"] = (landuse_ic_df["AreaAvailableForInd"] / At_i) * nInd_tba
    else:
        landuse_ic_df.loc[licidx, "No_of_ind_buildings"] = 0

    landuse_ic_df["No_of_ind_buildings"] = landuse_ic_df["No_of_ind_buildings"].fillna(0)

    # --- Commercial: only if there is available area ---
    if At_c > 0 and nCom_tba > 0:
        unassigned_com_area = com_fptarea_cs[-1] - nCom_asgn_area

        if unassigned_com_area > At_c:
            # Need to truncate excess commercial buildings
            # log_warning(
            #     "Required commercial buildings do not fit into available land area. "
            #     "Excess commercial buildings have been removed."
            # )
                
            com_df_unassignedArea = np.cumsum(com_df.loc[range(nCom_asgn, len(com_df)), "fptarea"])
            com_df_UAmask = com_df_unassignedArea < At_c
            nCom_tba = int(sum(com_df_UAmask))

        landuse_ic_df.loc[licidx, "No_of_com_buildings"] = (landuse_ic_df["AreaAvailableForCom"] / At_c) * nCom_tba
    else:
        landuse_ic_df.loc[licidx, "No_of_com_buildings"] = 0

    landuse_ic_df["No_of_com_buildings"] = landuse_ic_df["No_of_com_buildings"].fillna(0)

    
    #Assign number of commercial buildings to commercial zones____

    


    

    
    
    # Begin assigning buildings to zones 
    # Assign zoneid to industrial buildings (if any) in industrial areas
    limit_zoneID_ic_i = int(landuse_ic_df['No_of_ind_buildings'].sum())
    zoneID_ic_i = dist2vector(list(landuse_ic_df['zoneid']),\
                  list(landuse_ic_df['No_of_ind_buildings']),\
                  limit_zoneID_ic_i,'shuffle')
    ind_df.loc[range(nInd_asgn,nInd_asgn+limit_zoneID_ic_i),'zoneid']=list(map(int,zoneID_ic_i))
    ind_df = ind_df[ind_df['zoneid'].notna()] #Remove unassigned buildings
     
    # Assign zoneid to commercial buildings (if any) in commercial areas
    limit_zoneID_ic_c = int(landuse_ic_df['No_of_com_buildings'].sum())
    zoneID_ic_c = dist2vector(list(landuse_ic_df['zoneid']),\
                  list(landuse_ic_df['No_of_com_buildings']),\
                  limit_zoneID_ic_c,'shuffle')
    com_df.loc[range(nCom_asgn,nCom_asgn+limit_zoneID_ic_c),'zoneid']=list(map(int,zoneID_ic_c))
    com_df = com_df[com_df['zoneid'].notna()] #Remove unassigned buildings
    
    
    #%% Find populations in each zones and assign it back to landuse layer
    for i in landuse.index:
        zidmask = resbld_df['zoneid'] == landuse.loc[i,'zoneid']
        if sum(zidmask) == 0: # if no population has been added to the zone
            landuse.loc[i,'populationAdded'] = 0  
            continue
        else: # if new population has been added to the zone
            zone_nInd = resbld_df['residents'][zidmask]
            landuse.loc[i,'populationAdded'] = int(zone_nInd.sum())
    # population=Existing population, populationAdded=Projected future population
    # populationFinal = existing + future projected population
    landuse['populationFinal'] = landuse['population']+landuse['populationAdded']
    landuse['populationFinal'] = landuse['populationFinal'].astype('int')
    
    #%% Assign zoneIds for schools and hospitals
    # Assign schools and hospitals to zones starting from the highest 
    # population until the number of schools and hospitals are reached
    landuse_sorted = landuse.sort_values(by=['populationFinal'],\
                                                     ascending=False).copy()
    landuse_sorted.reset_index(inplace=True, drop=True)
    #Remove zones without population
    no_popl_zones = landuse_sorted['populationFinal']==0
    landuse_sorted =landuse_sorted.drop(index=landuse_sorted.index[no_popl_zones])
    
    sch_df = schhsp_df[schhsp_df['occbld']=='Edu'].copy() #Educational institutions
    hsp_df = schhsp_df[schhsp_df['occbld']=='Hea'].copy() #Health institutions
    
    sch_df.reset_index(drop=True,inplace=True)
    hsp_df.reset_index(drop=True,inplace=True)
    
    # For schools (Edu)__________
    
    # METHOD 1: If land use zones have already been defined, populate schools only 
    #   in the land use polygons designated as 'school'
    if school_distr_method == 'landuse':
        schpoly_zoneid, schpoly_area = [],[]
        sch_count =0
        for idx in landuse_shp.index: # Identify school polygons first
            lut_sch = landuse_shp.luf[idx].lower()
            sch_df_idx = sch_df.index
            if any(kw in lut_sch for kw in ['school', 'education', 'college', 'public', 'units']):
                #Extract area of school polygon (already converted to m^2)
                schpoly_area.append(landuse_shp.area[idx])
                schpoly_zoneid.append(landuse_shp.zoneid[idx])
                sch_count+=1
                #print(landuse_shp.zoneid[idx], landuse_shp.luf[idx],landuse_shp.area[idx])
            
        if sch_count >0: # if school land use zone exists        
            schpoly_area = np.array(schpoly_area) 
            schpoly_zoneid  = np.array(schpoly_zoneid)  
            #Distribute buildings in proportion to polygon area
            no_of_zoneid4school = len(sch_df)*schpoly_area/sum(schpoly_area)
            no_of_zoneid4school = no_of_zoneid4school.astype(int)
            no_of_zoneid4school_lv =  len(sch_df)-sum(no_of_zoneid4school[0:-1])
            if len(no_of_zoneid4school) > 0:
                no_of_zoneid4school[-1] = no_of_zoneid4school_lv
            
            zid4sch = dist2vector(schpoly_zoneid, no_of_zoneid4school, sum(no_of_zoneid4school),'shuffle')
            sch_df.loc[:, 'zoneid'] = np.array(zid4sch,dtype=int)
            
            #If building areas exceed available area in the polygon, the footprints
            # of excess buildings will not be produced 
        else: 
            log_warning('Unable to find school polygons in the land use files. If school '\
                  'land use polygons exist, make sure that the land use name (luf) '\
                  'contains the words \'school\' or \'education\' or \'college\'\n')
            log_info('The program will now use population based method.')
            school_distr_method = 'population'
    
    # METHOD 2: If land use polygon for schools is not defined, assign zoneIDs for
    #   schools by distributing schools in proportion to the population in
    #   each land use polygon. Thus, densly populated areas will have more schools.
    
    if school_distr_method == 'population':
        sch_ratios = landuse_sorted['populationFinal']/landuse_sorted['populationFinal'].sum()
        sch_dist = round(sch_ratios * len(sch_df))
        if sum(sch_dist) != len(sch_df):
            leap = len(sch_df) - sum(sch_dist)
            sch_dist[0] += leap
        sch_dist_updated = sch_dist.loc[(sch_dist!=0)]
        final_sch_list = []
        for i in range(len(sch_dist_updated)):
            temp_a = list(repeat(landuse_sorted['zoneid'].iloc[i], int(sch_dist_updated.iloc[i])))
            final_sch_list.extend(temp_a)
        sch_df.loc[:, 'zoneid'] = final_sch_list    
        
        sch_df.loc[:, 'zoneid'] = final_sch_list
    
    # For hospitals (Hea)__________
    
    # METHOD 1: If land use zones have already been defined, populate hospitals only 
    #   in the land use polygons designated as 'hospital'
    if hospital_distr_method == 'landuse':
        hsppoly_zoneid, hsppoly_area = [],[]
        hsp_count = 0
        for idx in landuse_shp.index: # Identify hospital polygons first
            lut_hsp = landuse_shp.luf[idx].lower()
            hsp_df_idx = hsp_df.index
            # Support both standard keywords and Urban Atlas "public... units" class
            if any(kw in lut_hsp for kw in ['hospital', 'health', 'clinic', 'public', 'units']):
                #Extract area of hospital polygon (regardless of units)
                hsppoly_area.append(landuse_shp.area[idx])
                hsppoly_zoneid.append(landuse_shp.zoneid[idx])
                hsp_count+=1
            
        if hsp_count >0: # if hospital land use zone exists        
            hsppoly_area = np.array(hsppoly_area) 
            hsppoly_zoneid  = np.array(hsppoly_zoneid)  
            #Distribute buildings in proportion to polygon area
            no_of_zoneid4hsp = len(hsp_df)*hsppoly_area/sum(hsppoly_area)
            no_of_zoneid4hsp = no_of_zoneid4hsp.astype(int)
            no_of_zoneid4hsp_lv =  len(hsp_df)-sum(no_of_zoneid4hsp[0:-1])
            if len(no_of_zoneid4hsp) > 0:
                no_of_zoneid4hsp[-1] = no_of_zoneid4hsp_lv
            
            zid4hsp = dist2vector(hsppoly_zoneid, no_of_zoneid4hsp, sum(no_of_zoneid4hsp),'shuffle')
            hsp_df.loc[:, 'zoneid'] = np.array(zid4hsp,dtype=int)
            
            #If building areas exceed available area in the polygon, the footprints
            # of excess buildings will not be produced 
        else: 
            log_warning('Unable to find hospital polygons in the land use files. If hospital land use polygons exist, make sure that the land use name (luf) contains keywords like hospital, health, public, etc.\n')
            log_info('The program will now use population based method.')
            hospital_distr_method = 'population'
    # METHOD 2: If land use polygon for hospitals is not defined, assign zoneIDs for
    #  hospitals by distributing hospitals in proportion to the population
    #  in each land use polygon. Thus, densly populated areas will have more hospitals.
    if hospital_distr_method == 'population':
        hsp_ratios = landuse_sorted['populationFinal']/landuse_sorted['populationFinal'].sum()
        hsp_dist = round(hsp_ratios * len(hsp_df))
        if sum(hsp_dist) != len(hsp_df):
            leap = len(hsp_df) - sum(hsp_dist)
            hsp_dist[0] += leap
        hsp_dist_updated = hsp_dist.loc[(hsp_dist!=0)]
        final_hsp_list = []
        for i in range(len(hsp_dist_updated)):
            temp_b = list(repeat(landuse_sorted['zoneid'].iloc[i], int(hsp_dist_updated.iloc[i])))
            final_hsp_list.extend(temp_b)
        hsp_df.loc[:, 'zoneid'] = final_hsp_list
    
        hsp_df.loc[:, 'zoneid'] = final_hsp_list
    #%% Concatenate the residential, industrial/commercial and special facilities
    # dataframes to obtain the complete building dataframe
    building_df=pd.concat([resbld_df,ind_df,com_df,sch_df,\
                            hsp_df]).reset_index(drop=True)
    #building_df=pd.concat([resbld_df,sch_df, hsp_df]).reset_index(drop=True)
    building_df['nstoreys'] = building_df['nstoreys'].astype(int)
    
    #Assign exposure string
    building_df['expStr'] = building_df['lrstype'].astype(str)+'+'+\
                            building_df['codelevel'].astype(str)+'+'+\
                            building_df['nstoreys'].astype(str)+'s'+'+'+\
                            building_df['occbld'].astype(str)
    # Assign building ids
    # lenbdf = len(building_df)
    # building_df.loc[range(0,lenbdf),'bldID'] = list(range(1,lenbdf+1))
    bldid_LL = max(resbld_df['bldID'])+1
    bldid_UL = bldid_LL + (len(building_df)-len(resbld_df))
    building_df.loc[range(len(resbld_df),len(building_df)),'bldID'] =\
                        list(range(bldid_LL,bldid_UL))
    building_df['bldID'] = building_df['bldID'].astype('int')
    
    #%% Step 21 Employment status of the individuals
    # Assumption 9: Only 20-65 years old individuals can work
    # Extract Tables 12 and 13
    
    # Table 12: Labour Force Participation Rate by Gender
    # Supports dynamic number of genders
    if len(tables['t12'][0]) > 0:
        t12_row = np.array(tables['t12'][0][0], dtype=float)
    else:
        t12_row = np.array([0.5, 0.5]) # Fallback
        
    t12_probs = []
    for i in range(len(gender_value)):
        if i < len(t12_row):
            t12_probs.append(t12_row[i])
        else:
            # Fallback: unnecessary specific probability not found, use last available
            if len(t12_probs) > 0:
                t12_probs.append(t12_probs[-1])
            else:
                t12_probs.append(0.5)

    # Table 13: Employment Rate by Gender and Education
    # Supports dynamic number of genders
    t13_rows = tables['t13'][0]
    t13_distributions = []
    
    for i in range(len(gender_value)):
        if i < len(t13_rows):
            t13_distributions.append(np.array(t13_rows[i], dtype=float))
        else:
            # Fallback
            if len(t13_distributions) > 0:
                t13_distributions.append(t13_distributions[-1])
            else:
                # Default probability if completely missing
                t13_distributions.append(np.ones(len(education_value)) * 0.5)

    # Identify individuals who can work and assign Labour Force status
    
    # Determine Age Limits for Labour Force from Table 4a
    # Default values (Index of age bins): 5 to 9 (inclusive)
    min_age_idx = 5
    max_age_idx = 9
    
    if len(tables['t4a']) > 0 and len(tables['t4a'][0]) > 0:
        try:
             # Assuming single row with [min_age, max_age]
             t4a_row = np.array(tables['t4a'][0][0], dtype=float)
             if len(t4a_row) >= 2:
                 min_age_idx = int(t4a_row[0])
                 max_age_idx = int(t4a_row[1])
        except Exception as e:
            log_warning(f"Failed to parse Table 4a for Labour Force dynamic age limits. Using defaults (5-9). Error: {e}")
            
    # Loop through each gender
    for i in range(len(gender_value)):
        g_val = gender_value[i]
        lf_prob = t12_probs[i]
        
        # Identify potential workers for this gender
        # Age assumption: Uses dynamic indices from Table 4a (default 5-9)
        # Original code used: (individual_df['age']>=5) & (individual_df['age']<=9)
        
        working_age_mask = (individual_df['gender'] == g_val) & \
                           (individual_df['age'] >= min_age_idx) & (individual_df['age'] <= max_age_idx)
                           
        potential_workers = individual_df.index[working_age_mask]
        
        if len(potential_workers) > 0:
            # Assign Labour Force
            # labourForce = 1 indicates that an individual is a part of labour force
            num_in_labour_force = int(lf_prob * len(potential_workers))
            labourforce_idx = sample(list(potential_workers), num_in_labour_force)
            individual_df.loc[labourforce_idx, 'labourForce'] = 1
            
    # Assign Employment Status based on Education and Gender
    # Loop through each gender
    for i in range(len(gender_value)):
        g_val = gender_value[i]
        epd_array = t13_distributions[i] # Employment prob distribution for this gender
        
        count = 0
        for epd in epd_array: # EPD for various educational attainment status
            # Individuals in labour force that belong to current EPD AND Current Gender
            eamask = (individual_df['eduAttStat'] == education_value[count]) & \
                     (individual_df['labourForce'] == 1) & \
                     (individual_df['gender'] == g_val)
                     
            nInd_in_epd = sum(eamask)
            if nInd_in_epd == 0:
                count += 1
                continue
            
            nInd_employed = int(epd * nInd_in_epd)
            if nInd_employed > 0:
                ind_ea_labourforce = list(individual_df.index[eamask])
                ind_employed_idx = sample(ind_ea_labourforce, nInd_employed)
                individual_df.loc[ind_employed_idx, 'employed'] = 1
            
            count += 1
            
    #%% Step 22 Assign IndividualFacID
    # bld_ID of the building that the individual regularly visits 
    # (can be workplace, school, etc.)
    # Assumption 13: Each individual is working within the total study area extent.
    # Assumption 17: Each individual (within schooling age limits) goes to 
    #                school within the total study area extent.
    
    # indivFacID_1 denotes bldID of the schools
    # students (schoolEnrollment=1) go to, whereas, indivFacID_2 denotes bldID of
    # com, ind and rescom buildings where working people go to (workplace bldID).
    
    # Assign working places to employed people in indivFacID_2_________________
    # Working places are defined as occupancy types 'Ind','Com' and 'ResCom'
    
    workplacemask=(building_df['occbld']=='Ind') | (building_df['occbld']=='Com')\
                    | (building_df['occbld'] == 'ResCom')
    workplaceidx = building_df.index[workplacemask]
    workplace_bldID = building_df['bldID'][workplaceidx].tolist()
    
    employedmask = individual_df['employed'] ==1
    employedidx = individual_df.index[employedmask]
    if len(employedidx)>len(workplaceidx):
        repetition = ceil(len(employedidx)/len(workplaceidx))
        workplace_sample_temp = list(repeat(workplace_bldID,repetition))
        workplace_sample = list(chain(*workplace_sample_temp))
    else:
        workplace_sample = workplace_bldID
    random.shuffle(workplace_sample)
    
    individual_df.loc[employedidx,'indivFacID_2'] = \
                                   workplace_sample[0:sum(employedmask)]
    
    individual_df.loc[employedidx,'indivfacid'] = \
                                   workplace_sample[0:sum(employedmask)]                               
    
    # Assign school bldIDs to enrolled students in indivFacID_1________________
    schoolmask = building_df['occbld']=='Edu'            
    schoolidx = building_df.index[schoolmask]
    school_bldID = building_df['bldID'][schoolidx].tolist()
    
    studentmask = individual_df['schoolEnrollment'] ==1
    studentidx = individual_df.index[studentmask]
    if len(studentidx)>len(schoolidx):
        repetition = ceil(len(studentidx)/len(schoolidx))
        school_sample_temp = list(repeat(school_bldID,repetition))
        school_sample = list(chain(*school_sample_temp))
    else:
        school_sample = school_bldID
    random.shuffle(school_sample)
    
    individual_df.loc[studentidx,'indivFacID_1'] = \
                                   school_sample[0:sum(studentmask)]  
    individual_df.loc[studentidx,'indivfacid'] = \
                                   school_sample[0:sum(studentmask)]                               
    
    # Replace missing values with -1 instead of NaN
    individual_df['indivFacID_1'] = individual_df['indivFacID_1'].fillna(-1)
    individual_df['indivFacID_2'] = individual_df['indivFacID_2'].fillna(-1) 
    individual_df['indivfacid'] = individual_df['indivfacid'].fillna(-1)  
    
    #%% Step 23 Assign community facility ID (CommFacID) to household layer
    # CommFacID denotes the bldID of the hospital the households usually go to.
    
    # In this case, randomly assign bldID of hospitals to the households, but in 
    # next version, households must be assigned hospitals closest to their location
    hospitalmask = building_df['occbld']=='Hea'
    hospitalidx = building_df.index[hospitalmask]
    hospital_bldID = building_df['bldID'][hospitalidx].tolist()
    repetition = ceil(len(household_df)/len(hospitalidx))
    hospital_sample_temp = list(repeat(hospital_bldID,repetition))
    hospital_sample = list(chain(*hospital_sample_temp))
    random.shuffle(hospital_sample)
    
    household_df.loc[household_df.index,'CommFacID'] =\
                                    hospital_sample[0:len(household_df)]
    
    #%% Step 24 Assign repValue
    # Assumption 12: Unit price for replacement wrt occupation type and 
    # special facility status of the building
    
    # Assign unit price
    for occtype in Unit_price:
        occmask = building_df['occbld'] == occtype
        occidx = building_df.index[occmask]
        building_df.loc[occidx, 'unit_price'] = Unit_price[occtype]
        
    building_df['repValue'] = building_df['fptarea'] *\
                             building_df['nstoreys']* building_df['unit_price']
    
    
    #%% Remove unnecessary columns and save the results 
    # building_df = building_df.drop(columns=\
    #          ['lut_number','lrstype','codelevel','nstoreys','occbld','unit_price'])
    building_df = building_df.drop(columns=['lut_number'])
    household_df = household_df.drop(columns=\
             ['income_numb','zoneType','zoneid','approxFootprint'])
    individual_df = individual_df.drop(columns=\
                        ['schoolEnrollment','labourForce','employed'])
        
    # Rename indices to convert all header names to lowercase
    building_df.rename(columns={'zoneid':'zoneid','bldID':'bldid','expStr':'expstr',\
       'specialFac':'specialfac','repValue':'repvalue','nHouse':'nhouse'},\
                                                               inplace=True)
    household_df.rename(columns={'bldID':'bldid','hhID':'hhid','nIND':'nind',\
                                 'CommFacID':'commfacid'}, inplace=True)
    individual_df.rename(columns={'hhID':'hhid','indivID':'individ',\
       'eduAttStat':'eduattstat','indivFacID_1':'indivfacid_1',\
       'indivFacID_2':'indivfacid_2'}, inplace=True)

    
    # #%% Generate building centroid coordinates
    # final_list = []
    # skipped_buildings_count = 0
    # landuse_layer = landuse_shp
    
    # if (school_distr_method == 'landuse' and hospital_distr_method == 'landuse'):
    
        # building_layer = building_df    
        # histo = building_df.groupby(['zoneid'])['zoneid'].count()
        # max_val = building_df.groupby(['zoneid'])['fptarea'].max()
    
        # for i in range(len(histo)):
            # df = landuse_layer[landuse_layer['zoneid'] == histo.index[i]].copy()
            # bui_indx = building_layer['zoneid'] == histo.index[i]
            # bui_attr = building_layer.loc[bui_indx].copy()
            
            # rot_a = random.randint(10, 40)
            # rot_a_rad = rot_a*math.pi/180
            
            # separation_val = math.sqrt(max_val.values[i])/abs(math.cos(rot_a_rad))
            # separation_val = round(separation_val, 2)
                
            # boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
            # boundary_approach = round(boundary_approach, 2)
            
            # df2 = df.buffer(-boundary_approach)    
            # df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
            # df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
            
            # #Continue the loop if buffered dataframe df2 is empty -PR
            # if df2.is_empty[df2.index[0]]:
                # #print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                # skipped_buildings_count +=\
                    # len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                # continue
            
            # xmin, ymin, xmax, ymax = df2.total_bounds    
            # xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
            # ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
            
            # pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
            # points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
            # grid = gpd.GeoSeries(points, crs=df.crs)
            # grid.name = 'geometry'
            
            # gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
            
            # def buff(row):
                # return row.geometry.buffer(row.buff_val, cap_style = 3)
            
            # if len(gridinside) >= histo.values[i]:
                # gridinside = gridinside.sample(min(len(gridinside), histo.values[i]))
                # gridinside['xcoord'] = gridinside.geometry.x
                # gridinside['ycoord'] = gridinside.geometry.y
                
                # buffer_val = np.sqrt(list(bui_attr.fptarea))/2
                # buffered = gridinside.copy()
                # buffered['buff_val'] = buffer_val[0:len(gridinside)]
                
                # if buffered.shape[0]==0: 
                    # #print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                    # skipped_buildings_count +=\
                        # len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                    # continue
                
                # buffered['geometry'] = buffered.apply(buff, axis=1)
                # polyinside = buffered.rotate(rot_a, origin='centroid')
                
                # polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
                # polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
                # polyinside2['fid'] = list(range(1,len(polyinside2)+1))
                
                # bui_attr['fid'] = list(range(1,len(bui_attr)+1))
                # bui_joined = polyinside2.merge(bui_attr, on='fid')
                # bui_joined = bui_joined.drop(columns=['fid'])
                
                # bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
                # bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))
                
            # elif len(gridinside) < histo.values[i]:            
                # separation_val = math.sqrt(max_val.values[i])
                # separation_val = round(separation_val, 2)
                # boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
                # boundary_approach = round(boundary_approach, 2)
                
                # df2 = df.buffer(-boundary_approach, 200)
                # df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
                # df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
                
                # xmin, ymin, xmax, ymax = df2.total_bounds    
                # xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
                # ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
                
                # pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
                # points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
                # grid = gpd.GeoSeries(points, crs=df.crs)
                # grid.name = 'geometry'
                
                # gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
                
                # gridinside = gridinside.sample(min(len(gridinside), histo.values[i]))
                # gridinside['xcoord'] = gridinside.geometry.x
                # gridinside['ycoord'] = gridinside.geometry.y
                
                # buffer_val = np.sqrt(list(bui_attr.fptarea))/2
                # buffered = gridinside.copy()
                # buffered['buff_val'] = buffer_val[0:len(gridinside)]
                
                # if buffered.shape[0]==0: 
                    # #print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                    # skipped_buildings_count +=\
                        # len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                    # continue
                
                # buffered['geometry'] = buffered.apply(buff, axis=1)
                # polyinside = buffered.rotate(0, origin='centroid')
                
                # polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
                # polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
                # polyinside2['fid'] = list(range(1,len(polyinside2)+1))
                
                # bui_attr['fid'] = list(range(1,len(bui_attr)+1))
                # bui_joined = polyinside2.merge(bui_attr, on='fid')
                # bui_joined = bui_joined.drop(columns=['fid'])
                
                # bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
                # bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))
        
            # final_list.append(bui_joined)
        
        # final = pd.concat(final_list)
        
    # else:
    
        # gen_list = np.unique(building_df['occbld'])
        # #gen_list = np.flip(gen_list)
        # for occ_i in gen_list:
            # histo = building_df.groupby(['zoneid','occbld'])['zoneid'].count().reset_index(name="count")
            # histo = histo.loc[(histo['occbld'] == occ_i)]
            # building_group = building_df.loc[(building_df['occbld'] == occ_i)]
            # max_val = building_group.groupby(['zoneid'])['fptarea'].max().reset_index(name="val")
            # max_val = pd.Series(max_val['val'].values)
            # building_layer = building_group
            # chunk_bui = []
            
            # for i in range(len(histo)):
                # df = landuse_layer[landuse_layer['zoneid'] == histo.iloc[i]['zoneid']].copy()
                # bui_indx = building_layer['zoneid'] == histo.iloc[i]['zoneid']
                # bui_attr = building_layer.loc[bui_indx].copy()
                
                # rot_a = random.randint(10, 40)
                # rot_a_rad = rot_a*math.pi/180
                
                # separation_val = math.sqrt(max_val.values[i])/abs(math.cos(rot_a_rad))
                # separation_val = round(separation_val, 2)
                    
                # boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
                # boundary_approach = round(boundary_approach, 2)
                
                # df2 = df.buffer(-boundary_approach)    
                # df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
                # df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
                
                # #Continue the loop if buffered dataframe df2 is empty -PR
                # if df2.is_empty[df2.index[0]]:
                    # #print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                    # skipped_buildings_count +=\
                        # len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                    # continue
                
                # xmin, ymin, xmax, ymax = df2.total_bounds    
                # xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
                # ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
                
                # pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
                # points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
                # grid = gpd.GeoSeries(points, crs=df.crs)
                # grid.name = 'geometry'
                
                # gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
                
                # def buff(row):
                    # return row.geometry.buffer(row.buff_val, cap_style = 3)
                
                # if len(gridinside) >= histo.iloc[i]['count']:
                    # gridinside = gridinside.sample(min(len(gridinside), histo.iloc[i]['count']))
                    # gridinside['xcoord'] = gridinside.geometry.x
                    # gridinside['ycoord'] = gridinside.geometry.y
                    
                    # buffer_val = np.sqrt(list(bui_attr.fptarea))/2
                    # buffered = gridinside.copy()
                    # buffered['buff_val'] = buffer_val[0:len(gridinside)]
                    
                    # if buffered.shape[0]==0: 
                        # #print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                        # skipped_buildings_count +=\
                            # len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                        # continue
                    
                    # buffered['geometry'] = buffered.apply(buff, axis=1)
                    # polyinside = buffered.rotate(rot_a, origin='centroid')
                    
                    # polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
                    # polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
                    # polyinside2['fid'] = list(range(1,len(polyinside2)+1))
                    
                    # bui_attr['fid'] = list(range(1,len(bui_attr)+1))
                    # bui_joined = polyinside2.merge(bui_attr, on='fid')
                    # bui_joined = bui_joined.drop(columns=['fid'])
                    
                    # bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
                    # bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))
                    
                # elif len(gridinside) < histo.iloc[i]['count']:            
                    # separation_val = math.sqrt(max_val.values[i])
                    # separation_val = round(separation_val, 2)
                    # boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
                    # boundary_approach = round(boundary_approach, 2)
                    
                    # df2 = df.buffer(-boundary_approach, 200)
                    # df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
                    # df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
                    
                    # xmin, ymin, xmax, ymax = df2.total_bounds    
                    # xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
                    # ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
                    
                    # pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
                    # points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
                    # grid = gpd.GeoSeries(points, crs=df.crs)
                    # grid.name = 'geometry'
                    
                    # gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
                    
                    # gridinside = gridinside.sample(min(len(gridinside), histo.iloc[i]['count']))
                    # gridinside['xcoord'] = gridinside.geometry.x
                    # gridinside['ycoord'] = gridinside.geometry.y
                    
                    # buffer_val = np.sqrt(list(bui_attr.fptarea))/2
                    # buffered = gridinside.copy()
                    # buffered['buff_val'] = buffer_val[0:len(gridinside)]
                    
                    # if buffered.shape[0]==0: 
                        # #print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                        # skipped_buildings_count +=\
                            # len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                        # continue
                    
                    # buffered['geometry'] = buffered.apply(buff, axis=1)
                    # polyinside = buffered.rotate(0, origin='centroid')
                    
                    # polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
                    # polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
                    # polyinside2['fid'] = list(range(1,len(polyinside2)+1))
                    
                    # bui_attr['fid'] = list(range(1,len(bui_attr)+1))
                    # bui_joined = polyinside2.merge(bui_attr, on='fid')
                    # bui_joined = bui_joined.drop(columns=['fid'])
                    
                    # bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
                    # bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))
                
                # chunk_bui.append(bui_joined)
                # final_list.append(bui_joined)
             
            # chunk_bui = pd.concat(chunk_bui)
            # final = pd.concat(final_list)
            
            # # print("Occupation Type: ", occ_i)
            # # print("Generated Buildings: ", len(chunk_bui))
            # # print("Number of Skipped Buildings: ", len(building_group)-len(chunk_bui), "\n")
        
            # # chunk_bui = chunk_bui.dissolve(aggfunc='first')
            # # landuse_layer = landuse_layer.overlay(chunk_bui, how='difference')
            
    final = generate_city_layout(landuse_shp, building_df, road_network=constraint_gdf)
    
    # Validation: Check for unplaced buildings (Post-Generation)
    if not final.empty:
        stats_requested = building_df['occbld'].value_counts()
        stats_generated = final['occbld'].value_counts()
        
        for b_type in ['Ind', 'Com', 'Edu', 'Hea']:
             req = stats_requested.get(b_type, 0)
             gen = stats_generated.get(b_type, 0)
             if gen < req:
                 diff = int(req - gen)
                 type_name = "Industrial" if b_type=='Ind' else "Commercial" if b_type=='Com' else "School" if b_type=='Edu' else "Hospital"
                 log_warning(f"{diff} {type_name} buildings could not be generated geometrically due to lack of space.")
    
    final['zoneid'] = final['zoneid'].astype('int64')
    final['specialfac'] = final['specialfac'].astype('int64')    
    final['nhouse'] = final['nhouse'].astype('int64')
    final['residents'] = final['residents'].astype('int64')
    
    # Convert back to Gegraphical Coordinate System if initial CRS is GCS
    if 'initial_crs' in locals():
        final = final.to_crs(initial_crs)

    final_tb = copy.deepcopy(final)
    final_tb = final_tb.drop(columns=['geometry'])
    
    # final hazırlandıktan sonra
    final_tb = final.drop(columns=["geometry"]).copy()
    placed_bldids = set(final_tb["bldid"].astype(int))

    # 1) Binaya hiç atanamayan (NaN) veya footprint’te olmayan haneleri sil
    #hh_ok = household_df["bldid"].notna() & household_df["bldid"].astype(int).isin(placed_bldids)

    # final'de yerleşmiş bldid'leri güvenli topla
    placed_bldids = pd.to_numeric(final_tb["bldid"], errors="coerce")
    placed_bldids = set(placed_bldids[np.isfinite(placed_bldids)].astype("Int64").dropna().astype(int))

    # household bldid'yi güvenli işle
    bld = pd.to_numeric(household_df["bldid"], errors="coerce")
    finite = np.isfinite(bld)  # NaN/inf -> False

    # Nullable integer (Int64) ile sadece geçerli olanları dönüştür
    bld_int = pd.Series(pd.NA, index=household_df.index, dtype="Int64")
    bld_int.loc[finite] = bld.loc[finite].astype("Int64")

    hh_ok = bld_int.isin(placed_bldids)
    household_df = household_df.loc[hh_ok].copy()

    valid_hhids = set(pd.to_numeric(household_df["hhid"], errors="coerce").dropna().astype(int))
    individual_df = individual_df.loc[pd.to_numeric(individual_df["hhid"], errors="coerce").isin(valid_hhids)].copy()

    household_df = household_df.loc[hh_ok].copy()

    # 2) Geriye kalan hanelere bağlı olmayan bireyleri sil
    valid_hhids = set(household_df["hhid"].astype(int))
    individual_df = individual_df.loc[individual_df["hhid"].astype(int).isin(valid_hhids)].copy()

    #%% Remove fields corresponding to unassigned buildings from all layers
    # The footprint generation part of this program may not be able to assign 
    # building footprint in some cases such as narrow strips or highly irregular
    # but small land areas. In this case, households and individuals 
    # corresponding to buildings without footprint coordinates must also be deleted.
    
    #Original dataframe which contains all generated buildings
    unique_building_df =  set(building_df['bldid'])
    #Building dataframe that contains only the building with footprints 
    unique_final = set(final_tb['bldid'])
    # Calculate list of buildings that do not exist in the dataframe with building
    # footprints 
    missing_buildings = np.array(list(set(unique_building_df).difference(unique_final)))
    
    # Extract the list of households corresponding to missing buildings
    hh_missing_idx_list = []
    for mb in missing_buildings:
        hh_missing_mask = household_df['bldid'] == mb
        hh_missing_idx_list.append(household_df.index[hh_missing_mask].tolist())
     
    # Flatten the list of lists to obtain indices and hhid of missing households
    hh_missing_idx =  [single_value for sublist in hh_missing_idx_list \
                                    for single_value in sublist]    
    hh_missing = household_df.loc[hh_missing_idx,'hhid'].tolist() 
    
    # Extract the list of individuals corresponding to missing buildings
    ind_missing_idx_list =[]
    for mh in hh_missing:
        ind_missing_mask =individual_df['hhid'] == mh
        ind_missing_idx_list.append(individual_df.index[ind_missing_mask].tolist())
    
    ind_missing_idx = [single_value for sublist in ind_missing_idx_list\
                                    for single_value in sublist]
    
    # Delete households corresponding to missing buildings
    household_df.drop(labels = hh_missing_idx, axis=0,inplace=True)    
    
    # Delete individuals corresponding to missing buildings
    individual_df.drop(labels = ind_missing_idx, axis=0, inplace=True)

    hh_stats = (
        household_df.groupby("bldid")
        .agg(nhouse=("hhid", "count"), residents=("nind", "sum"))
        .reset_index()
    )

    # final içinde aynı kolonlar varsa çakışmayı önle
    final = final.drop(columns=["nhouse", "residents"], errors="ignore")

    final = final.merge(hh_stats, on="bldid", how="left")
    final["nhouse"] = final["nhouse"].fillna(0).astype("int64")
    final["residents"] = final["residents"].fillna(0).astype("int64")

    # ---------------------------------------------------------------------------------
    #%% Step 26: Correct Invalid Hospital IDs (CommFacID) for Households
    # ---------------------------------------------------------------------------------
    # This step corrects hospital IDs that were assigned to households in 'household_df'
    # but do not exist in the 'final' table because their geometry could not be generated.
    # print("\nStep 26: Checking hospital assignments in the household layer...")

    # Step 1: Get the IDs of valid hospitals that were successfully generated.
    # Buildings with 'occbld' == 'Hea' (Health) are hospitals.
    valid_hospital_ids = []
    if 'occbld' in final.columns:
        valid_hospital_ids = final[final['occbld'] == 'Hea']['bldid'].unique().tolist()

    # Step 2: If no valid hospitals were generated, print a warning and exit this step.
    if not valid_hospital_ids:
        household_df['commfacid'] = -1
        log_warning("No hospital buildings were generated geometrically. The 'commfacid' column has been set to -1 to reflect this. Please revise your land use and/or tabular inputs for more precise results!")
        # log_msg(sc_warnings, "warning", "Hospital ID Correction", "No hospital buildings were generated geometrically. The 'commfacid' column has been set to -1 to reflect this. Please revise your land use and/or tabular inputs for more precise results!")
        
    else:
        # Step 3: Find households with an invalid 'commfacid' (i.e., not in the 'valid_hospital_ids' list).
        households_to_reassign_mask = ~household_df['commfacid'].isin(valid_hospital_ids)
        num_to_reassign = households_to_reassign_mask.sum()

        # print(f"Number of valid hospitals generated: {len(valid_hospital_ids)}")
        # print(f"Number of households assigned to an invalid hospital: {num_to_reassign}")

        # Step 4: If there are households to correct, perform the reassignment.
        if num_to_reassign > 0:
            # print("Reassigning invalid hospital IDs evenly among the existing hospitals...")

            # Repeat the list of valid hospital IDs to create a new assignment list
            # long enough for all households that need reassignment. This ensures an even distribution.
            num_valid_hospitals = len(valid_hospital_ids)
            
            # Calculate how many times the list needs to be repeated.
            repetitions = (num_to_reassign // num_valid_hospitals) + 1
            new_assignments_long = valid_hospital_ids * repetitions
            
            # Trim the list to the exact required length and shuffle it.
            new_assignments = new_assignments_long[:num_to_reassign]
            random.shuffle(new_assignments)

            # Update the 'commfacid' column in the original household_df.
            household_df.loc[households_to_reassign_mask, 'commfacid'] = new_assignments
            log_info(f"Successfully updated the hospital assignment for {num_to_reassign} households.")
        else:
            log_info("All hospital assignments are valid. No correction was needed.")

    # ---------------------------------------------------------------------------------
    #%% Step 27: Correct Invalid School IDs (indivfacid_1) for Individuals
    # ---------------------------------------------------------------------------------
    # This step corrects school IDs that were assigned to individuals in 'individual_df'
    # but do not exist in the 'final' table because their geometry could not be generated.
    # print("\nStep 27: Checking school assignments in the individual layer...")

    # Step 1: Get the IDs of valid schools that were successfully generated.
    # Buildings with 'occbld' == 'Edu' (Education) are schools.
    valid_school_ids = []
    if 'occbld' in final.columns:
        valid_school_ids = final[final['occbld'] == 'Edu']['bldid'].unique().tolist()

    # Step 2: If no valid schools were generated, print a warning and exit this step.
    if not valid_school_ids:
        individual_df['indivfacid_1'] = -1
        log_warning("No school buildings were generated geometrically. The 'indivfacid_1' column has been set to -1 to reflect this. Please revise your land use and/or tabular inputs for more precise results!")
        # log_msg(sc_warnings, "warning", "School ID Correction", "No school buildings were generated geometrically. The 'indivfacid_1' column has been set to -1 to reflect this. Please revise your land use and/or tabular inputs for more precise results!")
        
    else:
        # Step 3: Find individuals assigned to an invalid school.
        # We only check individuals who are actually assigned to a school (ID > 0)
        # and whose school ID is not in the list of valid, generated schools.
        students_mask = individual_df['indivfacid_1'] > 0
        invalid_school_mask = ~individual_df['indivfacid_1'].isin(valid_school_ids)
        
        individuals_to_reassign_mask = students_mask & invalid_school_mask
        num_to_reassign = individuals_to_reassign_mask.sum()

        # print(f"Number of valid schools generated: {len(valid_school_ids)}")
        # print(f"Number of students assigned to an invalid school: {num_to_reassign}")

        # Step 4: If there are students to correct, perform the reassignment.
        if num_to_reassign > 0:
            # print("Reassigning invalid school IDs evenly among the existing schools...")

            # Repeat the list of valid school IDs to create a new assignment list
            # long enough for all students that need reassignment.
            num_valid_schools = len(valid_school_ids)
            
            # Calculate how many times the list needs to be repeated.
            repetitions = (num_to_reassign // num_valid_schools) + 1
            new_assignments_long = valid_school_ids * repetitions
            
            # Trim the list to the exact required length and shuffle it.
            new_assignments = new_assignments_long[:num_to_reassign]
            random.shuffle(new_assignments)

            # Update the 'indivfacid_1' column in the original individual_df.
            individual_df.loc[individuals_to_reassign_mask, 'indivfacid_1'] = new_assignments
            # print(f"Successfully updated the school assignment for {num_to_reassign} students.")
            log_info(f"Successfully updated the school assignment for {num_to_reassign} students.")
        else:
            # print("All school assignments are valid. No correction was needed.")
            log_info("All school assignments are valid. No correction was needed.")

    # ---------------------------------------------------------------------------------
    #%% Step 28: Re-assign All Workplace IDs for Data Integrity
    # ---------------------------------------------------------------------------------
    # This step resolves two issues at once:
    # 1. It corrects workplace IDs ('indivfacid_2') assigned to buildings that failed generation.
    # 2. It ensures all valid, generated workplaces are assigned employees, fixing "empty" workplaces.
    # The strategy is to re-distribute the entire employed population evenly across all valid workplaces.
    # print("\nStep 28: Performing a full reassignment of workplaces for the employed population...")

    # Step 1: Get the IDs of all valid workplaces that were successfully generated.
    # Workplaces are 'Com' (Commercial), 'Ind' (Industrial), or 'ResCom' (Residential-Commercial).
    valid_workplace_ids = []
    if 'occbld' in final.columns:
        workplace_mask = final['occbld'].isin(['Com', 'Ind', 'ResCom'])
        valid_workplace_ids = final.loc[workplace_mask, 'bldid'].unique().tolist()

    # Step 2: Get all individuals who are assigned a job.
    # In the final dataframe, anyone with a workplace ID > 0 is considered employed.
    employed_mask = individual_df['indivfacid_2'] > 0
    num_employed = employed_mask.sum()

    # Step 3: Check if there are workplaces and employees to perform the assignment.
    if not valid_workplace_ids:
        log_warning("No workplace buildings were generated. Workplace assignments cannot be performed. Please revise your land use and/or tabular inputs for more precise results!")
        # log_msg(sc_warnings, "error", "Workplace Assignment", "No workplace buildings were generated. Workplace assignments cannot be performed. Please revise your land use and/or tabular inputs for more precise results!")

    elif num_employed == 0:
        log_info("There are no employed individuals in the dataset. Skipping workplace assignment. Please revise your land use and/or tabular inputs for more precise results!")
        # log_msg(sc_warnings, "error", "Workplace Assignment", "There are no employed individuals in the dataset. Skipping workplace assignment. Please revise your tabular inputs for more precise results!")
        
    else:
        # print(f"Total number of employed individuals: {num_employed}")
        # print(f"Total number of valid workplaces available: {len(valid_workplace_ids)}")
        # print("Redistributing all employees to ensure all workplaces are utilized...")
        log_info(f"{num_employed} employed individuals have been successfully assigned to {len(valid_workplace_ids)} available workplaces.")
        
        # Step 4: Create a new, evenly distributed list of workplace assignments.
        num_valid_workplaces = len(valid_workplace_ids)

        # Calculate how many times the list of workplaces needs to be repeated.
        repetitions = (num_employed // num_valid_workplaces) + 1
        new_assignments_long = valid_workplace_ids * repetitions
        
        # Trim the list to the exact length of the employed population and shuffle it.
        new_assignments = new_assignments_long[:num_employed]
        random.shuffle(new_assignments)

        # Step 5: Apply the new, corrected assignments to all employed individuals.
        # This overwrites all previous 'indivfacid_2' assignments for the employed population.
        individual_df.loc[employed_mask, 'indivfacid_2'] = new_assignments
        
        # Also update the general 'indivfacid' column to reflect the new workplace.
        # This ensures consistency for individuals who are employed.
        individual_df.loc[employed_mask, 'indivfacid'] = individual_df.loc[employed_mask, 'indivfacid_2']
        
        # print(f"Successfully reassigned {num_employed} employees to {num_valid_workplaces} workplaces.")
        
    # ---------------------------------------------------------------------------------
    #%% Step 29: Final Formatting of the 'indivfacid' Column
    # ---------------------------------------------------------------------------------
    # This final step updates the 'indivfacid' column to a composite string format,
    # combining the school ID and workplace ID for easy reference.
    # The format will be "school_id, workplace_id".
    # print("\nStep 29: Formatting the final 'indivfacid' column...")

    # Ensure the source columns are integer type before converting to string.
    # This prevents ".0" from appearing for float numbers.
    # individual_df['indivfacid_1'] = individual_df['indivfacid_1'].astype(int)
    # individual_df['indivfacid_2'] = individual_df['indivfacid_2'].astype(int)

    # # Combine the two columns into a single string column using vectorized operations,
    # # which is highly efficient.
    # individual_df['indivfacid'] = (
    #     individual_df['indivfacid_1'].astype(str) + 
    #     ", " + 
    #     individual_df['indivfacid_2'].astype(str)
    # )

    return final, household_df, individual_df
