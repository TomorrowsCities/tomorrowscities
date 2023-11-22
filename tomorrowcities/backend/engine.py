import os
os.environ['USE_PYGEOS'] = '0'
import pandas as pd
import geopandas as gpd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import interp1d
import networkx as nx 

def compute_road_infra(buildings, household, individual,
                        nodes, edges, intensity, fragility, hazard, 
                        road_water_height_threshold,
                        threshold_flood_distance):

    DS_NO = 0
    DS_SLIGHT = 1
    DS_MODERATE = 2
    DS_EXTENSIVE = 3
    DS_COMPLETE = 4

    # If a damage state is above this threshold (excluding), 
    # we consider the associated node as dead.
    threshold = DS_SLIGHT

    gdf_buildings = buildings.set_crs("EPSG:4326",allow_override=True)
    gdf_intensity = intensity.set_crs("EPSG:4326",allow_override=True)
    gdf_nodes = nodes.set_crs("EPSG:4326",allow_override=True)
    gdf_edges = edges.set_crs("EPSG:4326",allow_override=True)

    epsg = 3857 
    gdf_buildings = gdf_buildings.to_crs(f"EPSG:{epsg}")
    gdf_intensity = gdf_intensity.to_crs(f"EPSG:{epsg}")
    gdf_nodes = gdf_nodes.to_crs(f"EPSG:{epsg}")
    gdf_edges = gdf_edges.to_crs(f"EPSG:{epsg}")


    G = nx.DiGraph()
    for _, node in gdf_nodes.iterrows():
        G.add_node(node.node_id, pos=(node.geometry.x, node.geometry.y))
        
    for _, edge in gdf_edges.iterrows():
        G.add_edge(*(edge.from_node, edge.to_node))  

    gdf_buildings = gdf_buildings.drop(columns=['node_id'])
    gdf_buildings = gpd.sjoin_nearest(gdf_buildings,gdf_nodes, 
                how='left', rsuffix='road_node',distance_col='road_node_distance')

    if hazard in ['flood', 'debris','landslide']:
        gdf_edges = gpd.sjoin_nearest(gdf_edges, gdf_intensity, how='left',
                                          rsuffix='intensity',distance_col='distance')
        # TODO: sjoin_nearest or the approach below: compare
        #roads_with_width = gdf_edges['geometry'].buffer(threshold_flood_distance)
        #for i, road in enumerate(roads_with_width):
        #    print(i)
        #    within_ims = gdf_intensity.clip(road)
        #    if len(within_ims) > 0:
        #        max_im = within_ims['im'].max()
        #    else:
        #        max_im = 0
        #    gdf_edges.loc[i,'im'] = max_im
        if hazard == 'landslide':
            print('before')
            print(gdf_edges.loc[0])
            gdf_edges['susceptibility'] = 'low'
            gdf_edges.loc[gdf_edges['im'] == 2.0, 'susceptibility'] = 'medium'
            gdf_edges.loc[gdf_edges['im'] == 3.0, 'susceptibility'] = 'high'

            fragility['landslide_expstr'] = fragility['expstr'].astype(str) + "+"+ fragility["susceptibility"].astype(str) 
            gdf_edges['landslide_expstr'] = 'roads' 
            gdf_edges['landslide_expstr'] = gdf_edges['landslide_expstr'] + "+" + gdf_edges['susceptibility'].astype(str)
            gdf_edges = gdf_edges.merge(fragility, on='landslide_expstr', how='left')
            gdf_edges['ds'] = DS_NO
            gdf_edges['rnd'] = np.random.random((len(gdf_edges),1))
            collapsed_idx = (gdf_edges['rnd'] < gdf_edges['collapse_probability']) 
            gdf_edges.loc[collapsed_idx, 'ds'] = DS_COMPLETE
            gdf_edges.loc[collapsed_idx, 'is_damaged'] = True
            print('after')
            print(gdf_edges.loc[0])
        else:
            gdf_edges.loc[gdf_edges['im'] > road_water_height_threshold, 'ds'] = 1
            gdf_edges.loc[gdf_edges['im'] > road_water_height_threshold, 'is_damaged'] = True
    elif hazard == 'earthquake':
        fragility = fragility.rename(columns={"med_slight": "med_ds1", 
                        "med_moderate": "med_ds2",
                        "med_extensive": "med_ds3",
                        "med_complete": "med_ds4"})

        gdf_edges_centroids = gdf_edges.copy()
        gdf_edges_centroids['geometry'] = gdf_edges_centroids.geometry.centroid
        gdf_edges = gpd.sjoin_nearest(gdf_edges_centroids, gdf_intensity,how='left',rsuffix='intensity',distance_col='intensity_distance')
        
        gdf_edges = gdf_edges.merge(fragility, how='left',left_on='bridge_type',right_on='vuln_string')

        nulls = gdf_edges['med_ds1'].isna()
        gdf_edges.loc[nulls, ['med_ds1','med_ds2','med_ds3','med_ds4']] = [99999,99999,99999,99999]
        gdf_edges.loc[nulls, ['dispersion']] = [1]

        gdf_edges['log_im'] = np.log(gdf_edges['im'])
        for m in ['med_ds1','med_ds2','med_ds3','med_ds4']:
            gdf_edges[m] = np.log(gdf_edges[m])

        for i in [1,2,3,4]: 
            gdf_edges[f'prob_ds{i}'] = norm.cdf(gdf_edges['log_im'],gdf_edges[f'med_ds{i}'],gdf_edges['dispersion'])
        gdf_edges[['prob_ds0','prob_ds5']] = [1,0]
        for i in [1,2,3,4,5]:
            gdf_edges[f'ds_{i}'] = np.abs(gdf_edges[f'prob_ds{i-1}'] - gdf_edges[f'prob_ds{i}'])
        df_ds = gdf_edges[['ds_1','ds_2','ds_3','ds_4','ds_5']]
        gdf_edges['ds'] = df_ds.idxmax(axis='columns').str.extract(r'ds_([0-9]+)').astype('int') - 1

        gdf_edges.loc[gdf_edges['ds'] > threshold,'is_damaged'] = True

    print(gdf_buildings.columns)
    building_count_on_nodes = gdf_buildings.groupby(['node_id','occupancy']).agg({'bldid': 'count'}).reset_index().rename(columns={'bldid':'buildings'})

    all_nodes = set(gdf_nodes['node_id'])
    non_empty_nodes = set(building_count_on_nodes['node_id'])

    hospital_nodes = set(building_count_on_nodes[(building_count_on_nodes['occupancy'] == 'Hea') & (building_count_on_nodes['buildings'] > 0)]['node_id'])
    source_nodes = non_empty_nodes - hospital_nodes

    # Remove damaged roads/bridges
    G_dmg = G.copy()
    for i, edge in gdf_edges.iterrows():
        if edge['is_damaged']:
            try:
                G_dmg.remove_edge(*(edge.from_node, edge.to_node))
            except:
                # when remove an edge multiple times, ignore error
                pass

    print('network before ', G)
    print('network after  ', G_dmg)

    household_w_node_id = household.drop(columns=['node_id']).merge(gdf_buildings[['bldid','node_id']], on='bldid', how='left')
    household_w_node_id['hospital_access'] = False

    for hospital_node in hospital_nodes:
        for node_with_hospital_access in nx.descendants(G_dmg,hospital_node):
            idx = gdf_buildings['node_id'] == node_with_hospital_access
            gdf_buildings.loc[idx, 'hospital_access'] = True
            for hospital_bld in gdf_buildings[(gdf_buildings['node_id'] == hospital_node) & (gdf_buildings['occupancy'] == 'Hea')]['bldid']:
                #print(f'node {node_with_hospital_access} has access to {hospital_bld} / {hospital_node}')   
                idx = (household_w_node_id['commfacid'] == hospital_bld) & (household_w_node_id['node_id'] == node_with_hospital_access)
                household_w_node_id.loc[idx, 'hospital_access'] = True

    # Workplace/School (facility) connectivity analysis
    # For each individual, find the closest road node (closest) of the
    # household and the facility

    print('individua')
    print(individual)
    print('household_w_node_id')
    print(household_w_node_id)
    print('gdf_buildings')
    print(gdf_buildings)
    individual_w_nodes = individual.merge(household_w_node_id[['hhid','node_id']],on='hhid',how='left')\
                        .rename(columns={'node_id':'household_node_id'})\
                        .merge(gdf_buildings[['bldid','node_id']],how='left',left_on='indivfacid',right_on='bldid')\
                        .rename(columns={'node_id':'facility_node_id'})
    print('individual_w_nodes')
    print(individual_w_nodes)
    # Calculate distances between all nodes in the damaged network
    shortest_distance = nx.shortest_path_length(G_dmg)

    # Create a dictionary to store all open connections
    connection_dict = dict()
    for source, targets in shortest_distance:
        connection_dict[source] = dict()
        for target, hop in targets.items():
            connection_dict[source][target] = True

    # Based on connectivity, fill-in facillity_access attribute in the individual layer
    print(individual_w_nodes)
    individual_w_nodes['facility_access'] = individual_w_nodes.apply(lambda x: x['facility_node_id'] in connection_dict[x['household_node_id']].keys(),axis=1)

    return gdf_edges['ds'], gdf_edges['is_damaged'], gdf_buildings['node_id'], gdf_buildings['hospital_access'], household_w_node_id['node_id'], household_w_node_id['hospital_access'], individual_w_nodes['facility_access']

def compute_power_infra(buildings, household, nodes,edges,intensity,fragility,hazard,
                        threshold_flood, threshold_flood_distance):
    print('Computing power infrastructure')
    print(nodes.head())
    print(edges.head())
    print(fragility.head())
    print(intensity.head())

    DS_NO = 0
    DS_SLIGHT = 1
    DS_MODERATE = 2
    DS_EXTENSIVE = 3
    DS_COMPLETE = 4

    # If a damage state is above this threshold (excluding), 
    # we consider the associated node as dead.
    threshold = DS_MODERATE

    gdf_buildings = buildings.set_crs("EPSG:4326",allow_override=True)
    gdf_intensity = intensity.set_crs("EPSG:4326",allow_override=True)
    gdf_nodes = nodes.set_crs("EPSG:4326",allow_override=True)
    gdf_edges = edges.set_crs("EPSG:4326",allow_override=True)

    epsg = 3857 
    gdf_buildings = gdf_buildings.to_crs(f"EPSG:{epsg}")
    gdf_intensity = gdf_intensity.to_crs(f"EPSG:{epsg}")
    gdf_nodes = gdf_nodes.to_crs(f"EPSG:{epsg}")
    gdf_edges = gdf_edges.to_crs(f"EPSG:{epsg}")

    G_power = nx.Graph()
    for _, node in gdf_nodes.iterrows():
        G_power.add_node(node.node_id, pos=(node.geometry.x, node.geometry.y))
        
    for _, edge in edges.iterrows():
        G_power.add_edge(*(edge.from_node, edge.to_node))  
    
    # Assign nearest intensity to power nodes
    gdf_nodes = gpd.sjoin_nearest(gdf_nodes,gdf_intensity, 
                how='left', rsuffix='intensity',distance_col='distance')

    if hazard == 'earthquake':
        fragility = fragility.rename(columns={"med_slight": "med_ds1", 
                    "med_moderate": "med_ds2",
                    "med_extensive": "med_ds3",
                    "med_complete": "med_ds4",
                    "beta_slight": "beta_ds1",
                    "beta_moderate": "beta_ds2",
                    "beta_extensive": "beta_ds3",
                    "beta_complete": "beta_ds4"})
        #gdf_nodes = gdf_nodes.merge(fragility, how='left',left_on='eq_vuln',right_on='vuln_string')
        gdf_nodes = gdf_nodes.merge(fragility, how='left',left_on='eq_frgl',right_on='vuln_string')
        nulls = gdf_nodes['med_ds1'].isna()
        gdf_nodes.loc[nulls, ['med_ds1','med_ds2','med_ds3','med_ds4']] = [99999,99999,99999,99999]
        gdf_nodes.loc[nulls, ['beta_ds1','beta_ds2','beta_ds3','beta_ds4']] = [1,1,1,1]
        
        gdf_nodes['logim'] = np.log(gdf_nodes['im']/9.81)
    
        for m in ['med_ds1','med_ds2','med_ds3','med_ds4']:
            gdf_nodes[m] = np.log(gdf_nodes[m])

        for i in [1,2,3,4]: 
            gdf_nodes[f'prob_ds{i}'] = norm.cdf(gdf_nodes['logim'],gdf_nodes[f'med_ds{i}'],gdf_nodes[f'beta_ds{i}'])
        gdf_nodes[['prob_ds0','prob_ds5']] = [1,0]
        for i in [1,2,3,4,5]:
            gdf_nodes[f'ds_{i}'] = np.abs(gdf_nodes[f'prob_ds{i-1}'] - gdf_nodes[f'prob_ds{i}'])
        df_ds = gdf_nodes[['ds_1','ds_2','ds_3','ds_4','ds_5']]
        gdf_nodes['ds'] = df_ds.idxmax(axis='columns').str.extract(r'ds_([0-9]+)').astype('int') - 1
    elif hazard == 'landslide':
        print(gdf_nodes.loc[0])
        gdf_nodes['rnd'] = np.random.random((len(gdf_nodes),1))
        if 'ls_susceptibility' in gdf_nodes.columns:
            gdf_nodes['susceptibility'] = gdf_nodes['ls_susceptibility']
        else:
            gdf_nodes['susceptibility'] = 'low'
            gdf_nodes.loc[gdf_nodes['im'] == 2.0, 'susceptibility'] = 'medium'
            gdf_nodes.loc[gdf_nodes['im'] == 3.0, 'susceptibility'] = 'high'
        fragility['landslide_expstr'] = fragility['expstr'].astype(str) + "+"+ fragility["susceptibility"].astype(str) 
        gdf_nodes['landslide_expstr'] = gdf_nodes['ls_frgl'].astype(str) + "+" \
                                                   + gdf_nodes['susceptibility'].astype(str)
        gdf_nodes = gdf_nodes.merge(fragility, on='landslide_expstr', how='left')
        gdf_nodes['ds'] = DS_NO
        collapsed_idx = (gdf_nodes['rnd'] < gdf_nodes['collapse_probability']) 
        gdf_nodes.loc[collapsed_idx, 'ds'] = DS_COMPLETE
        print(gdf_nodes.loc[0])
    elif hazard == 'flood':
        away_from_flood = gdf_nodes['distance'] > threshold_flood_distance
        print('threshold_flood_distance',threshold_flood_distance)
        print('number of distant buildings', len(gdf_nodes.loc[away_from_flood, 'im']))
        gdf_nodes.loc[away_from_flood, 'im'] = 0

        # Override nearest intensity if water depth is already provided
        if "fl_water_depth" in gdf_nodes.columns:
            idx = gdf_nodes['fl_water_depth'] >= 0.0
            gdf_nodes.loc[idx, 'im'] = gdf_nodes['fl_water_depth']

        gdf_nodes = gdf_nodes.merge(fragility, left_on='fl_vuln', right_on='expstr', how='left')
        x = np.array([0,0.5,1,1.5,2,3,4,5,6])
        y = gdf_nodes[['hw0','hw0_5','hw1','hw1_5','hw2','hw3','hw4','hw5','hw6']].to_numpy()
        xnew = gdf_nodes['im'].to_numpy()
        flood_mapping = interp1d(x,y,axis=1,kind='linear',bounds_error=False, fill_value=(0,1))
        # TODO: find another way for vectorized interpolate
        gdf_nodes['fl_prob'] = np.diag(flood_mapping(xnew))
        gdf_nodes['ds'] = 0
        gdf_nodes.loc[gdf_nodes['fl_prob'] > threshold_flood,'ds'] = 1
        
    # All Nodes
    all_nodes = set(gdf_nodes['node_id'])

    # Power Plants (generators)
    power_plants = set(gdf_nodes[gdf_nodes['pwr_plant'] == 1]['node_id'])

    # Server Nodes 
    server_nodes = set(gdf_nodes[gdf_nodes['n_bldgs'] > 0]['node_id'])

    # Nodes directly affected by earthquake. Thresholding takes place.
    damaged_nodes = set(gdf_nodes[gdf_nodes['ds'] > threshold]['node_id'])

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
    gdf_nodes['is_damaged'] = gdf_nodes['node_id'].map(is_damaged_mapper)
    gdf_nodes['is_operational'] = gdf_nodes['node_id'].map(is_operational_mapper)

    # Find nearest server nodes
    gdf_buildings = gdf_buildings.drop(columns=['node_id'])
    gdf_buildings = gpd.sjoin_nearest(gdf_buildings,gdf_nodes[gdf_nodes['n_bldgs'] > 0], 
                how='left', rsuffix='power_node',distance_col='power_node_distance')
    
    # If nearest server is operational, then building has power, othwerwise not
    gdf_buildings['has_power'] = gdf_buildings['node_id'].map(is_operational_mapper)

    # Pass nearest server node information to household
    household_w_node_id = household.drop(columns=['node_id']).merge(gdf_buildings[['bldid','node_id']], on='bldid', how='left')
    household_w_node_id['has_power'] = household_w_node_id['node_id'].map(is_operational_mapper)

    hospitals = household[['hhid','commfacid']].merge(gdf_buildings[['bldid','has_power']], 
            how='left', left_on='commfacid', right_on='bldid', suffixes=['','_comm'],
            validate='many_to_one')

    return gdf_nodes['ds'], gdf_nodes['is_damaged'], gdf_nodes['is_operational'], \
           gdf_buildings['has_power'], household_w_node_id['has_power'],hospitals['has_power'] 

def compute(gdf_landuse, gdf_buildings, df_household, df_individual,gdf_intensity, df_hazard, hazard_type, policies=[],
            threshold_flood = 0.2, threshold_flood_distance = 10):

    if hazard_type != "landslide":
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

    if hazard_type == "landslide":
        print('----------up side down prev', gdf_building_intensity.shape)
        print(pd.unique(gdf_building_intensity['im']))
        gdf_building_intensity['susceptibility'] = 'low'
        gdf_building_intensity.loc[gdf_building_intensity['im'] == 2.0, 'susceptibility'] = 'medium'
        gdf_building_intensity.loc[gdf_building_intensity['im'] == 3.0, 'susceptibility'] = 'high'
        print(gdf_building_intensity.loc[0])
        print(gdf_building_intensity.columns)
        print(df_hazard.loc[0])
        df_hazard['landslide_expstr'] = df_hazard['expstr'].astype(str) +"+"+ df_hazard["susceptibility"].astype(str) 

        gdf_building_intensity['landslide_expstr'] = gdf_building_intensity['material'].astype(str)  + "+" \
                                                   + gdf_building_intensity['code_level'].astype(str)  + "+" \
                                                   + gdf_building_intensity["susceptibility"].astype(str) 
        print('x1', gdf_building_intensity.columns)
        print('x2', df_hazard.columns)

        print(len(gdf_building_intensity))
        gdf_building_collapse_prob = gdf_building_intensity.merge(df_hazard, 
                                        on='landslide_expstr', how='left')
        print('----------up side down ', gdf_building_collapse_prob.shape)
        print(gdf_building_collapse_prob.loc[0])
        print(len(gdf_building_collapse_prob))
        gdf_building_collapse_prob['ds'] = DS_NO
        collapsed_idx = (gdf_building_collapse_prob['rnd'] < gdf_building_collapse_prob['collapse_probability']) 
        gdf_building_collapse_prob.loc[collapsed_idx, 'ds'] = DS_COLLAPSED
        bld_hazard = gdf_building_collapse_prob[['bldid','ds']]
        return bld_hazard

    # TODO: Check if the logic makes sense
    if hazard_type == HAZARD_FLOOD:
        away_from_flood = gdf_building_intensity['distance'] > threshold_flood_distance
        print('threshold_flood_distance',threshold_flood_distance)
        print('number of distant buildings', len(gdf_building_intensity.loc[away_from_flood, 'im']))
        gdf_building_intensity.loc[away_from_flood, 'im'] = 0

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

    for pid in [11, 12, 19]:
        if pid in policies:
            gdf_building_intensity['temp_rand'] = np.random.random((len(gdf_building_intensity),1))
            idx = gdf_building_intensity['temp_rand'] < 0.50
            gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
            gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
            if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
                max_height = gdf_building_intensity['height'].max()
                gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+1))
                gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s') 

    for pid in [14, 15, 20]:
        if pid in policies:
            gdf_building_intensity['temp_rand'] = np.random.random((len(gdf_building_intensity),1))
            idx = gdf_building_intensity['temp_rand'] < 0.10
            gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
            gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
            if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
                max_height = gdf_building_intensity['height'].max()
                gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+1))
                gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s') 

    if 16 in policies:
        idx = gdf_building_intensity['specialfac'] != 0
        gdf_building_intensity.loc[idx, 'code_level'] == 'HC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+6))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 17 in policies:
        idx = (gdf_building_intensity['occupancy'] == 'Edu') | (gdf_building_intensity['occupancy'] == 'Hea') 
        gdf_building_intensity.loc[idx, 'code_level'] == 'HC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+6))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

    if 18 in policies:
        idx = ((gdf_building_intensity['avgincome'] == 'lowIncomeA') |\
                (gdf_building_intensity['avgincome'] == 'lowIncomeA') &\
                (gdf_building_intensity['rnd'] < 0.50))
        gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'MC'), 'code_level'] = 'HC'
        gdf_building_intensity.loc[idx & (gdf_building_intensity['code_level'] == 'LC'), 'code_level'] = 'MC'
        if hazard_type == HAZARD_FLOOD or hazard_type == HAZARD_DEBRIS:
            max_height = gdf_building_intensity['height'].max()
            gdf_building_intensity.loc[idx, 'height'] = gdf_building_intensity[idx]['height'].apply(lambda h: min(max_height, h+1))
            gdf_building_intensity['storeys'] = gdf_building_intensity['height'].apply(lambda h: str(h)+'s')

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
        print('no correspnding record in exposure', pd.unique(bld_eq.loc[nulls, 'vulnstreq']))
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


def calculate_metrics(gdf_buildings, df_household, df_individual, infra, hazard_type, policies=[],capacity=1.0):
    # only use necessary columns
    bld_hazard = gdf_buildings[['bldid','ds','expstr','occupancy','storeys',
                                'code_level','material','nhouse','residents','hospital_access','has_power']]

    # Find the damage state of the building that the household is in
    df_household_bld = df_household.merge(bld_hazard[['bldid','ds']], on='bldid', how='left',validate='many_to_one')

    # Find the damage state of the hospital that the household is associated with
    df_hospitals = df_household.merge(bld_hazard[['bldid', 'ds']], 
            how='left', left_on='commfacid', right_on='bldid', suffixes=['','_comm'],
            validate='many_to_one')

    # Find the occupancy of facility that the individual is associated
    df_individual_occupancy = df_individual.merge(bld_hazard[['bldid','occupancy','ds','has_power']], 
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
    df_indiv_household = df_individual[['hhid','individ']].merge(df_household_bld[['hhid','ds','hospital_access','hospital_has_power']])

    # Collect all damage states in a single table
    df_displaced_indiv = df_indiv_hosp.rename(columns={'ds':'ds_hospital'})\
        .merge(df_workers[['individ','ds','has_power']].rename(columns={'ds':'ds_workplace','has_power':'workplace_power'}),on='individ', how='left')\
        .merge(df_students[['individ','ds','has_power']].rename(columns={'ds':'ds_school','has_power':'school_power'}), on='individ', how='left')\
        .merge(df_indiv_household[['individ','ds','hospital_access','hospital_has_power']].rename(columns={'ds':'ds_household'}), on='individ',how='left')\
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


    if 12 in policies:
        for m in [2,3,4,5,7]:
            thresholds[f'metric{m}'] += 1

    # metric 1 number of unemployed workers in each building
    metric1_index = df_workers['ds'] > thresholds['metric1']
    if 'power' in infra:
        metric1_index = (metric1_index) | (df_workers['has_power'] == False)
    if 'road' in infra:
        metric1_index = (metric1_index) | (df_workers['facility_access'] == False)
    df_workers_per_building = df_workers[metric1_index][['individ','hhid','ds']].merge(
        df_household[['hhid','bldid']],on='hhid',how='left').groupby(
            'bldid',as_index=False).agg({'individ':'count'})

    df_metric1 = bld_hazard.merge(df_workers_per_building,how='left',left_on='bldid',right_on = 'bldid')[['bldid','residents','individ']]
    df_metric1.rename(columns={'individ':'metric1'}, inplace=True)
    df_metric1['metric1'] = (df_metric1['metric1'].fillna(0) * capacity).astype(int)
    df_metric1['metric1'] = df_metric1[['residents','metric1']].min(axis=1)
    df_metric1['metric1'] = df_metric1['metric1'].fillna(0).astype(int)

    # metric 2 number of students in each building with no access to schools
    metric2_index = df_students['ds'] > thresholds['metric2']
    if 'power' in infra:
        metric2_index = (metric2_index) | (df_students['has_power'] == False)
    if 'road' in infra:
        metric2_index = (metric2_index) | (df_students['facility_access'] == False)
    df_students_per_building = df_students[metric2_index][['individ','hhid','ds']].merge(
        df_household[['hhid','bldid']],on='hhid',how='left').groupby(
            'bldid',as_index=False).agg({'individ':'count'})

    df_metric2 = bld_hazard.merge(df_students_per_building,how='left',left_on='bldid',right_on = 'bldid')[['bldid','residents','individ']]
    df_metric2.rename(columns={'individ':'metric2'}, inplace=True)
    df_metric2['metric2'] = (df_metric2['metric2'].fillna(0) * capacity).astype(int)
    df_metric2['metric2'] = df_metric2[['residents','metric2']].min(axis=1)
    df_metric2['metric2'] = df_metric2['metric2'].fillna(0).astype(int)

    # metric 3 number of households in each building with no access to hospitals
    metric3_index = df_hospitals['ds'] > thresholds['metric3']
    if 'road' in infra:
        metric3_index = (metric3_index) | (df_hospitals['hospital_access'] == False)
    if 'power' in infra:
        metric3_index = (metric3_index) | (df_hospitals['hospital_has_power'] == False)
    df_hospitals_per_household = df_hospitals[metric3_index].groupby(
        'bldid',as_index=False).agg({'hhid':'count'})

    df_metric3 = bld_hazard.merge(df_hospitals_per_household,how='left',left_on='bldid',right_on='bldid')[['bldid','nhouse','hhid']]
    df_metric3.rename(columns={'hhid':'metric3'}, inplace=True)
    df_metric3['metric3'] = (df_metric3['metric3'].fillna(0) * capacity).astype(int)
    df_metric3['metric3'] = df_metric3[['nhouse','metric3']].min(axis=1)
    df_metric3['metric3'] = df_metric3['metric3'].fillna(0).astype(int)

    # metric 4 number of individuals in each building with no access to hospitals
    metric4_index = df_hospitals['ds'] > thresholds['metric4']
    if 'road' in infra:
        metric4_index = (metric4_index) | (df_hospitals['hospital_access'] == False)
    if 'power' in infra:
        metric4_index = (metric4_index) | (df_hospitals['hospital_has_power'] == False)
    df_hospitals_per_individual = df_hospitals[metric4_index].groupby(
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
    metric7_index = (df_displaced_indiv['ds_household'] > thresholds['metric6']) |\
                    (df_displaced_indiv['ds_school'] > thresholds['metric2']) |\
                    (df_displaced_indiv['ds_workplace'] > thresholds['metric1']) |\
                    (df_displaced_indiv['ds_hospital'] > thresholds['metric4']) 
    if 'road' in infra:
        metric7_index = (metric7_index) | (df_displaced_indiv['hospital_access'] == False)
        metric7_index = (metric7_index) | (df_displaced_indiv['facility_access'] == False)
    if 'power' in infra:
        metric7_index = (metric7_index) | (df_displaced_indiv['hospital_has_power'] == False)
        metric7_index = (metric7_index) | (df_displaced_indiv['workplace_power'] == False)
        metric7_index = (metric7_index) | (df_displaced_indiv['school_power'] == False)
    df_disp_per_bld = df_displaced_indiv[metric7_index]\
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