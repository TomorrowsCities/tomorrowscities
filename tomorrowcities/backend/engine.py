import os
os.environ['USE_PYGEOS'] = '0'
import pandas as pd
import geopandas as gpd
import numpy as np
from scipy.stats import norm
from scipy.interpolate import interp1d
import networkx as nx 

import time
import sys
import uuid
import os.path
import random
from random import sample
from numpy.random import multinomial, randint
from math import ceil
import math
from itertools import repeat, chain
from .utils import ParameterFile

def compute_road_infra(buildings, household, individual,
                        nodes, edges, intensity, fragility, hazard, 
                        road_water_height_threshold,
                        culvert_water_height_threshold,
                        threshold_flood_distance,
                        preserve_edge_directions,
                        earthquake_intensity_unit = 'm/s2',
                        ):

    earthquake_intensity_normalization_factor = 1
    if earthquake_intensity_unit == 'm/s2':
        earthquake_intensity_normalization_factor = 9.81

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

    # If the directions are not important, convert to undirected graph 
    if not preserve_edge_directions:
        G = nx.Graph(G)

    gdf_buildings = gdf_buildings.drop(columns=['node_id'])
    gdf_buildings = gpd.sjoin_nearest(gdf_buildings,gdf_nodes, 
                how='left', rsuffix='road_node',distance_col='road_node_distance')

    if hazard in ['flood', 'debris','landslide']:
        gdf_edges = gpd.sjoin_nearest(gdf_edges, gdf_intensity, how='left',
                                          rsuffix='intensity',distance_col='distance')
        gdf_edges = gdf_edges.drop_duplicates(subset=['edge_id'], keep='first')
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
            non_bridges = gdf_edges['bridge_type'].isna()
            culverts = gdf_edges['bridge_type'] == "culvert"
            flooded_roads = (non_bridges) & (gdf_edges['im'] > road_water_height_threshold)
            flooded_culverts = (culverts) & (gdf_edges['im'] > culvert_water_height_threshold)

            gdf_edges.loc[flooded_roads, 'ds'] = 1
            gdf_edges.loc[flooded_roads, 'is_damaged'] = True

            gdf_edges.loc[flooded_culverts, 'ds'] = 1
            gdf_edges.loc[flooded_culverts, 'is_damaged'] = True
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

        #gdf_edges['log_im'] = np.log(gdf_edges['im'])
        if 'im' in gdf_edges.columns:
            gdf_edges['log_im'] = np.log(gdf_edges['im']/earthquake_intensity_normalization_factor)
        elif 'pga' in gdf_edges.columns:
            gdf_edges['log_im'] = np.log(gdf_edges['pga']/earthquake_intensity_normalization_factor)
        
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

    # For each node which at least one hospital assigned to
    for hospital_node in hospital_nodes:
        # every node that can reach to hospital_node
        for node_with_hospital_access in nx.ancestors(G_dmg, hospital_node) | {hospital_node}:
            # find the buildings associated with node_with_hospital_access
            idx = gdf_buildings['node_id'] == node_with_hospital_access
            # these buildings have access to hospital_node
            gdf_buildings.loc[idx, 'hospital_access'] = True

            # for each hospital connected to hospital_node
            for hospital_bld in gdf_buildings[(gdf_buildings['node_id'] == hospital_node) & (gdf_buildings['occupancy'] == 'Hea')]['bldid']:
                # find the households satisfying:
                #  - if the hospital is the household's community hospital
                #  - and household's building is reachable from that hospital
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
    # If graph is directed, shortest path calculation obeys the directions
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
                        threshold_flood, threshold_flood_distance, preserve_edge_directions,
                        earthquake_intensity_unit = 'm/s2',
                        ):
    earthquake_intensity_normalization_factor = 1
    if earthquake_intensity_unit == 'm/s2':
        earthquake_intensity_normalization_factor = 9.81
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

    G_power = nx.DiGraph()
    for _, node in gdf_nodes.iterrows():
        G_power.add_node(node.node_id, pos=(node.geometry.x, node.geometry.y))
        
    for _, edge in edges.iterrows():
        G_power.add_edge(*(edge.from_node, edge.to_node))  
    
    # If the directions are not important, convert to undirected graph 
    if not preserve_edge_directions:
        G_power = nx.Graph(G_power)

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
        
        if 'im' in gdf_nodes.columns:
            gdf_nodes['logim'] = np.log(gdf_nodes['im']/earthquake_intensity_normalization_factor)
        elif 'pga' in gdf_nodes.columns:
            gdf_nodes['logim'] = np.log(gdf_nodes['pga']/earthquake_intensity_normalization_factor)
        else:
            print('not supposed to happen')

    
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
        xnew = gdf_nodes['im'].to_numpy(dtype=np.float64)
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
    
    print(gdf_buildings.loc[0,:])
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
            threshold_flood = 0.2, threshold_flood_distance = 10,
            earthquake_intensity_unit = 'm/s2',
            ):

    earthquake_intensity_normalization_factor = 1
    if earthquake_intensity_unit == 'm/s2':
        earthquake_intensity_normalization_factor = 9.81

    gem_fragility = True if isinstance(df_hazard, dict) else False
    print('gem_fragility mode', gem_fragility)
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
    if not gem_fragility:
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
        gdf_building_collapse_prob['casualty'] = gdf_building_collapse_prob['residents']
        collapsed_idx = (gdf_building_collapse_prob['rnd'] < gdf_building_collapse_prob['collapse_probability']) 
        gdf_building_collapse_prob.loc[collapsed_idx, 'ds'] = DS_COLLAPSED
        gdf_building_collapse_prob.loc[~collapsed_idx, 'casualty'] = 0
        bld_hazard = gdf_building_collapse_prob[['bldid','ds','casualty']]
        return bld_hazard

    # TODO: Check if the logic makes sense
    if hazard_type == HAZARD_FLOOD:
        away_from_flood = gdf_building_intensity['distance'] > threshold_flood_distance
        print('threshold_flood_distance',threshold_flood_distance)
        print('number of distant buildings', len(gdf_building_intensity.loc[away_from_flood, 'im']))
        gdf_building_intensity.loc[away_from_flood, 'im'] = 0
        print('maximum water depth on buildings ',gdf_building_intensity['im'].max())

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
        if not gem_fragility:
            bld_eq = gdf_building_intensity.merge(df_hazard, left_on='vulnstreq',right_on='expstr', how='left')
            nulls = bld_eq['muds1_g'].isna()
            print('no correspnding record in exposure', pd.unique(bld_eq.loc[nulls, 'vulnstreq']))
            bld_eq.loc[nulls, ['muds1_g','muds2_g','muds3_g','muds4_g']] = [0.048,0.203,0.313,0.314]
            bld_eq.loc[nulls, ['sigmads1','sigmads2','sigmads3','sigmads4']] = [0.301,0.276,0.252,0.253]

            # Intensity measure calculation
            sa_list = np.array([float(x.split()[-1]) for x in bld_eq.columns if x.startswith('sa ')])
            sa_cols = [x for x in bld_eq.columns  if x.startswith('sa ') or x == 'pga']
            # Means single-channel earthquake density map
            if len(sa_list) == 0:
                if 'im' in bld_eq.columns:
                    bld_eq['logim'] = np.log(bld_eq['im']/earthquake_intensity_normalization_factor)
                elif 'pga' in bld_eq.columns:
                    bld_eq['logim'] = np.log(bld_eq['pga']/earthquake_intensity_normalization_factor)
                else:
                    raise ValueError('No intensity measure found')
            else:
                # Multi-channel density map
                for i, row in bld_eq.iterrows():
                    minp, maxp = row['minperiod'], row['maxperiod']
                    if minp > 0 and maxp > 0 and maxp > minp:
                        # 0.001 corresponds to pga
                        x_interp = np.log(np.concatenate(([0.001],sa_list)))
                        y_interp = np.log(row[sa_cols].to_numpy(dtype=np.float32))
                        step = 0.01
                        x_required = np.log(np.linspace(minp, maxp, int((maxp - minp) / step + 1)))
                        sa_interp = np.exp(np.interp(x_required, x_interp, y_interp))
                        sa_gmean = np.prod(sa_interp)**(1/len(sa_interp))
                        bld_eq.at[i,'logim'] = np.log(sa_gmean/earthquake_intensity_normalization_factor)
                    else:
                        bld_eq.at[i,'logim'] = np.log(row['pga']/earthquake_intensity_normalization_factor)

            for m in ['muds1_g','muds2_g','muds3_g','muds4_g']:
                # TODO: double check if we should apply g-normalization
                bld_eq[m] = np.log(bld_eq[m])

            for i in [1,2,3,4]:
                bld_eq[f'prob_ds{i}'] = norm.cdf(bld_eq['logim'],bld_eq[f'muds{i}_g'],bld_eq[f'sigmads{i}'])


        else:
            gem_df = pd.DataFrame(df_hazard['fragilityFunctions'])
            gem_df['imt_2'] = gem_df['imt'].str.replace('(', ' ').str.replace(')','').str.lower()
            gem_df['imt_2'] = gem_df['imt_2'].apply(lambda x: f'sa {float(x.split()[-1]):.2f}' if x.startswith('sa ') else x)
            bld_eq = gdf_building_intensity.merge(gem_df, how='left',left_on='expstr', right_on='id', validate="many_to_one")

            def computer_damage_state(row):
                intensity_in_g = row[row['imt_2']] / earthquake_intensity_normalization_factor
                prob_ds1 = np.interp(intensity_in_g, row['imls'], row['slight'])
                prob_ds2 = np.interp(intensity_in_g, row['imls'], row['moderate'])
                prob_ds3 = np.interp(intensity_in_g, row['imls'], row['extensive'])
                prob_ds4 = np.interp(intensity_in_g, row['imls'], row['complete'])
                return prob_ds1, prob_ds2, prob_ds3, prob_ds4
            bld_eq[['prob_ds1','prob_ds2','prob_ds3','prob_ds4']] = bld_eq.apply(computer_damage_state, axis=1,result_type='expand')

        bld_eq[['prob_ds0','prob_ds5']] = [1,0]
        for i in [1,2,3,4,5]:
            bld_eq[f'ds_{i}'] = np.abs(bld_eq[f'prob_ds{i-1}'] - bld_eq[f'prob_ds{i}'])
        df_ds = bld_eq[['ds_1','ds_2','ds_3','ds_4','ds_5']]
        bld_eq['eq_ds'] = df_ds.idxmax(axis='columns').str.extract(r'ds_([0-9]+)').astype('int') - 1
        casualty_rates = np.array([0, 0.05, 0.28, 1.152, 74.41]) # percent
        bld_eq['casualy'] = 0
        bld_eq = bld_eq.assign(casualty=lambda x: casualty_rates[x['eq_ds']] * x['residents'] / 100)
        bld_eq['casualty'] = bld_eq['casualty'].astype(int) 
        # Create a simplified building-hazard relation
        bld_hazard = bld_eq[['bldid','eq_ds','casualty']]
        bld_hazard = bld_hazard.rename(columns={'eq_ds':'ds'})

        ds_str = {0: 'No Damage',1:'Low',2:'Medium',3:'High',4:'Collapsed'}

    elif hazard_type == HAZARD_FLOOD:
        bld_flood = gdf_building_intensity.merge(df_hazard, on='expstr', how='left')
        x = np.array([0,0.5,1,1.5,2,3,4,5,6])
        y = bld_flood[['hw0','hw0_5','hw1','hw1_5','hw2','hw3','hw4','hw5','hw6']].to_numpy()
        xnew = bld_flood['im'].to_numpy(dtype=np.float64)
        flood_mapping = interp1d(x,y,axis=1,kind='linear',bounds_error=False, fill_value=(0,1))
        # TODO: find another way for vectorized interpolate
        bld_flood['fl_prob'] = np.diag(flood_mapping(xnew))
        bld_flood['fl_ds'] = 0
        flooded_buildings = bld_flood['fl_prob'] > threshold_flood
        bld_flood.loc[flooded_buildings, 'fl_ds'] = 1

        casualty_rates = np.array([[0,0,0,0.000976715,0.0105355,0.052184493,0.160744982,0.373769339,0.743830881]])
        y_casualty = np.repeat(casualty_rates, len(bld_flood),axis=0)
        casualty_mapping = interp1d(x,y_casualty,axis=1,kind='linear',bounds_error=False, fill_value=(0,1))
        # TODO: find another way for vectorized interpolate
        bld_flood['casualty_prob'] = np.diag(casualty_mapping(xnew))
        bld_flood['casualty_rates'] = bld_flood['casualty_prob'] * bld_flood['residents']
        bld_flood['casualty'] = 0
        bld_flood.loc[flooded_buildings, 'casualty'] = bld_flood.loc[flooded_buildings, 'casualty_rates']
        bld_flood['casualty'] = bld_flood['casualty'].astype(int)


        # Create a simplified building-hazard relation
        bld_hazard = bld_flood[['bldid','fl_ds','casualty']]
        bld_hazard = bld_hazard.rename(columns={'fl_ds':'ds'})

        ds_str = {0: 'No Damage',1:'Flooded'}
    
    return bld_hazard

def create_tally(l, b, h, i):
    '''Create a tally dataframe from exposure'''

    tally = i.merge(h, how='left',left_on='hhid', right_on='hhid', validate='many_to_one')\
         .merge(b, how='left', left_on='bldid', right_on='bldid', validate='many_to_one', suffixes=(None,"_building"))\
         .merge(l.drop(columns='geometry'), how='left', left_on='zoneid', right_on='zoneid', validate='many_to_one')\
         .merge(b[['bldid','occupancy','ds','has_power']]\
                .rename(columns={'occupancy':'occupancy_facility','ds':'ds_facility','has_power':'has_power_facility'}),
                how='left',left_on='indivfacid', right_on='bldid',validate='many_to_one',suffixes=(None,'_facility'))\
         .merge(b[['bldid','ds']]\
                .rename(columns={'ds':'ds_hospital'}),
                how='left',left_on='commfacid', right_on='bldid',validate='many_to_one',suffixes=(None,'_hospital'))

    tally = tally.rename(columns={'casualty': 'casualty_in_building'})
    tally['casualty'] = 0

    #tally.to_excel('/tmp/tally.xlsx')
    building_level_casualties = tally[tally['casualty_in_building'] > 0][['bldid','casualty_in_building']].drop_duplicates()
    for (row, bldid, casualty_in_building) in building_level_casualties.itertuples(name=None):
        individuals_in_building = tally[tally['bldid'] == bldid]['individ']
        selected_individuals = individuals_in_building.sample(casualty_in_building)
        tally.loc[selected_individuals.index, 'casualty'] = 1

    tally['has_facility'] = tally['indivfacid'].apply(lambda x: x > -1)
    tally['lost_facility_access'] = tally.apply(lambda x: x['has_facility'] and not x['facility_access'], axis=1)

    tally_geo = gpd.GeoDataFrame(tally, geometry="geometry")

    return tally, tally_geo


def generate_metrics(t, t_full, hazard_type, population_displacement_consensus):
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



    # find the workers
    is_worker = \
        ( # there must be an associated facility
            t['bldid_facility'] > -1
        ) & \
        ( # associated facility must be a workplace
            (t['occupancy_facility'] == 'Com')    | \
            (t['occupancy_facility'] == 'ResCom') | \
            (t['occupancy_facility'] == 'Ind')
        )

    is_unemployed = \
        ( # must be a worker
            is_worker
        ) & \
        ( # workplace must be damaged or lost power or inaccessible
            (t['ds_facility'] > thresholds['metric1']) | \
            (t['has_power_facility'] == False) | \
            (t['facility_access'] == False)
        )

    # find the students
    is_student = \
        ( # there must be an associated facility
            t['bldid_facility'] > -1
        ) & \
        ( # associated facility must be an educational inst.
            t['occupancy_facility'] == 'Edu'
        )

    lost_school = \
        ( # must be a student
            is_student
        ) & \
        ( # school must be damaged or lost power or inaccessible
            (t['ds_facility'] > thresholds['metric2']) | \
            (t['has_power_facility'] == False) | \
            (t['facility_access'] == False)
        )

    # i individual associated with a hospital?
    has_hospital = \
        ( # there must be a association
            t['commfacid'] > -1
        ) & \
        ( # associated building id must be legit
            t['bldid_hospital'] > -1
        )

    household_lost_hospital = \
        (
            has_hospital
        ) & \
        (
            (t['ds_hospital'] > thresholds['metric3']) | \
            (t['hospital_has_power'] == False) | \
            (t['hospital_access'] == False) 
        )

    lost_hospital = \
        (
            has_hospital
        ) & \
        (
            (t['ds_hospital'] > thresholds['metric4']) | \
            (t['hospital_has_power'] == False) | \
            (t['hospital_access'] == False) 
        )

    lost_household = \
        (
            t['ds'] > thresholds['metric5']
        )

    is_homeless = \
        (
            t['ds'] > thresholds['metric6']
        )

    is_displaced = \
        (
            (t[['ds','ds_facility','ds_hospital']] \
                > [thresholds['metric6'], thresholds['metric1'], thresholds['metric4']]).sum(axis=1) \
                >= population_displacement_consensus
        ) | \
        (
            (t[['hospital_access','lost_facility_access']] \
                == [False, True]).sum(axis=1) \
                >= population_displacement_consensus  
        ) | \
        (
            (t[['has_power','hospital_has_power','has_power_facility']] \
                == [False, False, False]).sum(axis=1) \
                >= population_displacement_consensus  
        )

    is_casualty = \
        (
            t['casualty'] == 1
        )

    for j in range(1,10):
        t[f'metric{j}'] = 0

    metric1 = len(t[is_unemployed])
    metric2 = len(t[lost_school])
    metric3 = len(t[household_lost_hospital]['hhid'].unique())
    metric4 = len(t[lost_hospital])
    metric5 = len(t[lost_household]['hhid'].unique())
    metric6 = len(t[is_homeless])
    metric7 = len(t[is_displaced])
    metric8 = len(t[is_casualty])


    # I also need to find all workers and students to calculate
    # max_value
    # find the workers
    is_worker_in_full = \
        ( # there must be an associated facility
            t_full['bldid_facility'] > -1
        ) & \
        ( # associated facility must be a workplace
            (t_full['occupancy_facility'] == 'Com')    | \
            (t_full['occupancy_facility'] == 'ResCom') | \
            (t_full['occupancy_facility'] == 'Ind')
        ) 
    
    # find the students
    is_student_in_full = \
        ( # there must be an associated facility
            t_full['bldid_facility'] > -1
        ) & \
        ( # associated facility must be an educational inst.
            t_full['occupancy_facility'] == 'Edu'
        ) 
    
    # Max values are based on full tally table
    number_of_workers = len(t_full[is_worker_in_full])
    number_of_students = len(t_full[is_student_in_full])
    number_of_individuals = len(t_full)
    number_of_households = len(t_full['hhid'].unique())

    new_metrics = {"metric1": {"desc": "Number of workers unemployed", "value": metric1, "max_value": number_of_workers},
                "metric2": {"desc": "Number of children with no access to education", "value": metric2, "max_value": number_of_students},
                "metric3": {"desc": "Number of households with no access to hospital", "value": metric3, "max_value": number_of_households},
                "metric4": {"desc": "Number of individuals with no access to hospital", "value": metric4, "max_value": number_of_individuals},
                "metric5": {"desc": "Number of households displaced", "value": metric5, "max_value": number_of_households},
                "metric6": {"desc": "Number of homeless individuals", "value": metric6, "max_value": number_of_individuals},
                "metric7": {"desc": "Population displacement", "value": metric7, "max_value": number_of_individuals},
                "metric8": {"desc": "Number of casualties", "value": metric8, "max_value": number_of_individuals},
                }

    return new_metrics

def calculate_metrics(gdf_buildings, df_household, df_individual, infra, hazard_type, population_displacement_consensus, policies=[],capacity=1.0):
    # Very handy temporary attributes showin if an individual is associated with a facility 
    # and lost access to facility
    df_individual['has_facility'] = df_individual['indivfacid'].apply(lambda x: x > -1)
    df_individual['lost_facility_access'] = df_individual.apply(lambda x: x['has_facility']  and not x['facility_access'], axis=1)

    # only use necessary columns
    bld_hazard = gdf_buildings[['bldid','ds','expstr','occupancy','storeys',
                                'code_level','material','nhouse','residents','hospital_access','has_power','casualty']]

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
        .merge(df_household[['hhid','bldid','has_power']].rename(columns={'has_power':'household_power'}),on='hhid',how='left')

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
        for m in [2,3,4,5,7,8]:
            thresholds[f'metric{m}'] += 1

    # metric 1 number of unemployed workers in each building
    metric1_index = df_workers['ds'] > thresholds['metric1']
    if 'power' in infra:
        metric1_index = (metric1_index) | (df_workers['has_power'] == False)
    if 'road' in infra:
        metric1_index = (metric1_index) | (df_workers['lost_facility_access'] == True)
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
        metric2_index = (metric2_index) | (df_students['lost_facility_access'] == True)
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
    print('population_displacement_consensus', population_displacement_consensus)
    # direct damage
    metric7_index = (df_displaced_indiv[['ds_household','ds_school','ds_workplace','ds_hospital']] \
        > [thresholds['metric6'],thresholds['metric2'],thresholds['metric1'],thresholds['metric4']]).sum(axis=1) >= population_displacement_consensus
    # inaccebility
    if 'road' in infra:
        inaccesibility_index = (df_displaced_indiv[['hospital_access','lost_facility_access']] \
            == [False,True]).sum(axis=1) >= population_displacement_consensus
        metric7_index = (metric7_index) | (inaccesibility_index)
    # power loss
    if 'power' in infra:
        power_loss_index = (df_displaced_indiv[['household_power','hospital_has_power','workplace_power','school_power']] \
            == [False,False,False,False]).sum(axis=1) >= population_displacement_consensus
        metric7_index = (metric7_index) | (power_loss_index)
    df_disp_per_bld = df_displaced_indiv[metric7_index]\
                                            .groupby('bldid',as_index=False)\
                                            .agg({'individ':'count'})

    df_metric7 = bld_hazard.merge(df_disp_per_bld,how='left',left_on='bldid',right_on='bldid')[['bldid','residents','individ']]
    df_metric7.rename(columns={'individ':'metric7'}, inplace=True)
    df_metric7['metric7'] = (df_metric7['metric7'].fillna(0) * capacity).astype(int)
    df_metric7['metric7'] = df_metric7[['residents','metric7']].min(axis=1)
    df_metric7['metric7'] = df_metric7['metric7'].fillna(0).astype(int)

    df_metric8 = bld_hazard[['bldid','casualty']].copy().rename(columns={'casualty':'metric8'})

    df_metrics = {'metric1': df_metric1,
                'metric2': df_metric2,
                'metric3': df_metric3,
                'metric4': df_metric4,
                'metric5': df_metric5,
                'metric6': df_metric6,
                'metric7': df_metric7,
                'metric8': df_metric8}


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
                "metric7": {"desc": "Population displacement", "value": 0, "max_value": number_of_individuals},
                "metric8": {"desc": "Number of casualties", "value": 0, "max_value": number_of_individuals},}
    metrics["metric1"]["value"] = int(df_metric1['metric1'].sum())
    metrics["metric2"]["value"] = int(df_metric2['metric2'].sum())
    metrics["metric3"]["value"] = int(df_metric3['metric3'].sum())
    metrics["metric4"]["value"] = int(df_metric4['metric4'].sum())
    metrics["metric5"]["value"] = int(df_metric5['metric5'].sum())
    metrics["metric6"]["value"] = int(df_metric6['metric6'].sum())
    metrics["metric7"]["value"] = int(df_metric7['metric7'].sum())
    metrics["metric8"]["value"] = int(df_metric8['metric8'].sum())

    return metrics, df_metrics


def dist2vector(d_value, d_number,d_limit,shuffle_or_not):
    # d_value, d_number = vectors of same length (numpy array)
    # d_limit = single integer which indicates the sum of all values
    #           in d_number. 
    # shuffle_or_not = 'shuffle' will return a randomly shuffled list otherwise
    #     by default or with 'DoNotShuffle' the list will not be shuffled
    # Output: insert_vector is a list
    # get rid of extra dimensions if there is any
    # x: to be repeated array
    x = np.squeeze(d_value)
    # how many repetations per element
    w = np.squeeze(d_number)
    # total number of repetetions
    n = d_limit
    # rounding off float repetetations
    reps = np.round(w).astype('int32')
    # make sure sum of reps is still n after rounding
    reps[-1] = n - np.sum(reps[:-1])
    # Repet x[i] reps[i] times for all i
    y = np.repeat(x, reps)
    if shuffle_or_not == 'shuffle':
        random.shuffle(y)
    return [str(element) for element in y]

def generate_exposure(parameter_file: ParameterFile, land_use_file: gpd.GeoDataFrame, population_calculate=False, seed=42):
    # To re-generate a desired state comment above line and use: rng = int(seed_value_in_result)
    tic = time.time()
    print('1 -------', end=' ')
    random.seed(seed)
    np.random.seed(seed)
    df_nc, ipdf, df1, df2, df3 = parameter_file.get_sheets()


    # Convert both to the same target coordinate system
    landuse_shp = land_use_file.set_crs("EPSG:4326",allow_override=True)
    landuse_shp = landuse_shp.to_crs(f"EPSG:3857")

                    
    # Extract the nomenclature for load resisting system and land use types
    startmarker = '\['
    startidx = df_nc[df_nc.apply(lambda row: row.astype(str).str.contains(\
                    startmarker,case=False).any(), axis=1)]
        
    endmarker = '\]'
    endidx = df_nc[df_nc.apply(lambda row: row.astype(str).str.contains(\
                    endmarker,case=False).any(), axis=1)]
        
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
            
    # Income types is hardcoded
    avg_income_types =np.array(['lowIncomeA','lowIncomeB','midIncome','highIncome'])

    #Average dwelling area (sqm) wrt income type (44 for LI, 54 for MI, 
    #67 for HI in Tomorrovwille)
    #Range of footprint area fpt_area (sqm) wrt. income type (32-66 for LI,
    # 32-78 for MI and 70-132 for HI in Tomorrowville)                 
    average_dwelling_area = np.array([ipdf.iloc[13,2],ipdf.iloc[13,3],\
                                    ipdf.iloc[13,4],ipdf.iloc[13,5]])

    fpt_area = {'lowIncomeA':np.fromstring(ipdf.iloc[14,2],dtype=float,sep=','),
                'lowIncomeB':np.fromstring(ipdf.iloc[14,3],dtype=float,sep=','),
                'midIncome':np.fromstring(ipdf.iloc[14,4],dtype=float,sep=','),
                'highIncome':np.fromstring(ipdf.iloc[14,5],dtype=float,sep=',')}

    # Storey definition 1- Low rise (LR) 1-4, 2- Mid rise (MR) 5-8,
    # 3- High rise (HR) 9-19
    storey_range = {0:np.fromstring(ipdf.iloc[17,2],dtype=int,sep=','),
                    1:np.fromstring(ipdf.iloc[17,3],dtype=int,sep=','),
                    2:np.fromstring(ipdf.iloc[17,4],dtype=int,sep=',')}

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

    print(time.time() - tic)
    tic = time.time()
    print('2 ------',end=' ')
    #%% Read the landuse shapefile



    #Calculate area of landuse zones using polygons only if area is not already. 
    # First, convert coordinate system to cartesian
    if 'area' not in landuse_shp.columns:
        landuse_shp_cartesian = landuse_shp.copy()
        landuse_shp_cartesian = landuse_shp_cartesian.to_crs({'init': 'epsg:3857'})
        landuse_shp_cartesian['area']=landuse_shp_cartesian['geometry'].area # m^2
        landuse_shp_cartesian['area']=landuse_shp_cartesian['area']/10**4 # Hectares
        landuse_shp_cartesian = landuse_shp_cartesian.drop(columns=['geometry'])
        landuse = landuse_shp_cartesian.copy()
    else:
        landuse = landuse_shp.copy()
        landuse = landuse.drop(columns=['geometry'])
        
    # In the landuse shape file, if avgincome = lowIncome, replace it by lowIncomeA
    lowIncome_mask = landuse['avgincome'] == 'lowIncome'
    landuse.loc[lowIncome_mask,'avgincome'] = 'lowIncomeA'

    # Typecast the various fields in landuse shapefile
    landuse['population'] = landuse['population'].astype(int)
    landuse['densitycap'] = landuse['densitycap'].astype(float)
    landuse['area'] = landuse['area'].astype(float)
    landuse['zoneid'] = landuse['zoneid'].astype(int)
    landuse['floorarear'] = landuse['floorarear'].astype(float)
    landuse['setback'] = landuse['setback'].astype(float)



    #%% Read the landuse table (if xlsx file instead of shapefile is available)
    #landuse = pd.read_excel(os.path.join(ippath,ipfile_landuse),sheet_name=0)

    #%% Concatenate the dataframes and process the data
    tabledf = pd.concat([df1,df2,df3]).reset_index(drop=True)

    # Define a dictionary containing data distribution tables
    # Table names sorted according to the order in the excel input spreadsheet
    tables_temp = {
        't1':[],'t2':[],'t3':[],'t4':[],'t5':[],'t5a':[],'t6':[],'t9':[],
        't12':[],'t13':[],'t7':[],'t8':[],'t11':[],'t10':[],'t14':[]   
        }
    startmarker = '\['
    startidx = tabledf[tabledf.apply(lambda row: row.astype(str).str.contains(\
                    startmarker,case=False).any(), axis=1)]
        
    endmarker = '\]'
    endidx = tabledf[tabledf.apply(lambda row: row.astype(str).str.contains(\
                    endmarker,case=False).any(), axis=1)]
        
    count=0
    for key in tables_temp:
        #print(startidx.index[count], endidx.index[count])
        tablepart = tabledf.loc[list(range(startidx.index[count]+1,endidx.index[count]))]
        tablepart = tablepart.drop(columns =0 )
        tablepart = tablepart.dropna(axis=1).reset_index(drop=True).values.tolist()
        tables_temp[key].append(tablepart)
        count+=1

    tables = tables_temp

    print(time.time() - tic)
    tic = time.time()
    print('3 ------',end=' ')
    #%% Basic exception handling to check improper inputs in the spreadsheet
    input_error_flag = False
    input_error_flag_shp = False

    if numb_com ==0:
        print('The number of commercial buildings cannot be zero.')
        input_error_flag = True
    if numb_ind == 0:
        print('The number of industrial buildings cannot be zero.')
        input_error_flag = True
        
    if len(lutidx) != len(tables['t7'][0]) or len(lutidx) != len(tables['t8'][0])\
        or len(lutidx) != len(tables['t9'][0]) or len(lutidx) != len(tables['t11'][0]):
            print('The number of rows in Tables 7,8,9 and 11 must be equal to '\
                'the number of land use types (LUT) in Nomenclature sheet.\n')
            input_error_flag = True

    if len(lrsidx)!=len(tables['t7'][0][0]) or len(lrsidx)!=len(tables['t8'][0][0])\
        or len(lrsidx)!=len(tables['t11'][0][0]):
            print('The number of columns in Tables 7,8 and 11 must be equal to '\
                'the number of load resisting system (LRS) types in '\
                'Nomenclature sheet. \n')
            input_error_flag = True

    # Check if avgincome values are missing for fields in the nomenclature list
    for val in lut_types:
        avgInc_mask = landuse['luf'] == val
        incomeval4lut = landuse.loc[avgInc_mask,'avgincome']
        if incomeval4lut.isnull().values.any():
            print('avgincome field missing for ',val,'\n')
            input_error_flag_shp = True        
            
    if input_error_flag:
        print('Please correct the faulty inputs in the input spreadsheet.\n')
        sys.exit(1)
        
    if input_error_flag_shp:
        print('Please correct the faulty inputs in the input shapefile.\n')
        sys.exit(1)
        
        
    print(time.time() - tic)
    tic = time.time()
    print('3 ------',end=' ')

    #%% Note on definition of data layers
    # The household layer is initialized as Pandas dataframe in Step 2
    # The individual layer is initialized as Pandas dataframe in Step 5
    # The building layer is initialized as Pandas dataframe in Step 12
    # landuse_res_df (residential zone landuse subdataframe) is defined in step 11
    # landuse_ic_df (commercial/industrial) is also defined in step 11

    #%% Function definition: dist2vector

    print(time.time() - tic)
    tic = time.time()
    print('4 ------',end=' ')
    #%% The data generation process begins here____________________________________

    #%% Step 1: Calculate maximum population (nPeople)
    if population_calculate:
        landuse['population'] = landuse['population'].astype(int)
        # Subtracts existing population from projected population
        nPeople = round(landuse['densitycap']*landuse['area']-landuse['population'])
        nPeople[nPeople<0]=0
    else:
        landuse['population'] = landuse['population'].astype(int)
        nPeople = landuse['population']

    print(time.time() - tic)
    tic = time.time()
    print('5 ------',end=' ')
    #%% Step 2: Calculate the number of households (nhouse), hhid
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
    nhouse_all = round(nPeople/(sum(household_prop*t1_l1)))
    nhouse_all = nhouse_all.astype('int32')
    nhouse = nhouse_all[nhouse_all>0] # Exclude zones with zero households
    nhouseidx = nhouse.index
    #Preallocate a dataframe with nan to hold the household layer
    household_df = pd.DataFrame(np.nan, index = range(sum(nhouse)),
                                columns=['bldid','hhid','income','nind','commfacid',
                                        'income_numb','zonetype','zoneid',
                                        'approxFootprint'])
    #Calculate a list of cumulative sum of nhouse
    nhouse_cuml = np.cumsum(nhouse)

    #  Assign household id (hhid) 
    a = 0
    for i in nhouseidx:
        b =  nhouse_cuml[i]
        household_df.loc[range(a,b),'hhid'] = range(a+1,b+1) # First hhid index =1
        household_df.loc[range(a,b),'zoneid'] = landuse.loc[i,'zoneid']
        household_df.loc[range(a,b),'zonetype'] = landuse.loc[i,'avgincome']
        a = b

    del a,b
    household_df['hhid'] = household_df['hhid'].astype(int)

    print(time.time() - tic)
    tic = time.time()
    print('6 ------',end=' ')
    #%% Step 3: Identify the household size and assign "nInd" values to each household
    a_g = 0
    for i in nhouseidx:
        b_g = nhouse_cuml[i]
        # Find Total of every different nInd number for households
        household_num = nhouse[i] * household_prop
        # Round the household numbers for various numbers of individuals 
        # without exceeding total household number
        cumsum_household_num = np.round_(np.cumsum(household_num)).astype('int32')
        cumsum_household_num_diff = np.diff(cumsum_household_num)
        first_val = nhouse[i] - sum(cumsum_household_num_diff)
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
        
        household_df.loc[range(a_g,b_g), 'nind'] = insert_vector 
        a_g = b_g

    del a_g, b_g, count,insert_vector,subvector

    household_df['nind'] = household_df['nind'].astype(int)

    print(time.time() - tic)
    tic = time.time()
    print('7 ------',end=' ')
    #%% Step 4: Identify and assign income type of the households
    # Table 2 states the % of various income groups in different income zones
    # Convert Table 2 to numpy array
    # for row in range((len(tables['t2'][0]))):
    #     tables['t2'][0][row]=np.fromstring(tables['t2'][0][row],dtype=float,sep=',') 

    t2 = np.array(tables['t2'][0])

    count = 0

    for inc in avg_income_types:
        #Find indices corresponding to a zone type
        itidx = household_df['zonetype'] == inc
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
    print(time.time() - tic)
    tic = time.time()
    print('8 ------',end=' ')
    del count,insert_vector
        

    #%% Step 5: Identify and assign a unique ID for each  individual

    #Asumption 2: Gender distribution is same for different income types 

    #Preallocate a dataframe with nan to hold the individual layer
    nindiv = int(sum(household_df['nind'])) # Total number of individuals
    individual_df = pd.DataFrame(np.nan, index = range(nindiv),
                            columns=['hhid', 'individ', 'gender', 'age','head',
                                    'eduattstat','indivfacid_1','indivfacid_2',
                                    'indivfacid',
                                    'schoolenrollment','labourForce','employed'])
    individual_df.loc[range(nindiv),'individ'] = [range(1,nindiv+1)]
    individual_df['individ'].astype('int')
    print(time.time() - tic)
    tic = time.time()
    print('9 ------',end=' ')
    #%% Step 6: Identify and assign gender for each individual
    # Convert the gender distribution table 3 to numpy array
    tables['t3'][0] = np.array(tables['t3'][0][0],dtype=float) 
    female_p = tables['t3'][0][0]
    male_p = 1-female_p
    gender_value = np.array([1,2], dtype=int) # 1=Female, 2=Male
    gender_number = np.array([female_p, male_p])*nindiv

    d_limit = nindiv # Size of array to match after rounding off
    d_value = gender_value
    d_number = gender_number 

    insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
    individual_df.loc[range(nindiv),'gender'] = insert_vector
    individual_df['gender'] = individual_df['gender'].astype('int')

    #%% Step 7: Identify and assign age for each individual
    #Assumption 3: Age profile is same for different income types
    #Convert the age profile wrt gender distribution table 4 to numpy array
    ageprofile_value = np.array([1,2,3,4,5,6,7,8,9,10], dtype=int)
    t4_l1_f = np.array(tables['t4'][0][0], dtype=float) #For female
    t4_l2_m = np.array(tables['t4'][0][1], dtype=float) #For male
    t4 = np.array([t4_l1_f, t4_l2_m])

    for i in range(len(gender_value)):
        gidx = individual_df['gender'] == gender_value[i]    
        d_limit = sum(gidx)
        d_value = ageprofile_value
        d_number = t4[i]*sum(gidx)    
        insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
        individual_df.loc[gidx,'age'] = insert_vector

    individual_df['age'] = individual_df['age'].astype(int) 
    print(time.time() - tic)
    tic = time.time()
    print('10 ------',end=' ')
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
    t5_l1_f = np.array(tables['t5'][0][0], dtype=float) #For female
    t5_l2_m = np.array(tables['t5'][0][1], dtype=float) #For male
    t5 = np.array([t5_l1_f, t5_l2_m])

    for i in range(len(gender_value)):
        gidx = individual_df['gender'] == gender_value[i]    
        d_limit = sum(gidx)
        d_value = education_value
        d_number = t5[i]*sum(gidx)    
        insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle')
        individual_df.loc[gidx,'eduattstat'] = insert_vector

    individual_df['eduattstat'] = individual_df['eduattstat'].astype(int)

    print(time.time() - tic)
    tic = time.time()
    print('11 ------',end=' ')
    #%% Step 9: Identify and assign the head of household to corresponding hhid

    # Assumption 5: Head of household is dependent on gender
    # Assumption 6: Only (age>20) can be head of households
    #Convert the head of houseold distribution table 6 to numpy array
    tables['t6'][0] = np.array(tables['t6'][0][0],dtype=float) 
    female_hh = tables['t6'][0][0]
    male_hh = 1-female_hh

    # Calculate the number of household heads by gender
    hh_number= np.array([female_hh, male_hh])*sum(nhouse)
    hh_number= hh_number.astype(int)
    hh_number[0] = sum(nhouse) - hh_number[1]

    for i in range(len(gender_value)): #Assign female and male candidates
        gaidx= (individual_df['gender'] == gender_value[i]) & \
                (individual_df['age']>4) # '>4' denotes above age group '18-20'    
        #Index of household head candidates in individual_df
        hh_candidate_idx =  list(individual_df.loc[gaidx,'gender'].index)            
        # Take a random permutation sample to obtain household head indices from 
        # the index of possible household candidates in individual_df
        ga_hh_idx = random.sample(hh_candidate_idx, hh_number[i])                                         
        #print('gaidx=',sum(gaidx), 'ga_hh_idx', len(ga_hh_idx))
        
        individual_df.loc[ga_hh_idx,'head'] = 1
        


    # 1= household head, 2= household members other than the head    
    individual_df.loc[individual_df['head'] != 1,'head'] =0

    #Assign household ID (hhid) randomly
    hhid_temp = household_df['hhid'].tolist()
    random.shuffle(hhid_temp)
    individual_df.loc[individual_df['head'] == 1,'hhid'] = hhid_temp
    print(time.time() - tic)
    tic = time.time()
    print('12 ------',end=' ')
    #%% Step 10: Identify and assign the household that each individual belongs to
    # In relation with Assumption 6, no individuals under 20 years of age can live
    # alone in an household
    individual_df_temp = individual_df[individual_df['head']==0]
    individual_df_temp_idx = list(individual_df_temp.index)
    #hhidlist = household_df['hhid'].tolist()
    for i in range(1,len(t1_l1)): #Loop through household numbers >1
        hh_nind = t1_l1[i] # Number of individuals in households
        # Find hhid corresponding to household numbers
        hh_df_idx = household_df['nind']== hh_nind
        hhidx = household_df.loc[hh_df_idx,'hhid'].tolist()
        #Random shuffle hhidx here
        amph = hh_nind -1 # additional member per household
        for j in range(amph):
            # Randomly select len(hhidx) number of indices from individual_df_temp_idx
            idtidx = random.sample(individual_df_temp_idx, len(hhidx))
            individual_df.loc[idtidx,'hhid'] = hhidx
            #Remove idtidx before next iteration
            individual_df_temp = individual_df_temp.drop(index=idtidx)
            individual_df_temp_idx = list(individual_df_temp.index)
            
    individual_df['hhid'] = individual_df['hhid'].astype(int)

    print(time.time() - tic)
    tic = time.time()
    print('13 ------',end=' ')
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
    agemask = (individual_df['age'] == 2) | (individual_df['age']==3) 
    school_df = pd.DataFrame(np.nan, index = range(sum(agemask)),
                    columns=['individ','hhid','eduattstath','income','enrollment'])
    school_df_idx = individual_df.loc[agemask,'individ'].index
    school_df.set_index(school_df_idx, inplace=True)
    school_df['individ'] = individual_df.loc[agemask,'individ']
    school_df['hhid'] = individual_df.loc[agemask,'hhid']
    # Then, pick a slice of individual_df corresponding to the household a student
    # belongs to. From there, Pick eduAtt status of head of household. To expedite
    # computation, dataframe columns have been converted to list
    school_df_hhid_list = list(school_df['hhid'])
    temp_df = individual_df[individual_df['hhid'].isin(school_df_hhid_list)]
    head4school_df = temp_df[temp_df['head'] == 1]
    head4school_df_hhid_list = list(head4school_df['hhid'])
    head4school_df_edus_list = list(head4school_df['eduattstat'])
    school_df_edu_list = np.ones(len(school_df_hhid_list))*np.nan

    # Label 'lowIncomeA' and 'lowIncomeB' = 1, 'midIncome' =2, 'highIncome' =3
    household_df_hhid_list = list(household_df['hhid'])
    #Use .copy() to avoid SettingwithCopyWarning
    income4school_df=household_df[household_df['hhid'].\
                                isin(school_df_hhid_list)].copy()
    li_mask = (income4school_df['income'] == avg_income_types[0]) |\
            (income4school_df['income'] == avg_income_types[1]) 
    lm_mask = income4school_df['income'] == avg_income_types[2]
    lh_mask = income4school_df['income'] == avg_income_types[3]
    income4school_df.loc[li_mask,'income'] = 1
    income4school_df.loc[lm_mask,'income'] = 2
    income4school_df.loc[lh_mask,'income'] = 3
    income4school_df_income_list = list(income4school_df['income'])
    income4school_df_hhid_list = list(income4school_df['hhid'])
    school_df_income_list = np.ones(len(school_df_hhid_list))*np.nan

    # Faster way
    #school_df
    #head4school_df
    school_df_edu_list_df = school_df[['hhid']].merge(head4school_df[['hhid','eduattstat']], how='left', on='hhid')
    school_df_edu_list= list(school_df_edu_list_df['eduattstat'])
 
    school_df_income_list_df = school_df[['hhid']].merge(income4school_df[['hhid','income']], how='left', on='hhid')
    school_df_income_list= list(school_df_income_list_df['income'])

    #count=0
    # NOTE: If the operation inside this for loop can be replaced with indexing
    # operation the computation time for this code can be further reduced.
    #for hhid in school_df_hhid_list:
    #    #print('hhid',hhid, count, len(school_df_hhid_list))
    #    #assign education attained by head of household to school_df
    #    hhid_temp = [i for i, value in enumerate(head4school_df_hhid_list)\
    #                if value == hhid ]
    #    school_df_edu_list[count] = head4school_df_edus_list[hhid_temp[0]]
    #    #assign income type of household to school_df
    #    hhid_temp2 = [i for i, value in enumerate(income4school_df_hhid_list)\
    #                if value == hhid ]
    #    school_df_income_list[count] = income4school_df_income_list[hhid_temp2[0]]
    #    count+=1



    #print('original edu')
    #print(len(school_df_edu_list), school_df_edu_list[:10],school_df_edu_list[-10:])
    #print('original income')
    #print(len(school_df_income_list), school_df_income_list[:10],school_df_income_list[-10:])
        
    school_df.loc[school_df.index, 'eduattstath'] = school_df_edu_list 
    school_df['eduattstath'] = school_df['eduattstath'].astype(int)
    school_df['income'] = school_df_income_list
    school_df['income'] = school_df['income'].astype(int)

    print(time.time() - tic)
    tic = time.time()
    print('14 ------',end=' ')

    #assign school enrollment (1 = enrolled, 0 = not enrolled)
    for incomeclass in range(1,4): # Income class 1,2,3
        for head_eduattstat in range(1,6): # Education attainment category 1 to 5
            enrmask = (school_df['income'] == incomeclass) &\
                    (school_df['eduattstath'] == head_eduattstat)
            no_of_pstudents = sum(enrmask) # Number of potential students
            if no_of_pstudents ==0: #continue if no students exist for given case
                continue
            i,j = incomeclass-1, head_eduattstat-1 # indices to access table 5a
            d_limit = no_of_pstudents # Size of array to match after rounding off
            d_value = [1,0] #1= enrolled, 0 = not enrolled
            d_number = np.array([t5a[i,j], 1-t5a[i,j]])*no_of_pstudents        
            insert_vector = dist2vector(d_value, d_number,d_limit,'shuffle') 
            school_df.loc[enrmask,'enrollment'] = insert_vector
            
    school_df['enrollment']= school_df['enrollment'].astype(int)
    # Substitute the enrollment status back to individual_df dataframe
    individual_df.loc[school_df.index,'schoolenrollment']=  school_df['enrollment']   

    print(time.time() - tic)
    tic = time.time()
    print('15 ------',end=' ')
    #%% Step 11: Identify approximate total residential building area needed
    # (approxDwellingAreaNeeded_sqm) 
    # Assumption 7a on Average dwelling area (sqm) for different income types.

    # The output is stored in the column 'totalbldarea_res' in landuse_res_df,
    # which represents the total buildable area

    #Sub dataframe of landuse type containing only residential areas
    landuse_res_df = landuse.loc[nhouse.index].copy()
    landuse_res_df.loc[nhouse.index,'nhousehold'] = nhouse
    hh_temp_df = household_df.copy()

    for i in range(0,len(avg_income_types)):
        hh_temp_df['income'] = hh_temp_df['income'].replace(avg_income_types[i],\
                                                        average_dwelling_area[i])
    for index in landuse_res_df.index: # Loop through each residential zone
        zoneid = landuse_res_df['zoneid'][index]
        sum_part = hh_temp_df.loc[hh_temp_df['zoneid']==zoneid,'income'].sum()
        landuse_res_df.loc[index, 'approxDwellingAreaNeeded_sqm'] = sum_part
        
    # Zones where no households live i.e. potential commercial or industrial zones    
    noHH = nhouse_all[nhouse_all<=0].index
    landuse_ic_df = landuse.loc[noHH].copy()
    landuse_ic_df['area'] = landuse_ic_df['area']*10000 # Convert hectare to sq m
        

    print(time.time() - tic)
    tic = time.time()
    print('16 ------',end=' ')

    #%% Steps 12,13,14,15: 
    #    Identify number of residential buildings and generate building layer 

    # Table 7 contains Number of storeys distribution for various LRS and LUT
    # Table 11 contains code compliance distribution for various LRS and LUT
    t7= tables['t7'][0]
    t11 = tables['t11'][0]

    # Convert Table 8 to numpy array
    # Table8 contains LRS distribution with respect to various LUT
    for row in range((len(tables['t8'][0]))):
        tables['t8'][0][row]=np.array(tables['t8'][0][row],dtype=float) 
    t8 = np.array(tables['t8'][0]) # Table 8

    # Determine the number of buildings in each zone based on average income class 
    # building footprint range for each landuse zone and Tables 7 and 8
    no_of_resbldg = 0 # Total residential buildings in all zones
    footprint_base_sum = 0 # footprint at base, not multiplied by storeys
    footprint_base_L,storey_L,lrs_L,zoneid_L,codelevel_L = [],[],[],[],[]

    print(time.time() - tic)
    tic = time.time()
    print('17 ------',end=' ')
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
            t7dist = np.fromstring(t7row[lrsidx[lrs]],dtype=float, sep=',')
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
            t11dist = np.fromstring(t11row[lrsidx[lrs]],dtype=float, sep=',')
            lrs_pos = lrs_vector==lrs
            cc_number = multinomial(sum(lrs_pos),t11dist,size=1)
            cc_part = dist2vector(code_level, cc_number,sum(lrs_pos),'shuffle')
            cc_vector += cc_part
        random.shuffle(cc_vector)
        
        #If it is necessary to equalize number of storeys = number of households
        storey_vector_cs = np.cumsum(storey_vector)
        stmask = storey_vector_cs <= landuse_res_df.loc[i,'nhousehold']
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

    print(time.time() - tic)
    tic = time.time()
    print('18 ------',end=' ')
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
                            columns=['zoneid', 'bldid', 'specialfac', 'repvalue',
                                    'nhouse', 'residents', 'expstr','fptarea',
                                    'occbld','lrstype','codelevel',
                                    'nstoreys'])
    resbld_range = range(0,no_of_resbldg)
    #resbld_df.loc[resbld_range,'bldid'] = list(range(1,no_of_resbldg+1))
    resbld_df.loc[resbld_range,'zoneid'] = zoneid_L
    resbld_df['zoneid'] = resbld_df['zoneid'].astype('int')
    resbld_df.loc[resbld_range,'occbld'] = 'Res'
    resbld_df.loc[resbld_range,'specialfac'] = 0
    resbld_df.loc[resbld_range,'fptarea'] = footprint_base_L
    resbld_df.loc[resbld_range,'nstoreys'] = storey_L
    resbld_df.loc[resbld_range,'lrstype'] = lrs_L
    resbld_df.loc[resbld_range,'codelevel'] = codelevel_L
    print(time.time() - tic)
    tic = time.time()
    print('19 ------',end=' ')
    #%% Assign zoneids and building IDs for Res and ResCom
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
    available_zoneid = list(set(resbld_df['zoneid']))
    for zoneid in available_zoneid: #Loop through zones
        zonemask = resbld_df['zoneid'] == zoneid
        zone_idx = list(zonemask.index.values[zonemask])
        lutlrdidx=landuse_res_df[landuse_res_df['zoneid']==zoneid].index.values[0]
        #Occupancy type distribution for a zone
        occtypedist = t9[lutidx[ landuse_res_df['luf'][lutlrdidx]]]
        no_of_resbld = sum(zonemask) # Number of residential buildings in a zone
        # if mixed residential+commercial buildings as well as residential buildings exist
        if occtypedist[3] !=0 and occtypedist[0] !=0 : 
            # nrc = number of mixed res+com buildings in a zone
            nrc = int(occtypedist[3]/occtypedist[0]*no_of_resbld)
        elif occtypedist[3] !=0 and occtypedist[0] ==0:
            nrc = int(no_of_resbld)
        else: # if only residential buildings exist
            continue
        nrc_idx = sample(zone_idx,nrc)
        resbld_df.loc[nrc_idx,'occbld'] = 'ResCom'

    print(time.time() - tic)
    tic = time.time()
    print('20 ------',end=' ')
    #Assign building Ids for res and rescom buildings
    lenresbld = len(resbld_df)
    resbld_df.loc[range(0,lenresbld),'bldid'] = list(range(1,lenresbld+1))
    resbld_df['bldid'] = resbld_df['bldid'].astype('int')

    #%% STEP16: Identify and assign number of households and residents for each 
    #residential building
    #Assign nhouse, residents. All the households and residents must be assigned
    #to this layer.
    print(time.time() - tic)
    tic = time.time()
    print('20.2 ------',end=' ')
    dwellings_str=dist2vector(resbld_df['bldid'],np.array(storey_L),\
                                        np.sum(np.array(storey_L)),'DoNotShuffle')
    print(time.time() - tic)
    tic = time.time()
    print('20.3 ------',end=' ')
    dwellings = list(map(int,dwellings_str))
    #dwellings.sort()
    dwellings_selected = dwellings[0:len(household_df)]
    print(time.time() - tic)
    tic = time.time()
    print('20.4 ------',end=' ')
    random.shuffle(dwellings_selected)
    #Assign building IDs to all households
    household_df.loc[:,'bldid'] = dwellings_selected


    # Assign number of households and residents to residential buildings resbld_df
    # This loop must be optimized for speed

    print(time.time() - tic)
    tic = time.time()
    print('20.5 ------',end=' ')

    # Alternative
    # Drop the columns which I'll already generate in a second
    resbld_df = resbld_df.drop(columns=['nhouse','residents'])
    # Get nind information from household table
    resbld_w_household = resbld_df[['bldid']].merge(household_df[['bldid','hhid','nind']], how='inner', on='bldid')
    # Aggregate by bldid. nhouse: count of household, residents: number of individuals 
    resbld_w_household = resbld_w_household.groupby('bldid').agg({'hhid':'count','nind':'sum'}).reset_index().rename(columns={'hhid':'nhouse','nind':'residents'})
    # Merge nhouse and residents columns back into building table
    resbld_df = resbld_df.merge(resbld_w_household,how='inner',on='bldid')

    print(time.time() - tic)
    tic = time.time()
    print('21 ------',end=' ')
    # Remove rows in resbld_df which contains no residents
    
  

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
                            columns=['zoneid', 'bldid', 'specialfac', 'repvalue',
                                    'nhouse', 'residents', 'expstr','fptarea',
                                    'lut_number','occbld','lrstype','codelevel',
                                    'nstoreys'])

    t10= tables['t10'][0] # Extract Table 10
    a = 0
    for i in range(0,len(nci)): # First commercial, then industrial
        attr = t10[i]
        #Extract distributions for footprint, storeys, code compliance and LRS
        fpt_ic = np.fromstring(attr[0], dtype=float, sep=',')
        nstorey_ic = np.fromstring(attr[1], dtype=int, sep=',')
        codelevel_ic = np.fromstring(attr[2], dtype=float, sep=',')
        lrs_ic = np.fromstring(attr[3], dtype=float, sep=',')
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

    print(time.time() - tic)
    tic = time.time()
    print('22 ------',end=' ')
    # Assign number of households, Residents, special facility label
    range_all_ic = range(0,len(indcom_df))
    indcom_df.loc[range_all_ic,'nhouse'] = 0
    indcom_df.loc[range_all_ic,'residents'] = 0
    indcom_df.loc[range_all_ic,'specialfac'] = 0

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
        print("WARNING: Total population",nindiv,"is less than the user-specified "\
            "number of individuals per school",nsch_pi,". So, total school for "\
            "this population = 1 (by default) \n")
        nsch = 1

    if nhsp == 0:
        print("WARNING: Total population",nindiv,"is less than the user-specified "\
            "number of individuals per hospital",nhsp_pi,". So, total hospital for "\
            "this population = 1 (by default) \n ")
        nhsp = 1

    nsh = np.array([nsch,nhsp])
    nsh_cs = np.cumsum(nsh)
    occbld_label_sh = ['Edu','Hea']
    specialfac = [1,2] # Special facility label
    schhsp_df = pd.DataFrame(np.nan, index = range(0, nsch+nhsp),
                            columns=['zoneid', 'bldid', 'specialfac', 'repvalue',
                                    'nhouse', 'residents', 'expstr','fptarea',
                                    'lut_number','occbld','lrstype','codelevel',
                                    'nstoreys'])
    t14= tables['t14'][0] # Extract Table 14
    print(time.time() - tic)
    tic = time.time()
    print('23 ------',end=' ')
    a=0
    for i in range(0,len(t14)): # First school, then hospital
        attr_sh = t14[i]
        #Extract distributions for footprint, storeys, code compliance and LRS
        fpt_sh = np.fromstring(attr_sh[0], dtype=float, sep=',')
        nstorey_sh = np.fromstring(attr_sh[1], dtype=int, sep=',')
        codelevel_sh = np.fromstring(attr_sh[2], dtype=float, sep=',')
        lrs_sh = np.fromstring(attr_sh[3], dtype=float, sep=',')
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
        schhsp_df.loc[range_sh,'specialfac'] = specialfac[i]                 

    # Assign number of households, Residents, 
    range_all_sh = range(0,len(schhsp_df))
    schhsp_df.loc[range_all_sh,'nhouse'] = 0
    schhsp_df.loc[range_all_sh,'residents'] = 0

    print(time.time() - tic)
    tic = time.time()
    print('24 ------',end=' ')
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
            print('Warning: If population exists, but neither residential nor '\
                'residential+commercial buildings are allowed, there is '\
                'inconsistency between population and current row in table 9.'\
                'Therefore, it is assumed that total number of buildings in '\
                'zoneid', landuse_res_df.loc[i,'zoneid'],\
                '= no. of residential buildings in this zone.')
            print('Also, consider allowing residential and/or res+com building '\
                'to this zone in Table 9, if it is assigned population.\n')
        else:  
            Tb = Nrc/(otd[0]+otd[3]) # If either residential or res+com exist  

        #Calculate the number of industrial buildings using Table 9   
        if otd[1]>0:
            landuse_res_df.loc[i,'ind_weightage'] = ceil(Tb * otd[1])
            #landuse_res_df.loc[i,'no_of_ind_buildings'] = ceil(Tb * otd[1])
        else:
            # landuse_res_df.loc[i,'no_of_ind_buildings'] = 0
            landuse_res_df.loc[i,'ind_weightage'] = 0
            
        #Calculate the number of commercial buildings using Table 9     
        if otd[2]>0:
            landuse_res_df.loc[i,'com_weightage'] = ceil(Tb * otd[2])
            #landuse_res_df.loc[i,'no_of_com_buildings'] = ceil(Tb * otd[2])
        else:
            landuse_res_df.loc[i,'com_weightage'] = 0
            #landuse_res_df.loc[i,'no_of_com_buildings'] = 0

    print(time.time() - tic)
    tic = time.time()
    print('25 ------',end=' ')
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
        landuse_res_df['no_of_com_buildings'] = np.floor(ncom*com_wt/com_wt.sum())
    else:
        landuse_res_df['no_of_com_buildings'] = com_wt

    ind_wt = landuse_res_df['ind_weightage'].copy()   
    if ind_wt.sum() > nind:
        landuse_res_df['no_of_ind_buildings'] = np.floor(nind*ind_wt/ind_wt.sum())
    else:
        landuse_res_df['no_of_ind_buildings'] = ind_wt    

        
    landuse_res_df['no_of_ind_buildings'] =\
                        landuse_res_df['no_of_ind_buildings'].astype('int')
    landuse_res_df['no_of_com_buildings'] =\
                        landuse_res_df['no_of_com_buildings'].astype('int')
                        
    # Number and area of commercial buildings to be assigned    
    nCom_asgn = landuse_res_df['no_of_com_buildings'].sum()
    nCom_asgn_area = com_df.loc[range(0, nCom_asgn),'fptarea'].sum() 
    # Number and area of industrial buildings to be assigned
    nInd_asgn = landuse_res_df['no_of_ind_buildings'].sum()
    nInd_asgn_area = ind_df.loc[range(0,nInd_asgn),'fptarea'].sum()


    # Assign zoneid to industrial buildings (if any) in residential areas
    zoneid_r_i = dist2vector(list(landuse_res_df['zoneid']),\
                list(landuse_res_df['no_of_ind_buildings']),nInd_asgn,'shuffle')
    ind_df.loc[range(0,nInd_asgn),'zoneid'] = list(map(int,zoneid_r_i))

    # Assign zoneid to commercial buildings (if any) in residential areas
    zoneid_r_c = dist2vector(list(landuse_res_df['zoneid']),\
                list(landuse_res_df['no_of_com_buildings']),nCom_asgn,'shuffle')
    com_df.loc[range(0,nCom_asgn),'zoneid'] = list(map(int,zoneid_r_c))


    # Back-calculated number of commercial buildings per 1000 people        
    #nCom_asgn/(len(individual_df)/1000)

    # Case 2 For industrial/commercial buildings in non-residential areas__________

    # Number of industrial buildings that have not been assigned
    nInd_tba = int(len(ind_df) - nInd_asgn)
    # Number of commercial buildings that have not been assigned
    nCom_tba = int(len(com_df) - nCom_asgn)

    print(time.time() - tic)
    tic = time.time()
    print('26 ------',end=' ')
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
            landuse_ic_df.loc[i,'areaavailableforind']=\
                                            AC_ind/100*landuse_ic_df.loc[i,'area']
        else:
            landuse_ic_df.loc[i,'areaavailableforind']=0

        if otd[2]>0:
            landuse_ic_df.loc[i,'areaavailableforcom']=\
                                            AC_com/100*landuse_ic_df.loc[i,'area']
        else:
            landuse_ic_df.loc[i,'areaavailableforcom']=0
            
    print(time.time() - tic)
    tic = time.time()
    print('27 ------',end=' ')
    # Check how many of the generated com/ind buildings fit into the available area
    ind_fptarea_cs = list(np.cumsum(ind_df['fptarea']))
    com_fptarea_cs = list(np.cumsum(com_df['fptarea']))

    # Total areas available for commercial and industrial buildings in all zones
    At_c= landuse_ic_df['areaavailableforcom'].sum()
    At_i = landuse_ic_df['areaavailableforind'].sum()
    licidx = landuse_ic_df.index

    #Assign number of industrial buildings to industrial zones____
    # Unassigned area (c or i) = Total footprint (c or i) - area to be assigned(c or i) 
    unassigned_ind_area = ind_fptarea_cs[-1]-nInd_asgn_area # Total - assigned
    # if unassigned_ind_area <= At_i:
    #     landuse_ic_df.loc[licidx,'no_of_ind_buildings'] =\
    #         landuse_ic_df['areaavailableforind']/At_i*nInd_tba
    #     landuse_ic_df['no_of_ind_buildings'] =\
    #         landuse_ic_df['no_of_ind_buildings'].fillna(0)    
    #     landuse_ic_df['no_of_ind_buildings']=\
    #         landuse_ic_df['no_of_ind_buildings'].astype('int')
    # else:
    #     print('Required industrial buildings do not fit into available land area.')
    #     sys.exit(1)

    if unassigned_ind_area > At_i:
        # Need to truncate excess industrial buildings
        print('WARNING: Required industrial buildings do not fit into available '\
            'land area. So, excess industrial buildings have been removed.')
        ind_df_unassignedArea = np.cumsum(ind_df.loc[range(nInd_asgn,len(ind_df)),\
                                                    'fptarea'])
        ind_df_UAmask = ind_df_unassignedArea < At_i 
        nInd_tba = sum(ind_df_UAmask)

    landuse_ic_df.loc[licidx,'no_of_ind_buildings'] =\
        landuse_ic_df['areaavailableforind']/At_i*nInd_tba
    landuse_ic_df['no_of_ind_buildings'] =\
        landuse_ic_df['no_of_ind_buildings'].fillna(0)    
    landuse_ic_df['no_of_ind_buildings']=\
        landuse_ic_df['no_of_ind_buildings'].astype('int')

    #Assign number of commercial buildings to commercial zones____
    unassigned_com_area = com_fptarea_cs[-1]-nCom_asgn_area

    if unassigned_com_area > At_c:
        # Need to truncate excess commercial buildings
        print('WARNING: Required commercial buildings do not fit into available '\
            'land area. So, excess commerical buildings have been removed.')
        com_df_unassignedArea = np.cumsum(com_df.loc[range(nCom_asgn,len(com_df)),\
                                                    'fptarea'])
        com_df_UAmask = com_df_unassignedArea < At_c 
        nCom_tba = sum(com_df_UAmask)

    landuse_ic_df.loc[licidx,'no_of_com_buildings'] =\
        landuse_ic_df['areaavailableforcom']/At_c*nCom_tba
    landuse_ic_df['no_of_com_buildings'] =\
            landuse_ic_df['no_of_com_buildings'].fillna(0)  
    landuse_ic_df['no_of_com_buildings']=\
        landuse_ic_df['no_of_com_buildings'].astype('int')


    print(time.time() - tic)
    tic = time.time()
    print('28 ------',end=' ')
    # Begin assigning buildings to zones 
    # Assign zoneid to industrial buildings (if any) in industrial areas
    limit_zoneid_ic_i = landuse_ic_df['no_of_ind_buildings'].sum()
    zoneid_ic_i = dist2vector(list(landuse_ic_df['zoneid']),\
                list(landuse_ic_df['no_of_ind_buildings']),\
                limit_zoneid_ic_i,'shuffle')
    ind_df.loc[range(nInd_asgn,nInd_asgn+limit_zoneid_ic_i),'zoneid']=list(map(int,zoneid_ic_i))
    ind_df = ind_df[ind_df['zoneid'].notna()] #Remove unassigned buildings

    # Assign zoneid to commercial buildings (if any) in commercial areas
    limit_zoneid_ic_c = landuse_ic_df['no_of_com_buildings'].sum()
    zoneid_ic_c = dist2vector(list(landuse_ic_df['zoneid']),\
                list(landuse_ic_df['no_of_com_buildings']),\
                limit_zoneid_ic_c,'shuffle')
    com_df.loc[range(nCom_asgn,nCom_asgn+limit_zoneid_ic_c),'zoneid']=list(map(int,zoneid_ic_c))
    com_df = com_df[com_df['zoneid'].notna()] #Remove unassigned buildings


    print(time.time() - tic)
    tic = time.time()
    print('29 ------',end=' ')
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
    landuse['populationfinal'] = landuse['population']+landuse['populationAdded']
    landuse['populationfinal'] = landuse['populationfinal'].astype('int')

    #%% Assign zoneIds for schools and hospitals
    # Assign schools and hospitals to zones starting from the highest 
    # population until the number of schools and hospitals are reached
    landuse_sorted = landuse.sort_values(by=['populationfinal'],\
                                                    ascending=False).copy()
    landuse_sorted.reset_index(inplace=True, drop=True)
    #Remove zones without population
    no_popl_zones = landuse_sorted['populationfinal']==0
    landuse_sorted =landuse_sorted.drop(index=landuse_sorted.index[no_popl_zones])

    sch_df = schhsp_df[schhsp_df['occbld']=='Edu'].copy() #Educational institutions
    hsp_df = schhsp_df[schhsp_df['occbld']=='Hea'].copy() #Health institutions

    sch_df.reset_index(drop=True,inplace=True)
    hsp_df.reset_index(drop=True,inplace=True)

    # Assign zoneids for schools/educational institutions
    sch_range = range(0,len(sch_df))
    if len(sch_df) <= len(landuse_sorted):
        sch_df.loc[sch_range, 'zoneid'] = landuse_sorted.loc[sch_range,'zoneid']
    else:
        iterations_s = ceil(len(sch_df)/len(landuse_sorted))
        a1_s= list(repeat(landuse_sorted['zoneid'].tolist(),iterations_s))
        a_s = list(chain(*a1_s))
        sch_df.loc[sch_range, 'zoneid'] = a_s[0:len(sch_df)]
            
    # Assign zoneids for hospitals/health institutions
    hsp_range= range(0,len(hsp_df))
    if len(hsp_df) <= len(landuse_sorted):
        hsp_range = range(0,len(hsp_df))
        hsp_df.loc[hsp_range, 'zoneid'] = landuse_sorted.loc[hsp_range,'zoneid']
    else:
        iterations_h = ceil(len(hsp_df)/len(landuse_sorted))
        a1_h= list(repeat(landuse_sorted['zoneid'].tolist(),iterations_h))
        a_h = list(chain(*a1_h))
        hsp_df.loc[hsp_range, 'zoneid'] = a_h[0:len(hsp_df)]


    print(time.time() - tic)
    tic = time.time()
    print('30 ------',end=' ')
    #%% Concatenate the residential, industrial/commercial and special facilities
    # dataframes to obtain the complete building dataframe
    building_df=pd.concat([resbld_df,ind_df,com_df,sch_df,\
                            hsp_df]).reset_index(drop=True)
    #building_df=pd.concat([resbld_df,sch_df, hsp_df]).reset_index(drop=True)
    building_df['nstoreys'] = building_df['nstoreys'].astype(int)

    #Assign exposure string
    building_df['expstr'] = building_df['lrstype'].astype(str)+'+'+\
                            building_df['codelevel'].astype(str)+'+'+\
                            building_df['nstoreys'].astype(str)+'s'+'+'+\
                            building_df['occbld'].astype(str)
    # Assign building ids
    # lenbdf = len(building_df)
    # building_df.loc[range(0,lenbdf),'bldid'] = list(range(1,lenbdf+1))
    building_df.loc[range(len(resbld_df),len(building_df)),'bldid'] =\
                        list(range(len(resbld_df)+1,len(building_df)+1))
    building_df['bldid'] = building_df['bldid'].astype('int')

    #%% Step 21 Employment status of the individuals
    # Assumption 9: Only 20-65 years old individuals can work
    # Extract Tables 12 and 13
    t12 = np.array(tables['t12'][0][0],dtype=float) #[Female, Male]

    t13_f = np.array(tables['t13'][0][0],dtype=float) #Female
    t13_m = np.array(tables['t13'][0][1],dtype=float) #Male
    t13 = [t13_f,t13_m]

    # Identify individuals who can work
    working_females_mask = (individual_df['gender']==1) & \
                (individual_df['age']>=5) & (individual_df['age']<=9)
    working_males_mask = (individual_df['gender']==2) & \
                (individual_df['age']>=5) & (individual_df['age']<=9)
    potential_female_workers = individual_df.index[working_females_mask]
    potential_male_workers = individual_df.index[working_males_mask]
        
    # But according to Table 12, not all individuals who can work are employed,
    # so the labour force is less than 100%
    labourforce_female = sample(list(potential_female_workers),\
                                    int(t12[0]*len(potential_female_workers)))
    labourforce_male = sample(list(potential_male_workers),\
                                    int(t12[1]*len(potential_male_workers))) 
    # labourForce = 1 indicates that an individual is a part of labour force, but 
    # not necessarily employed.
    individual_df.loc[labourforce_female,'labourForce'] =1
    individual_df.loc[labourforce_male,'labourForce'] =1  

    print(time.time() - tic)
    tic = time.time()
    print('31 ------',end=' ')
    # According to Table 13, the employment probability for labourforce differs
    # based on educational attainment status   
    for epd_array in t13: #Employment probability distribution for female and male
        count = 0
        ind_employed_idx =[]
        for epd in epd_array: # EPD for various educational attainment status
            # Individuals in labour force that belong to current EPD
            eamask = (individual_df['eduattstat'] == education_value[count]) & \
                    (individual_df['labourForce']==1)
            nInd_in_epd = sum(eamask)
            if nInd_in_epd == 0:
                continue
            
            nInd_employed = int(epd*nInd_in_epd)
            if nInd_employed == 0:
                continue
            ind_ea_labourforce = list(individual_df.index[eamask])
            ind_employed_idx = sample(ind_ea_labourforce, nInd_employed)
            individual_df.loc[ind_employed_idx,'employed'] = 1
            
            #Check ouput epd (for debugging)
            #print(epd,':',len(ind_employed_idx)/len(ind_ea_labourforce))
            
            count+=1
            
    print(time.time() - tic)
    tic = time.time()
    print('32 ------',end=' ')
    #%% Step 22 Assign IndividualFacID
    # bld_ID of the building that the individual regularly visits 
    # (can be workplace, school, etc.)
    # Assumption 13: Each individual is working within the total study area extent.
    # Assumption 17: Each individual (within schooling age limits) goes to 
    #                school within the total study area extent.

    # indivfacid_1 denotes bldid of the schools
    # students (schoolenrollment=1) go to, whereas, indivfacid_2 denotes bldid of
    # com, ind and rescom buildings where working people go to (workplace bldid).

    # Assign working places to employed people in indivfacid_2_________________
    # Working places are defined as occupancy types 'Ind','Com' and 'ResCom'

    workplacemask=(building_df['occbld']=='Ind') | (building_df['occbld']=='Com')\
                    | (building_df['occbld'] == 'ResCom')
    workplaceidx = building_df.index[workplacemask]
    workplace_bldid = building_df['bldid'][workplaceidx].tolist()

    employedmask = individual_df['employed'] ==1
    employedidx = individual_df.index[employedmask]
    if len(employedidx)>len(workplaceidx):
        repetition = ceil(len(employedidx)/len(workplaceidx))
        workplace_sample_temp = list(repeat(workplace_bldid,repetition))
        workplace_sample = list(chain(*workplace_sample_temp))
    else:
        workplace_sample = workplace_bldid
    random.shuffle(workplace_sample)

    print(time.time() - tic)
    tic = time.time()
    print('33 ------',end=' ')

    individual_df.loc[employedidx,'indivfacid_2'] = \
                                workplace_sample[0:sum(employedmask)]

    individual_df.loc[employedidx,'indivfacid'] = \
                                workplace_sample[0:sum(employedmask)]                               

    # Assign school bldids to enrolled students in indivfacid_1________________
    schoolmask = building_df['occbld']=='Edu'            
    schoolidx = building_df.index[schoolmask]
    school_bldid = building_df['bldid'][schoolidx].tolist()

    studentmask = individual_df['schoolenrollment'] ==1
    studentidx = individual_df.index[studentmask]
    if len(studentidx)>len(schoolidx):
        repetition = ceil(len(studentidx)/len(schoolidx))
        school_sample_temp = list(repeat(school_bldid,repetition))
        school_sample = list(chain(*school_sample_temp))
    else:
        school_sample = school_bldid
    random.shuffle(school_sample)

    individual_df.loc[studentidx,'indivfacid_1'] = \
                                school_sample[0:sum(studentmask)]  
    individual_df.loc[studentidx,'indivfacid'] = \
                                school_sample[0:sum(studentmask)]                               

    # Replace missing values with -1 instead of NaN
    individual_df['indivfacid_1'] = individual_df['indivfacid_1'].fillna(-1)
    individual_df['indivfacid_2'] = individual_df['indivfacid_2'].fillna(-1) 
    individual_df['indivfacid'] = individual_df['indivfacid'].fillna(-1)  

    print(time.time() - tic)
    tic = time.time()
    print('34 ------',end=' ')
    #%% Step 23 Assign community facility ID (commfacid) to household layer
    # commfacid denotes the bldid of the hospital the households usually go to.

    # In this case, randomly assign bldid of hospitals to the households, but in 
    # next version, households must be assigned hospitals closest to their location
    hospitalmask = building_df['occbld']=='Hea'
    hospitalidx = building_df.index[hospitalmask]
    hospital_bldid = building_df['bldid'][hospitalidx].tolist()
    repetition = ceil(len(household_df)/len(hospitalidx))
    hospital_sample_temp = list(repeat(hospital_bldid,repetition))
    hospital_sample = list(chain(*hospital_sample_temp))
    random.shuffle(hospital_sample)

    household_df.loc[household_df.index,'commfacid'] =\
                                    hospital_sample[0:len(household_df)]

    print(time.time() - tic)
    tic = time.time()
    print('34.5 ------',end=' ')
    #%% Step 24 Assign repvalue
    # Assumption 12: Unit price for replacement wrt occupation type and 
    # special facility status of the building

    # Assign unit price
    for occtype in Unit_price:
        occmask = building_df['occbld'] == occtype
        occidx = building_df.index[occmask]
        building_df.loc[occidx, 'unit_price'] = Unit_price[occtype]
        
    building_df['repvalue'] = building_df['fptarea'] *\
                            building_df['nstoreys']* building_df['unit_price']


    print(time.time() - tic)
    tic = time.time()
    print('35 ------',end=' ')
    #%% Remove unnecessary columns and save the results 
    # building_df = building_df.drop(columns=\
    #          ['lut_number','lrstype','codelevel','nstoreys','occbld','unit_price'])
    building_df = building_df.drop(columns=['lut_number'])
    household_df = household_df.drop(columns=\
            ['income_numb','zonetype','zoneid','approxFootprint'])
    individual_df = individual_df.drop(columns=\
                        ['schoolenrollment','labourForce','employed'])
        
    # Rename indices to convert all header names to lowercase
    building_df.rename(columns={'zoneid':'zoneid','bldID':'bldid','expStr':'expstr',\
    'specialFac':'specialfac','repValue':'repvalue','nHouse':'nhouse'},\
                                                            inplace=True)
    household_df.rename(columns={'bldID':'bldid','hhID':'hhid','nIND':'nind',\
                                'CommFacID':'commfacid'}, inplace=True)
    individual_df.rename(columns={'hhID':'hhid','indivID':'individ',\
    'eduAttStat':'eduattstat','indivFacID_1':'indivfacid_1',\
    'indivFacID_2':'indivfacid_2'}, inplace=True)


    #%% Generate building centroid coordinates

    histo = building_df.groupby(['zoneid'])['zoneid'].count()
    max_val = building_df.groupby(['zoneid'])['fptarea'].max()
    landuse_layer = landuse_shp
    building_layer = building_df
    final_list = []
    skipped_buildings_count = 0
    for i in range(len(histo)):
        df = landuse_layer[landuse_layer['zoneid'] == histo.index[i]].copy()
        bui_indx = building_layer['zoneid'] == histo.index[i]
        bui_attr = building_layer.loc[bui_indx].copy()
        
        rot_a = random.randint(10, 40)
        rot_a_rad = rot_a*math.pi/180

        separation_val = math.sqrt(max_val.values[i])/abs(math.cos(rot_a_rad))
        separation_val = round(separation_val, 2)
        boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
        boundary_approach = round(boundary_approach, 2)
        
        df2 = df.buffer(-boundary_approach)    
        df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
        df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
        
        #Continue the loop if buffered dataframe df2 is empty -PR
        if df2.is_empty[df2.index[0]]:
            print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
            skipped_buildings_count +=\
                len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
            continue
        
        xmin, ymin, xmax, ymax = df2.total_bounds    
        xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
        ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
        
        pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
        points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
        grid = gpd.GeoSeries(points, crs=df.crs)
        grid.name = 'geometry'
        
        gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
        
        def buff(row):
            return row.geometry.buffer(row.buff_val, cap_style = 3)
        
        if len(gridinside) >= histo.values[i]:
            gridinside = gridinside.sample(min(len(gridinside), histo.values[i]))
            gridinside['xcoord'] = gridinside.geometry.x
            gridinside['ycoord'] = gridinside.geometry.y
            
            buffer_val = np.sqrt(list(bui_attr.fptarea))/2
            buffered = gridinside.copy()
            buffered['buff_val'] = buffer_val[0:len(gridinside)]
            
            if buffered.shape[0]==0: #PR
                print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                skipped_buildings_count +=\
                    len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                continue
            
            buffered['geometry'] = buffered.apply(buff, axis=1)
            polyinside = buffered.rotate(rot_a, origin='centroid')
            
            polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
            polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
            polyinside2['fid'] = list(range(1,len(polyinside2)+1))
            
            bui_attr['fid'] = list(range(1,len(bui_attr)+1))
            bui_joined = polyinside2.merge(bui_attr, on='fid')
            bui_joined = bui_joined.drop(columns=['fid'])
            
            bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
            bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))
            
        elif len(gridinside) < histo.values[i]:
            separation_val = math.sqrt(max_val.values[i])
            separation_val = round(separation_val, 2)
            boundary_approach =  (math.sqrt(max_val.values[i])/2)*math.sqrt(2)
            boundary_approach = round(boundary_approach, 2)
            
            df2 = df.buffer(-boundary_approach, 200)
            df2 = gpd.GeoDataFrame(gpd.GeoSeries(df2))
            df2 = df2.rename(columns={0:'geometry'}).set_geometry('geometry')
            
            xmin, ymin, xmax, ymax = df2.total_bounds    
            xcoords = [ii for ii in np.arange(xmin, xmax, separation_val)]
            ycoords = [ii for ii in np.arange(ymin, ymax, separation_val)]
            
            pointcoords = np.array(np.meshgrid(xcoords, ycoords)).T.reshape(-1, 2)
            points = gpd.points_from_xy(x=pointcoords[:,0], y=pointcoords[:,1])
            grid = gpd.GeoSeries(points, crs=df.crs)
            grid.name = 'geometry'
            
            gridinside = gpd.sjoin(gpd.GeoDataFrame(grid), df2[['geometry']], how="inner")
            
            gridinside = gridinside.sample(min(len(gridinside), histo.values[i]))
            gridinside['xcoord'] = gridinside.geometry.x
            gridinside['ycoord'] = gridinside.geometry.y
            
            buffer_val = np.sqrt(list(bui_attr.fptarea))/2
            buffered = gridinside.copy()
            buffered['buff_val'] = buffer_val[0:len(gridinside)]
            
            if buffered.shape[0]==0: #PR
                print('Dataframe index ', df.index[0], 'is empty after buffering.\n')
                skipped_buildings_count +=\
                    len(building_df.loc[building_df['zoneid'] == df.index[0],'zoneid'])
                continue
            
            buffered['geometry'] = buffered.apply(buff, axis=1)
            polyinside = buffered.rotate(0, origin='centroid')
            
            polyinside2 = gpd.GeoDataFrame(gpd.GeoSeries(polyinside))
            polyinside2 = polyinside2.rename(columns={0:'geometry'}).set_geometry('geometry')
            polyinside2['fid'] = list(range(1,len(polyinside2)+1))
            
            bui_attr['fid'] = list(range(1,len(bui_attr)+1))
            bui_joined = polyinside2.merge(bui_attr, on='fid')
            bui_joined = bui_joined.drop(columns=['fid'])
            
            bui_joined['xcoord'] = list(round(gridinside.geometry.x, 3))
            bui_joined['ycoord'] = list(round(gridinside.geometry.y, 3))

        final_list.append(bui_joined)

    final = pd.concat(final_list)
    print(time.time() - tic)
    tic = time.time()
    print('36 ------',end=' ')

    #print('\nTotal number of buildings generated:', len(building_layer))
    #print('Total number of coordinate pairs generated:', len(final), '\n')

    # Remove fields corresponding to unassigned buildings from all layers
    # The footprint generation part of this program may not be able to assign 
    # building footprint in some cases such as narrow strips or highly irregular
    # but small land areas. In this case, households and individuals 
    # corresponding to buildings without footprint coordinates must also be deleted.

    #Original dataframe which contains all generated buildings
    unique_building_df =  set(building_df['bldid'])
    #Building dataframe that contains only the building with footprints 
    unique_final = set(final['bldid'])
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

    final = final.to_crs("EPSG:4326")
    
    print(time.time() - tic)
    tic = time.time()
    print('37 ------',end=' ')
    print(time.time() - tic)
    return final, household_df, individual_df

