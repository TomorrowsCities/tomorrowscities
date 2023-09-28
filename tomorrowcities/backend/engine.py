import os
os.environ['USE_PYGEOS'] = '0'
import pandas as pd
import geopandas as gpd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import interp1d
import networkx as nx 

def compute_power_infra(nodes,edges,intensity,fragility):
    print('Computing power infrastructure')
    print(nodes.head())
    print(edges.head())
    print(fragility.head())
    print(intensity.head())

    eq_vuln = fragility.rename(columns={"med_slight": "med_ds1", 
                        "med_moderate": "med_ds2",
                        "med_extensive": "med_ds3",
                        "med_complete": "med_ds4",
                        "beta_slight": "beta_ds1",
                        "beta_moderate": "beta_ds2",
                        "beta_extensive": "beta_ds3",
                        "beta_complete": "beta_ds4"})
    
    G_power = nx.Graph()
    for _, node in nodes.iterrows():
        G_power.add_node(node.node_id, pos=(node.x_coord, node.y_coord))
        
    for _, edge in edges.iterrows():
        G_power.add_edge(*(edge.from_node, edge.to_node))  

    nodes = gpd.sjoin_nearest(nodes,intensity, 
                how='left', rsuffix='intensity',distance_col='distance')

    nodes = nodes.merge(eq_vuln, how='left',left_on='eq_vuln',right_on='vuln_string')
    nulls = nodes['med_ds1'].isna()
    nodes.loc[nulls, ['med_ds1','med_ds2','med_ds3','med_ds4']] = [99999,99999,99999,99999]
    nodes.loc[nulls, ['beta_ds1','beta_ds2','beta_ds3','beta_ds4']] = [1,1,1,1]
    #print(nodes.columns)
    nodes['logim'] = np.log(nodes['im']/9.81)
    
    for m in ['med_ds1','med_ds2','med_ds3','med_ds4']:
        nodes[m] = np.log(nodes[m])

    for i in [1,2,3,4]: 
        nodes[f'prob_ds{i}'] = norm.cdf(nodes['logim'],nodes[f'med_ds{i}'],nodes[f'beta_ds{i}'])
    nodes[['prob_ds0','prob_ds5']] = [1,0]
    for i in [1,2,3,4,5]:
        nodes[f'ds_{i}'] = np.abs(nodes[f'prob_ds{i-1}'] - nodes[f'prob_ds{i}'])
    df_ds = nodes[['ds_1','ds_2','ds_3','ds_4','ds_5']]
    nodes['eq_ds'] = df_ds.idxmax(axis='columns').str.extract(r'ds_([0-9]+)').astype('int') - 1
    
    # Damage State Codes
    DS_NO = 0
    DS_SLIGHT = 1
    DS_MODERATE = 2
    DS_EXTENSIVE = 3
    DS_COMPLETE = 4

    # If a damage state is above this threshold (excluding), 
    # we consider the associated node as dead.
    threshold = DS_MODERATE 

    # All Nodes
    all_nodes = set(nodes['node_id'])

    # Power Plants (generators)
    power_plants = set(nodes[nodes['pwr_plant'] == 1]['node_id'])

    # Server Nodes 
    server_nodes = set(nodes[nodes['n_bldgs'] > 0]['node_id'])

    # Nodes directly affected by earthquake. Thresholding takes place.
    damaged_nodes = set(nodes[nodes['eq_ds'] > threshold]['node_id'])

    # Damaged Server Nodes
    damaged_server_nodes = damaged_nodes.intersection(server_nodes)

    # Damaged Power Plants
    damaged_power_plants = damaged_nodes.intersection(power_plants)

    # Operational power plants
    operating_power_plants = power_plants - damaged_nodes

    # Damaged power network
    G_power_dmg = G_power.copy()
    G_power_dmg.remove_nodes_from(damaged_nodes)

    print('Power network before earthquake ', G_power)
    print('Power network after  earthquake ', G_power_dmg)

    # Calculate all distances in the post-earthquake network 
    shortest_distance = nx.shortest_path_length(G_power_dmg)

    operating_nodes = set()
    for source, targets in shortest_distance:
        if source in operating_power_plants:
            for target, hop in targets.items():
                operating_nodes.add(target)

    # Both alive (operating) and server
    operating_server_nodes = operating_nodes.intersection(server_nodes)

    # It must be a server node but not operating
    nonoperating_server_nodes = server_nodes - operating_server_nodes

    # Summary of the nodes
    print('all nodes', all_nodes)    
    print('server nodes', server_nodes)        
    print('power plants', power_plants)
    print('damaged nodes', damaged_nodes)
    print('damaged power plants', damaged_power_plants)
    print('damaged server nodes', damaged_server_nodes)
    print('operating nodes', operating_nodes)
    print('operating power plants', operating_power_plants)
    print('operating server nodes', operating_server_nodes)
    print('nonoperating server nodes', nonoperating_server_nodes)

        
    is_damaged_mapper     = {id:id in damaged_nodes   for id in all_nodes}
    is_operational_mapper = {id:id in operating_nodes for id in all_nodes}
    nodes['is_damaged'] = nodes['node_id'].map(is_damaged_mapper)
    nodes['is_operational'] = nodes['node_id'].map(is_operational_mapper)

    return nodes['eq_ds'], nodes['is_damaged'], nodes['is_operational']

def compute(gdf_landuse, gdf_buildings, df_household, df_individual,gdf_intensity, df_hazard, hazard_type, policies=[]):

    np.random.seed(seed=0)

    column_names = {'zoneID':'zoneid','bldID':'bldid','nHouse':'nhouse',
                    'specialFac':'specialfac','expStr':'expstr','repValue':'repvalue',
                    'xCoord':'xcoord','yCoord':'ycoord','hhID':'hhid','nInd':'nind',
                    'CommFacID':'commfacid','indivId':'individ','eduAttStat':'eduattstat',
                    'indivFacID':'indivfacid','VALUE':'im'}


    gdf_landuse = gdf_landuse.rename(columns=column_names)
    gdf_buildings = gdf_buildings.rename(columns=column_names)
    df_household = df_household.rename(columns=column_names)
    df_individual = df_individual.rename(columns=column_names)
    gdf_intensity = gdf_intensity.rename(columns=column_names)

    # Damage States
    DS_NO = 0
    DS_SLIGHT = 1
    DS_MODERATE = 2
    DS_EXTENSIZE = 3
    DS_COLLAPSED = 4

    # Hazard Types 
    HAZARD_EARTHQUAKE = "earthquake"
    HAZARD_FLOOD = "flood"
    HAZARD_DEBRIS = "debris"

    threshold_flood = 0.2
    threshold_flood_distance = 10
    epsg = 3857 

    # Replace strange TypeX LRS with RCi
    print('deneme',df_hazard.columns)
    df_hazard['expstr'] = df_hazard['expstr'].str.replace('Type[0-9]+','RCi',regex=True)

    number_of_unique_buildings = len(pd.unique(gdf_buildings['bldid']))
    print('number of unique building', number_of_unique_buildings)
    print('number of records in building layer ', len(gdf_buildings['bldid']))

    # Convert both to the same target coordinate system
    gdf_buildings = gdf_buildings.set_crs("EPSG:4326",allow_override=True)
    gdf_intensity = gdf_intensity.set_crs("EPSG:4326",allow_override=True)

    gdf_buildings = gdf_buildings.to_crs(f"EPSG:{epsg}")
    gdf_intensity = gdf_intensity.to_crs(f"EPSG:{epsg}")

    gdf_building_intensity = gpd.sjoin_nearest(gdf_buildings,gdf_intensity, 
                how='left', rsuffix='intensity',distance_col='distance')
    gdf_building_intensity = gdf_building_intensity.drop_duplicates(subset=['bldid'], keep='first')

    gdf_building_intensity = gdf_building_intensity.merge(gdf_landuse[['zoneid','avgincome']],on='zoneid',how='left')

    gdf_building_intensity['rnd'] = np.random.random((len(gdf_building_intensity),1))

    # TODO: Check if the logic makes sense
    if hazard_type == HAZARD_FLOOD:
        away_from_flood = gdf_building_intensity['distance'] > threshold_flood_distance
        print('threshold_flood_distance',threshold_flood_distance)
        print('number of distant buildings', len(gdf_building_intensity.loc[away_from_flood, 'im']))
        gdf_building_intensity.loc[away_from_flood, 'im'] = 0
    gdf_building_intensity[['material','code_level','storeys','occupancy']] =  \
        gdf_building_intensity['expstr'].str.split('+',expand=True)
    gdf_building_intensity['height'] = gdf_building_intensity['storeys'].str.extract(r'([0-9]+)s').astype('int')


    if 1 in policies:
        # First, mid-code -> high-code
        # then, low-code -> mid-code
        gdf_building_intensity.loc[(gdf_building_intensity['occupancy'] == 'Res') & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
        gdf_building_intensity.loc[(gdf_building_intensity['occupancy'] == 'Res') & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            idx = gdf_building_intensity['occupancy'] == 'Res'
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+2))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 2 in policies:
        # First, mid-code -> high-code
        # then, low-code -> mid-code
        gdf_building_intensity.loc[((gdf_building_intensity['avgincome'] == 'lowIncomeA') | (gdf_building_intensity['avgincome'] == 'lowIncomeA')) & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
        gdf_building_intensity.loc[((gdf_building_intensity['avgincome'] == 'lowIncomeA') | (gdf_building_intensity['avgincome'] == 'lowIncomeA')) & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            idx = (gdf_building_intensity['avgincome'] == 'lowIncomeA') | (gdf_building_intensity['avgincome'] == 'lowIncomeA')
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+4))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 3 in policies:
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[:, 'height'] = gdf_building_intensity['height'].apply(lambda h: min(max_height, h+6))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 4 in policies:
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            idx = gdf_building_intensity['specialfac'] != 0
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+4))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 5 in policies:
        # First, mid-code -> high-code
        # then, low-code -> mid-code
        idx = ((gdf_building_intensity['avgincome'] == 'lowIncomeA') |\
                (gdf_building_intensity['avgincome'] == 'lowIncomeA') &\
                (gdf_building_intensity['specialfac'] == 0))
        gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
        gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+1))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 6 in policies:
        # First, mid-code -> high-code
        # then, low-code -> mid-code
        idx = ((gdf_building_intensity['avgincome'] == 'lowIncomeA') |\
                (gdf_building_intensity['avgincome'] == 'lowIncomeA') &\
                (gdf_building_intensity['specialfac'] != 0))
        gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
        gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+1))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 7 in policies:
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            idx = (gdf_building_intensity['rnd'] < 0.70) & (gdf_building_intensity['occupancy'] == 'Res')
            gdf_building_intensity.loc[idx,'occupancy'] = 'Agri'

    if 8 in policies:
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            idx = gdf_building_intensity['specialfac'] == 0
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+4))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 9 in policies:
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[:, 'height'] = gdf_building_intensity['height'].apply(lambda h: min(max_height, h+1))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 10 in policies:
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            idx = gdf_building_intensity['rnd'] < 0.80
            gdf_building_intensity.loc[idx,'occupancy'] = 'Agri'

    lr = (gdf_building_intensity['height'] <= 4)
    mr = (gdf_building_intensity['height'] >= 5) & (gdf_building_intensity['height'] <= 8)
    hr = (gdf_building_intensity['height'] >= 9)
    gdf_building_intensity.loc[lr, 'height_level'] = 'LR'
    gdf_building_intensity.loc[mr, 'height_level'] = 'MR'
    gdf_building_intensity.loc[hr, 'height_level'] = 'HR'

    # Earthquake uses simplified taxonomy
    gdf_building_intensity['vulnstreq'] = \
        gdf_building_intensity[['material','code_level','height_level']] \
            .agg('+'.join,axis=1)
    
    gdf_building_intensity['expstr'] = \
        gdf_building_intensity[['material','code_level','storeys','occupancy']] \
            .agg('+'.join,axis=1)
    
     
    if hazard_type == HAZARD_EARTHQUAKE:
        bld_eq = gdf_building_intensity.merge(df_hazard, left_on='vulnstreq',right_on='expstr', how='left')
        nulls = bld_eq['muds1_g'].isna()
        bld_eq.loc[nulls, ['muds1_g','muds2_g','muds3_g','muds4_g']] = [0.048,0.203,0.313,0.314]
        bld_eq.loc[nulls, ['sigmads1','sigmads2','sigmads3','sigmads4']] = [0.301,0.276,0.252,0.253]
        bld_eq['logim'] = np.log(bld_eq['im']/9.81)
        for m in ['muds1_g','muds2_g','muds3_g','muds4_g']:
            bld_eq[m] = np.log(bld_eq[m])

        for i in [1,2,3,4]: 
            bld_eq[f'prob_ds{i}'] = norm.cdf(bld_eq['logim'],bld_eq[f'muds{i}_g'],bld_eq[f'sigmads{i}'])
        bld_eq[['prob_ds0','prob_ds5']] = [1,0]
        for i in [1,2,3,4,5]:
            bld_eq[f'ds_{i}'] = np.abs(bld_eq[f'prob_ds{i-1}'] - bld_eq[f'prob_ds{i}'])
        df_ds = bld_eq[['ds_1','ds_2','ds_3','ds_4','ds_5']]
        bld_eq['eq_ds'] = df_ds.idxmax(axis='columns').str.extract(r'ds_([0-9]+)').astype('int') - 1
        # Create a simplified building-hazard relation
        bld_hazard = bld_eq[['bldid','eq_ds']]
        bld_hazard = bld_hazard.rename(columns={'eq_ds':'ds'})

        ds_str = {0: 'No Damage',1:'Low',2:'Medium',3:'High',4:'Collapsed'}

    elif hazard_type == HAZARD_FLOOD:
        bld_flood = gdf_building_intensity.merge(df_hazard, on='expstr', how='left')
        x = np.array([0,0.5,1,1.5,2,3,4,5,6])
        y = bld_flood[['hw0','hw0_5','hw1','hw1_5','hw2','hw3','hw4','hw5','hw6']].to_numpy()
        xnew = bld_flood['im'].to_numpy()
        flood_mapping = interp1d(x,y,axis=1,kind='linear',bounds_error=False, fill_value=(0,1))
        # TODO: find another way for vectorized interpolate
        bld_flood['fl_prob'] = np.diag(flood_mapping(xnew))
        bld_flood['fl_ds'] = 0
        bld_flood.loc[bld_flood['fl_prob'] > threshold_flood,'fl_ds'] = 1
        # Create a simplified building-hazard relation
        bld_hazard = bld_flood[['bldid','fl_ds']]
        bld_hazard = bld_hazard.rename(columns={'fl_ds':'ds'})

        ds_str = {0: 'No Damage',1:'Flooded'}
    
    return bld_hazard


def calculate_metrics(gdf_buildings, df_household, df_individual, hazard_type, policies=[],capacity=1.0):
    # only use necessary columns
    bld_hazard = gdf_buildings[['bldid','ds','expstr','nhouse','residents']]
    bld_hazard[['material','code_level','storeys','occupancy']] =  \
        bld_hazard['expstr'].str.split('+',expand=True).copy()
    #bld_hazard['occupancy'] = bld_hazard['occupancy'].astype('category')

    # Find the damage state of the building that the household is in
    df_household_bld = df_household.merge(bld_hazard[['bldid','ds']], on='bldid', how='left',validate='many_to_one')

    # Find the damage state of the hospital that the household is associated with
    df_hospitals = df_household.merge(bld_hazard[['bldid', 'ds']], 
            how='left', left_on='commfacid', right_on='bldid', suffixes=['','_comm'],
            validate='many_to_one')

    # Find the occupancy of facility that the individual is associated
    df_individual_occupancy = df_individual.merge(bld_hazard[['bldid','occupancy','ds']], 
                        how='inner',left_on='indivfacid',right_on='bldid',
                        suffixes=['_l','_r'],validate='many_to_one')

    # Filtering working places
    df_workers = df_individual_occupancy.query('occupancy in ["Com","ResCom","Ind"]')

    # Filtering schools
    df_students = df_individual_occupancy.query('occupancy in ["Edu"]')

    # connect individuals to damage state of associated hospitals
    df_indiv_hosp = df_individual.merge(df_hospitals[['hhid','ds']], 
                        how='left', on='hhid', validate='many_to_one')

    # get the ds of household that individual lives in
    df_indiv_household = df_individual[['hhid','individ']].merge(df_household_bld[['hhid','ds']])

    # Collect all damage states in a single table
    df_displaced_indiv = df_indiv_hosp.rename(columns={'ds':'ds_hospital'})\
        .merge(df_workers[['individ','ds']].rename(columns={'ds':'ds_workplace'}),on='individ', how='left')\
        .merge(df_students[['individ','ds']].rename(columns={'ds':'ds_school'}), on='individ', how='left')\
        .merge(df_indiv_household[['individ','ds']].rename(columns={'ds':'ds_household'}), on='individ',how='left')\
        .merge(df_household[['hhid','bldid']],on='hhid',how='left')

    DS_NO = 0
    DS_SLIGHT = 1
    DS_MODERATE = 2
    DS_EXTENSIZE = 3
    DS_COLLAPSED = 4

    # Hazard Types 
    HAZARD_EARTHQUAKE = "earthquake"
    HAZARD_FLOOD = "flood"
    HAZARD_DEBRIS = "debris"

    if hazard_type == HAZARD_EARTHQUAKE:
    # Effect of policies on thresholds
    # First get the global threshold
        thresholds = {f'metric{id}': DS_SLIGHT for id in range(8)}
    else:
        # Default thresholds for flood and debris
        # For flood, there are only two states: 0 or 1.
        # So threshold is set to 0.
        thresholds = {f'metric{id}': DS_NO for id in range(8)}

    # metric 1 number of unemployed workers in each building
    df_workers_per_building = df_workers[df_workers['ds'] > thresholds['metric1']][['individ','hhid','ds']].merge(
        df_household[['hhid','bldid']],on='hhid',how='left').groupby(
            'bldid',as_index=False).agg({'individ':'count'})

    df_metric1 = bld_hazard.merge(df_workers_per_building,how='left',left_on='bldid',right_on = 'bldid')[['bldid','residents','individ']]
    df_metric1.rename(columns={'individ':'metric1'}, inplace=True)
    df_metric1['metric1'] = (df_metric1['metric1'].fillna(0) * capacity).astype(int)
    df_metric1['metric1'] = df_metric1[['residents','metric1']].min(axis=1)
    df_metric1['metric1'] = df_metric1['metric1'].fillna(0).astype(int)

    # metric 2 number of students in each building with no access to schools
    df_students_per_building = df_students[df_students['ds'] > thresholds['metric2']][['individ','hhid','ds']].merge(
        df_household[['hhid','bldid']],on='hhid',how='left').groupby(
            'bldid',as_index=False).agg({'individ':'count'})

    df_metric2 = bld_hazard.merge(df_students_per_building,how='left',left_on='bldid',right_on = 'bldid')[['bldid','residents','individ']]
    df_metric2.rename(columns={'individ':'metric2'}, inplace=True)
    df_metric2['metric2'] = (df_metric2['metric2'].fillna(0) * capacity).astype(int)
    df_metric2['metric2'] = df_metric2[['residents','metric2']].min(axis=1)
    df_metric2['metric2'] = df_metric2['metric2'].fillna(0).astype(int)

    # metric 3 number of households in each building with no access to hospitals
    df_hospitals_per_household = df_hospitals[df_hospitals['ds'] > thresholds['metric3']].groupby(
        'bldid',as_index=False).agg({'hhid':'count'})

    df_metric3 = bld_hazard.merge(df_hospitals_per_household,how='left',left_on='bldid',right_on='bldid')[['bldid','nhouse','hhid']]
    df_metric3.rename(columns={'hhid':'metric3'}, inplace=True)
    df_metric3['metric3'] = (df_metric3['metric3'].fillna(0) * capacity).astype(int)
    df_metric3['metric3'] = df_metric3[['nhouse','metric3']].min(axis=1)
    df_metric3['metric3'] = df_metric3['metric3'].fillna(0).astype(int)

    # metric 4 number of individuals in each building with no access to hospitals
    df_hospitals_per_individual = df_hospitals[df_hospitals['ds'] > thresholds['metric4']].groupby(
        'bldid',as_index=False).agg({'nind':'sum'})

    df_metric4 = bld_hazard.merge(df_hospitals_per_individual,how='left',left_on='bldid',right_on='bldid')[['bldid','residents','nind']]
    df_metric4.rename(columns={'nind':'metric4'}, inplace=True)
    df_metric4['metric4'] = (df_metric4['metric4'].fillna(0) * capacity).astype(int)
    df_metric4['metric4'] = df_metric4[['residents','metric4']].min(axis=1)
    df_metric4['metric4'] = df_metric4['metric4'].fillna(0).astype(int)

    # metric 5 number of damaged households in each building
    df_homeless_households = df_household_bld[df_household_bld['ds'] > thresholds['metric5']].groupby(
        'bldid',as_index=False).agg({'hhid':'count'})

    df_metric5 = bld_hazard.merge(df_homeless_households,how='left',left_on='bldid',right_on='bldid')[['bldid','nhouse','hhid']]
    df_metric5.rename(columns={'hhid':'metric5'}, inplace=True)
    df_metric5['metric5'] = (df_metric5['metric5'].fillna(0) * capacity).astype(int)
    df_metric5['metric5'] = df_metric5[['nhouse','metric5']].min(axis=1)
    df_metric5['metric5'] = df_metric5['metric5'].fillna(0).astype(int)

    # metric 6 number of homeless individuals in each building
    df_homeless_individuals = df_household_bld[df_household_bld['ds'] > thresholds['metric6']].groupby(
        'bldid',as_index=False).agg({'nind':'sum'})

    df_metric6 = bld_hazard.merge(df_homeless_individuals,how='left',left_on='bldid',right_on='bldid')[['bldid','residents','nind']]
    df_metric6.rename(columns={'nind':'metric6'}, inplace=True)
    df_metric6['metric6'] = (df_metric6['metric6'].fillna(0) * capacity).astype(int)
    df_metric6['metric6'] = df_metric6[['residents','metric6']].min(axis=1)
    df_metric6['metric6'] = df_metric6['metric6'].fillna(0).astype(int)

    # metric 7 the number of displaced individuals in each building
    # more info: an individual is displaced if at least of the conditions below hold
    df_disp_per_bld = df_displaced_indiv[(df_displaced_indiv['ds_household'] > thresholds['metric6']) |
                                        (df_displaced_indiv['ds_school'] > thresholds['metric2']) |
                                        (df_displaced_indiv['ds_workplace'] > thresholds['metric1']) |
                                        (df_displaced_indiv['ds_hospital'] > thresholds['metric4'])]\
                                            .groupby('bldid',as_index=False)\
                                            .agg({'individ':'count'})

    df_metric7 = bld_hazard.merge(df_disp_per_bld,how='left',left_on='bldid',right_on='bldid')[['bldid','residents','individ']]
    df_metric7.rename(columns={'individ':'metric7'}, inplace=True)
    df_metric7['metric7'] = (df_metric7['metric7'].fillna(0) * capacity).astype(int)
    df_metric7['metric7'] = df_metric7[['residents','metric7']].min(axis=1)
    df_metric7['metric7'] = df_metric7['metric7'].fillna(0).astype(int)



    df_metrics = {'metric1': df_metric1,
                'metric2': df_metric2,
                'metric3': df_metric3,
                'metric4': df_metric4,
                'metric5': df_metric5,
                'metric6': df_metric6,
                'metric7': df_metric7}


    number_of_workers = len(df_workers)
    print('number of workers', number_of_workers)

    number_of_students = len(df_students)
    print('number of students', number_of_students)

    number_of_households = len(df_household)
    print('number of households', number_of_households)

    number_of_individuals = len(df_individual)
    print('number of individuals', number_of_individuals)
    metrics = {"metric1": {"desc": "Number of workers unemployed", "value": 0, "max_value": number_of_workers},
                "metric2": {"desc": "Number of children with no access to education", "value": 0, "max_value": number_of_students},
                "metric3": {"desc": "Number of households with no access to hospital", "value": 0, "max_value": number_of_households},
                "metric4": {"desc": "Number of individuals with no access to hospital", "value": 0, "max_value": number_of_individuals},
                "metric5": {"desc": "Number of households displaced", "value": 0, "max_value": number_of_households},
                "metric6": {"desc": "Number of homeless individuals", "value": 0, "max_value": number_of_individuals},
                "metric7": {"desc": "Population displacement", "value": 0, "max_value": number_of_individuals},}
    metrics["metric1"]["value"] = int(df_metric1['metric1'].sum())
    metrics["metric2"]["value"] = int(df_metric2['metric2'].sum())
    metrics["metric3"]["value"] = int(df_metric3['metric3'].sum())
    metrics["metric4"]["value"] = int(df_metric4['metric4'].sum())
    metrics["metric5"]["value"] = int(df_metric5['metric5'].sum())
    metrics["metric6"]["value"] = int(df_metric6['metric6'].sum())
    metrics["metric7"]["value"] = int(df_metric7['metric7'].sum())

    return metrics, df_metrics