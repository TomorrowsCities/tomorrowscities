---
author: huseyin.kaya
title: Road Network Analysis
description: How road connectivity impacts are computed for earthquake, flood, and landslide scenarios
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/bridge.jpg?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/bridge.jpg?raw=true
alt: "Road Network Analysis"
createdAt: 2023-10-10
duration: 7 min read
category:
  - general
---

[TOC]

## Introduction
Road network analysis in the app is used to estimate how hazard damage to bridges and road links changes access between people and essential services. The workflow currently supports **earthquake**, **flood**, and **landslide** scenarios.

At a high level, the app:

* assigns each building to its nearest road node
* evaluates whether road edges remain functional after hazard impact
* removes damaged edges from the network
* recalculates connectivity to hospitals and other assigned facilities

The result is not only a set of damaged road edges, but also updated accessibility fields on buildings, households, and individuals.

## Required Inputs
To run road analysis, the scenario needs the following layers:

* **Road nodes**
* **Road edges**
* **Building**
* **Household**
* **Individual**
* **Intensity**
* a hazard-dependent fragility layer

The exact hazard-dependent layer is:

* **Earthquake:** `road fragility`
* **Flood:** no separate road fragility is required; flood thresholds are applied directly to road edges
* **Landslide:** `landslide fragility`

## Coordinate Reference System
Input geospatial files are expected in **WGS84 / EPSG:4326**. During analysis, the app internally transforms layers to **EPSG:3857** so that nearest-neighbour joins and distance calculations can be performed in metric space.

## Road Nodes
Road nodes represent the junctions of the network. The minimum required fields are:

|node_id|geometry|
|-------|--------|
|3385919019|POINT (82.61515 27.80731)|
|3385919022|POINT (82.61096 27.80733)|

Required fields:

* **node_id**: unique identifier for each node
* **geometry**: point geometry in EPSG:4326

## Road Edges
Road edges represent the links between nodes. The minimum required fields are:

|edge_id|from_node|to_node|length|bridge_type|geometry|
|-------|---------|-------|------|-----------|--------|
|0|3385919019|3762934344|206.598|NaN|LINESTRING (...)|
|1|3385919022|3762934349|26.608|Steel|LINESTRING (...)|

Required fields:

* **edge_id**: unique edge identifier
* **from_node**: start node ID
* **to_node**: end node ID
* **length**: edge length
* **bridge_type**: bridge taxonomy used for earthquake fragility matching; non-bridge roads can remain empty
* **geometry**: line geometry in EPSG:4326

Optional but commonly present:

* **bridge**: boolean indicator for bridge membership

## Earthquake Road Fragility
For earthquake analysis, the app expects a **road fragility** table with the following fields:

|vuln_string|med_slight|med_moderate|med_extensive|med_complete|dispersion|
|-----------|----------|------------|-------------|------------|----------|
|Steel|0.18|0.29|0.44|0.63|0.55|
|RC|0.14|0.24|0.36|0.51|0.50|

In this format:

* **vuln_string** must match the `bridge_type` field in road edges
* **med_\*** columns define the median thresholds for DS1 to DS4
* **dispersion** controls the spread of the fragility curve

If a road edge does not match a fragility row, the current implementation effectively treats it as not damaged by the earthquake model.

## Landslide Fragility
For landslide analysis, the app expects a fragility table with:

* **expstr**
* **susceptibility**
* one or more trigger-level probability columns

During execution, the selected trigger-level column is converted into `collapse_probability`, and road edges are matched using a simple road class plus susceptibility combination.

## How the Current Algorithm Works

### Step 1: Assign buildings to road nodes
Each building is assigned to its nearest road node using a nearest-neighbour spatial join. The resulting node ID is written back to the building layer and then passed through to the household layer.

### Step 2: Build the graph
The road network is assembled as a graph from:

* road nodes as graph nodes
* road edges as graph edges

If **Preserve Edge Directions** is disabled, the graph is converted to an undirected network. If it is enabled, shortest-path calculations respect the supplied edge direction.

### Step 3: Evaluate road damage by hazard

#### Flood
For flood, the current implementation assigns the **nearest intensity value** to each road edge. It then marks roads as fully damaged (`DS4`) when:

* a non-bridge road exceeds the road water threshold, or
* a culvert exceeds the culvert water threshold

This is threshold-based logic rather than a probabilistic bridge fragility calculation.

In practice, flood damage assignment depends on:

* the nearest flood intensity value linked to the edge
* whether the edge is treated as a regular road or a culvert
* the flood distance threshold
* the configured water-level thresholds for roads and culverts

If the nearest flood point is too far away, the edge is treated as outside the flood footprint. If it is close enough and the water depth crosses the relevant threshold, the edge is treated as failed.

#### Earthquake
For earthquake, the app evaluates road edges using the **centroid** of each edge and assigns the nearest intensity measure. Bridge edges are then matched to the road fragility table using `bridge_type`, and a damage state is derived from the fragility model.

Edges with damage states above the built-in functionality threshold are marked as `is_damaged = True`.

In practice, earthquake damage assignment depends on:

* the `bridge_type` value of the edge
* the matching fragility record in the road fragility table
* the nearest assigned earthquake intensity value
* the selected earthquake intensity unit

The fragility model converts local shaking into damage-state probabilities. The app then assigns the most likely damage state and removes edges above the functionality threshold from the usable network.

#### Landslide
For landslide, the app assigns the nearest susceptibility/intensity context to each edge and uses the selected collapse probability to determine whether the edge fails.

### Step 4: Remove damaged edges
Any edge flagged as damaged is removed from a copy of the road network. Connectivity calculations are then performed on this damaged network.

### Step 5: Recalculate access
The app uses the damaged graph to update:

* **building-level hospital access**
* **household-level hospital access**
* **individual-level facility access**

The facility access logic works from the road node assigned to the household and the road node assigned to the individual's associated facility.

## How This Affects Metrics
Road analysis mainly affects metrics through **loss of connectivity**, not by directly rewriting all building damage results.

The most important downstream effect is on access-related metrics, especially:

* **households with no access to hospitals**
* accessibility-related interpretation of individual facility access
* scenario understanding through the number and spatial pattern of damaged road edges

This means that a scenario can show relatively modest direct building damage but still produce worse social outcomes if hospitals or important facilities become harder to reach through the damaged network.

### Road Impacts in Flood vs Earthquake
The practical difference between flood and earthquake in the road workflow is:

* **Flood:** roads are typically failed by threshold exceedance, so service loss behaves more like a binary inundation effect
* **Earthquake:** bridges fail through a fragility-based structural model, so service loss depends more strongly on bridge class and local shaking intensity

Because of that difference, flood scenarios often reflect whether a segment is overtopped or not, while earthquake scenarios more explicitly reflect differences in structural vulnerability between bridge types.

## Output Fields Added by the App

### Road edge outputs
The `road edges` layer receives:

* **ds**: road or bridge damage state
* **is_damaged**: boolean functional status used in network removal

### Building outputs
The `building` layer receives:

* **node_id**: nearest road node
* **hospital_access**: whether the building retains access to a hospital through the damaged network

### Household outputs
The `household` layer receives:

* **node_id**: inherited nearest road node
* **hospital_access**: whether the household can still reach its associated hospital

### Individual outputs
The `individual` layer receives:

* **facility_access**: whether the individual can still reach the associated facility node through the damaged network

## Important Parameters
The current road workflow depends on several important settings from the Engine page:

* **Minimum Flood Distance Threshold**: if the nearest flood intensity point is farther than this distance, the structure is treated as outside flood influence
* **Minimum Water Level Threshold for Roads**: threshold above which non-bridge roads are treated as flooded
* **Minimum Water Level Threshold for Culverts**: threshold above which culvert edges are treated as flooded
* **Earthquake Intensity Unit**: must match the uploaded intensity layer when earthquake is selected
* **Preserve Edge Directions**: controls whether the connectivity analysis uses a directed or undirected graph

## Quick Interpretation Tips
* If road damage looks limited but access loss is high, the network may be failing at a small number of strategically important links.
* In flood runs, accessibility can change sharply because road failure is threshold-based; small parameter changes may therefore produce noticeably different connectivity results.
* In earthquake runs, check whether `bridge_type` values are matching the fragility table before concluding that bridges are highly resilient.
* If one-way or directional movement matters in the study area, results can differ materially depending on whether **Preserve Edge Directions** is enabled.
* Compare damaged edges together with household or facility access outputs, because the social effect of disruption often depends more on where a link fails than on how many links fail.

## Remarks
* Hospital accessibility in the current model is linked to the household's associated hospital, not to any hospital anywhere in the network.
* Earthquake road damage currently depends on `bridge_type` matching the fragility table. If your bridge taxonomy is inconsistent, damage results may appear too low.
* Flood road damage currently uses threshold logic rather than a bridge-specific probabilistic flood fragility model.
* If your network edges are directional and one-way behaviour matters, enable **Preserve Edge Directions** before calculation.
* As with any scenario analysis, the outputs depend strongly on the assumptions embedded in exposure classes, network topology, and fragility definitions.
