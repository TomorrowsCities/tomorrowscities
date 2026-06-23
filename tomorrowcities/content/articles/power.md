---
author: huseyin.kaya
title: Power Network Analysis
description: How power service loss is computed for earthquake, flood, and landslide scenarios
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/power.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/power.png?raw=true
alt: "Power Network Analysis"
createdAt: 2023-10-10
duration: 7 min read
category:
  - general
---

[TOC]

## Introduction
Power network analysis estimates whether buildings, households, and hospital-linked households continue to receive service after damage to the electrical network. The current workflow supports **earthquake**, **flood**, and **landslide** scenarios.

The app models the power network as a graph and then removes or disables affected infrastructure nodes depending on the hazard. Service loss is then propagated to buildings and households through the nearest active distribution node.

## Required Inputs
To run power analysis, the scenario needs:

* **Power nodes**
* **Power edges**
* **Building**
* **Household**
* **Intensity**
* a hazard-dependent fragility or vulnerability layer

The hazard-dependent layer is:

* **Earthquake:** `power fragility`
* **Flood:** `vulnerability`
* **Landslide:** `landslide fragility`

## Coordinate Reference System
Input geospatial files should be provided in **EPSG:4326**. The app internally converts them to **EPSG:3857** for distance-based spatial operations.

## Power Nodes
The minimum required attributes for power nodes are:

|node_id|pwr_plant|n_bldgs|geometry|
|-------|---------|-------|--------|
|1|1|0|POINT (...)|
|2|0|250|POINT (...)|
|3|0|120|POINT (...)|

Required fields:

* **node_id**: unique node identifier
* **pwr_plant**: whether the node is a generation/source node
* **n_bldgs**: number of buildings served by the node; nodes with values greater than zero are treated as service/distribution nodes
* **geometry**: point geometry in EPSG:4326

Common optional fields used by different hazards include:

* **eq_frgl**: earthquake fragility taxonomy string
* **fl_vuln**: flood vulnerability string
* **ls_frgl**: landslide fragility taxonomy string
* **ls_susceptibility**: optional landslide susceptibility class
* **fl_water_depth**: optional flood depth override at node level

## Power Edges
The minimum required attributes for power edges are:

|edge_id|from_node|to_node|geometry|
|-------|---------|-------|--------|
|1|2|1|LINESTRING (...)|
|2|3|1|LINESTRING (...)|

Required fields:

* **edge_id**: unique line identifier
* **from_node**: start node ID
* **to_node**: end node ID
* **geometry**: line geometry

In the current implementation, power edges are used to build the connectivity graph, but hazard damage states are evaluated on **power nodes**, not directly on edges.

## Earthquake Power Fragility
For earthquake analysis, the app expects a **power fragility** table with:

|vuln_string|med_slight|med_moderate|med_extensive|med_complete|beta_slight|beta_moderate|beta_extensive|beta_complete|
|-----------|----------|------------|-------------|------------|-----------|-------------|--------------|-------------|
|ESS1|0.15|0.29|0.45|0.90|0.70|0.55|0.45|0.45|
|ESS2|0.13|0.26|0.34|0.74|0.65|0.50|0.40|0.40|

In this format:

* **vuln_string** must match the power node field **`eq_frgl`**
* **med_\*** values define median thresholds for damage states
* **beta_\*** values define dispersion parameters

## Flood Power Vulnerability
For flood analysis, the app uses the standard **vulnerability** table rather than the earthquake-style fragility table. Power nodes are matched using **`fl_vuln`**, and flood depths are converted into damage states using the vulnerability curve.

If a node contains **`fl_water_depth`**, that value overrides the nearest intensity point for flood calculations.

In practice, flood damage assignment depends on:

* the node vulnerability class in `fl_vuln`
* the water-depth-to-damage relationship in the vulnerability table
* the nearest flood intensity value, unless `fl_water_depth` is already provided
* the flood thresholds used to convert relative damage into DS2, DS3, and DS4

## Landslide Fragility
For landslide analysis, the app expects:

* **expstr**
* **susceptibility**
* one or more trigger-level probability columns

At runtime, the chosen trigger-level column is converted to `collapse_probability`, and the node is matched using `ls_frgl + susceptibility`.

## How the Current Algorithm Works

### Step 1: Build the graph
The app creates a graph from:

* power nodes as graph nodes
* power edges as graph edges

If **Preserve Edge Directions** is disabled, the graph is converted to an undirected network. If enabled, direction is preserved during connectivity evaluation.

### Step 2: Assign hazard intensity to nodes
Each power node is assigned its nearest intensity measure using a nearest-neighbour spatial join.

### Step 3: Derive damage states

#### Earthquake
Power nodes are matched to the power fragility table using `eq_frgl -> vuln_string`. The app computes probabilities for DS1 to DS4 and then assigns a discrete damage state.

In practice, earthquake damage assignment depends on:

* the node taxonomy stored in `eq_frgl`
* the matching fragility row in the power fragility table
* the nearest earthquake intensity value assigned to the node
* the selected earthquake intensity unit

The fragility model transforms local shaking intensity into damage-state probabilities. Nodes beyond the operational damage cutoff are treated as failed and removed from the post-event network.

#### Flood
Power nodes are matched to the flood vulnerability table using `fl_vuln -> expstr`. Water depth is converted into relative damage and then mapped to a damage state using the Engine flood thresholds.

This means the flood workflow is less about structural fragility curves in the earthquake sense and more about depth-damage translation followed by threshold-based damage-state assignment.

#### Landslide
Power nodes are matched to landslide fragility using `ls_frgl` and susceptibility, and failure is sampled from collapse probability.

### Step 4: Remove damaged nodes
Nodes with damage states above the built-in functionality threshold are treated as failed and removed from the operational power network.

In the current implementation:

* generation nodes are identified by **`pwr_plant == 1`**
* service/distribution nodes are identified by **`n_bldgs > 0`**

### Step 5: Recalculate service availability
The app then computes which nodes remain reachable from operational generation nodes. Buildings are attached to the nearest service node, and service availability is propagated to:

* buildings
* households
* hospital-linked households

## How This Affects Metrics
Power analysis affects outcomes mainly through **service availability** rather than through a dedicated top-level "power damage" metric.

The most important downstream fields are:

* **building `has_power`**
* **household `has_power`**
* **household `hospital_has_power`**

These outputs influence how users interpret indirect disruption, especially when the functionality of buildings, households, and health-related facilities matters as much as their structural damage.

### Power Impacts in Flood vs Earthquake
The practical difference between flood and earthquake in the power workflow is:

* **Earthquake:** damage is controlled by node fragility class plus shaking intensity
* **Flood:** damage is controlled by vulnerability curves plus water depth

In both cases, the final service outcome depends on two things:

1. whether a node is damaged
2. whether surviving service nodes are still connected to an operating generation source

So two scenarios with similar raw node damage counts can still produce different service-loss outcomes if their remaining network connectivity differs.

## Output Fields Added by the App

### Power node outputs
The `power nodes` layer receives:

* **ds**: node damage state
* **is_damaged**: whether the node is considered damaged
* **is_operational**: whether the node remains connected to an operating source in the post-damage network

### Building outputs
The `building` layer receives:

* **has_power**: whether the building is linked to an operational service node

### Household outputs
The `household` layer receives:

* **has_power**: whether the household's building still has service
* **hospital_has_power**: whether the household's associated community facility / hospital building still has power

## Important Parameters
The current power workflow depends on:

* **Earthquake Intensity Unit**: must match the uploaded intensity layer for earthquake runs
* **Minimum Flood Distance Threshold**: used to suppress flood influence when the nearest flood point is too far from the node
* **Flood damage thresholds**: used to translate flood vulnerability results into DS2, DS3, and DS4
* **Preserve Edge Directions**: controls whether connectivity is directional or undirected

## Quick Interpretation Tips
* A modest number of damaged power nodes can still produce large service loss if those nodes disconnect important parts of the network from generation sources.
* In flood scenarios, review both the vulnerability curves and the flood DS thresholds before comparing service-loss outcomes across cases.
* In earthquake scenarios, low damage counts may sometimes indicate taxonomy mismatches in `eq_frgl` rather than genuinely robust infrastructure.
* If buildings are linked to sparse or unevenly distributed service nodes, `has_power` patterns may reflect network design assumptions as much as hazard intensity.
* Interpret node damage together with `is_operational` and downstream `has_power` fields, because a node can survive structurally but still fail to provide service if connectivity to generation is lost.

## Remarks
* Power service is evaluated through node damage and network connectivity. The current implementation does not assign independent hazard damage states to power edges.
* Earthquake matching depends on `eq_frgl`, not the older `eq_vuln` naming used in some historical examples.
* Flood analysis for power uses the generic vulnerability table, not the earthquake fragility format.
* Buildings are linked to their nearest service node (`n_bldgs > 0`), so the realism of service loss depends strongly on how those service nodes are defined in the input network.
* As with the rest of the app, these outputs are scenario-based analytical results and should be interpreted in light of the assumptions embedded in the supplied network, exposure, and hazard data.
