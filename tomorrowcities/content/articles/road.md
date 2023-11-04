---
author: huseyin.kaya
title: Road Networks
description: Earthquake and flood damage asssesment on road networks with bridges
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/bridge.jpg?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/bridge.jpg?raw=true
alt: "Data Formats"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Introduction
In this article, we are going to explain how to conduct
earthquake and flood damage assessment on road networks. 

## Quick Start
For the impatient readers, here is a quick road to conduct road network analysis.

* Download [Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing)
* Go to https://huggingface.co/spaces/hkayabilisim/app-engine/engine
* Go the [Engine](/engine)
* Drag and drop the following files inside sample dataset to the engine:
* rapti_road_edges.geojson
* rapti_road_nodes.geojson
* rapti_road_fragility.xlsx
* rapti_flood_max_depth_70yr_future_212mm_05.tif
* rapti_dummy_individual.json
* rapti_dummy_household.json
* rapti_dummy_buildings.geojson
* Unselect *Building*
* Select Road and Earthquake for infrastructure and hazard type, respectively.
* Click Calculate to run the engine.

When completed successfully:

* The damage state of the bridges will be shown in the *ds* attribute of the *road edges* layer.
* In the same layer, you will see the boolean *is_damaged* attribute.
* The roads in the *road edge* layer will also be colored red if *is_damaged* attribute is true.
* Every building will have a new attribute called *nearest_road_node* which determines the nearest junction point
of the transportation network. When you click the buildings, this information will be shown in details view.

## Data
From a computational point of perspective, a road transportation network is a bi-directional graph
whose edges correspond to roads or bridges whereas the nodes represent the junction points. 
In order to fully represent the network, computational platform requires two separate geo-spatial data frames
: nodes and edges. 

### Coordinate Reference System
In order to maintain portability, the platform expects the coordinates in WGS84 - World Geodetic System 1984 (EPSG:4326) which is the most used geographical coordinate system. A curious reader might wonder how WGS84 is used in distance calculations. We should note that, during the internal calculations, the engine transforms the coordinates to WGS 84 / Pseudo-Mercator (EPSG:3857) which is a cartesian coordinate system.

### Nodes
The nodes of the transportation network are defined in a geo-spatial data frame containing the coordinates 
of the nodes as well as their unique identification numbers. The id's can be any anything as long as 
they provide uniqueness of the nodes.


| |node_id	| geometry|
|-|---------|---------|
|0|3385919019|	POINT (82.61515 27.80731)|
|1|3385919022|	POINT (82.61096 27.80733)|
|2|3385919040|	POINT (82.60816 27.80784)|
|3|3385919056|	POINT (82.60709 27.80830)|
|4|3385919116|	POINT (82.69962 27.80961)|

### Edges
The edges are the line strings connecting the nodes. Every edge has a unique id denoted by *edge_id*. The nodes at the end points of an edge are denoted by *from_node* and *to_node* attributes. As the name suggests, the *length* attribute is the length of the edge. Although every a edge is a road, when it is a part of a bridge, this is denoted by boolean attribute *bridge*. The type of the bridge is specified by *bridge_type* to be used in flood and earthquake damage assessment. The geometry is any shape define the topology of the road. It can be a composition of dimensionless line strings. 


| |edge_id|	from_node|	to_node|	length|	bridge|	bridge_type|	geometry|
|-|-------|----------|---------|--------|-------|------------|----------|
|0|	0	|3385919019|	3762934344|	206.598	|False|	NaN|	LINESTRING (82.61515 27.80731, 82.61477 27.807...|
|1|	1	|3385919019|	3762934320|	954.306	|False|	NaN|	LINESTRING (82.61515 27.80731, 82.61585 27.807...|
|2|	2	|3385919019|	3762934257|	419.059	|False|	NaN|	LINESTRING (82.61515 27.80731, 82.61514 27.807...|
|3|	3	|3385919022|	3762934349|	26.608	|True	|Steel|	LINESTRING (82.61096 27.80733, 82.61082 27.807...|
|4|	4	|3385919022|	3762934344|	207.798	|False|	NaN	|LINESTRING (82.61096 27.80733, 82.61114 27.807...|

### Required layers
In order to calculate the impact metrics due to damages in the structural elements of the road
network, following layers should be provided.

* Road nodes
* Road edges
* Building
* Household
* Individual
* Intensity
* Vulnerability or Fragility
* Hazard type (flood, earthquake, debris)

## Algorithm
Road network analysis is composed of many steps some of them depend on the type of hazard.  

* The first step is to assign every building to the nearest node of the transportation network. This is achieved by nearest neighbor calculation. At the end of this step, a new attribute named *nearest_road_node* is added to building layer. The reason of this step is to determine the source and sink nodes of the graph. A source node is where the buildings and hence individuals are accumulated.
Whereas a sink is a node where hospitals are associated.

* if the hazard is flood:
* Buffer is added to roads so that they have a non-zero width of $2\times w$ where w is a threshold distance for flood calculations. 
* All intensity measures falling inside the road are determined
* The maximum of those intensity measures is taken as the ultimate intensity measure for this specific road. 

### Earthquake
* Unlike flood, in earthquake we don't need to create a buffer around roads. Instead,
we simply find the nearest intensity measure to the road.

After 

### Parameters
As you may notice, there are several parameters used in the calculations. Let's summarize them here:

* *flood_threshold_distance*: This parameter is buried inside the engine. It is used only in flood or debris flow calculations.
If a nearest intensity measure obtained for a bridge or any other structure is above this threshold, then the structure is 
assumed to be immune from the hazard. It's unit is in meters and its default value is 10 meters.
* *threshold*: This is also buried inside the engine. If a damage state of a structure is above this threshold,
then structure is assumed to be out of service. Its default value is 1 which represents slight damage. So
the structures having greater than slight damages is assumed to nonfunctional. 
* *road_water_height_threshold* If a part of a road has water level greater than this threshold, we 
asssume the road is flooded and hence does not provide service.

## Remarks
* In the exposure dataset, every household is associated with a unique hospital.
If there is a damage in that hospital, the household is assumed to lost its access to
hospitals. In the road network analysis, the idea is similar; if the household can
not reach its associated hospital via a path, then it is assumed to lost its 
hospital access even though it may reach other hospitals via intact bridges. 
* In setting intensity measure to roads, one can apply nearest neighbor calculation. If a road or a bridge is very long, then there will be many intensity measures getting close to the road. Let's say, the nearest water level intensity measure is 0.1 meter with a distance of 0.5 m) however there is 6 meter water level with a distance of 1 m on some other part of the road. In this case, 
* Since the roads can work in opposite directions, nx.DiGraph is used to represent the topology.

