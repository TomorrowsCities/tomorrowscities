---
author: huseyin.kaya
title: Road Networks
description: Earthquake and flood damage asssesment on road networks with bridges
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/data.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/data.png?raw=true
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

## Data
From a computational point of perspective, a road network is a bi-directional graph
whose edges correspond to roads whereas the nodes represent connection points such as cross-roads or bridges. 

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

### Flood
* The first step is to assign buildings to nearest nodes of the transporation network.
* Buffer is added to roads so that they have a non-zero width of 2*threshold_flood_distance
* All intensity measures falling inside the road are determined
* The maximum of those intensity measures is taken as the ultimate intensity measure for this specific road. 

### Earthquake
* The first step is to assign buildings to nearest nodes of the transporation network.
* Unlike flood, in earthquake we don't need to create a buffer around roads. Instead,
we simply find the nearest intensity measure to the road/bridge.
## Remarks
* In the exposure dataset, every household is associated with a unique hospital.
If there is a damage in that hospital, the household is assumed to lost its access to
hospitals. In the road network analysis, the idea is similar; if the household can
not reach its associated hospital via a path, then it is assumed to lost its 
hospital access even though it may reach other hospitals via intact bridges. 
* In setting intensity measure to roads, one can apply nearest neighbor calculation. If a road or a bridge is very long, then there will be many intensity measures getting close to the road. Let's say, the nearest water level intensity measure is 0.1 meter with a distance of 0.5 m) however there is 6 meter water level with a distance of 1 m on some other part of the road. In this case, 

