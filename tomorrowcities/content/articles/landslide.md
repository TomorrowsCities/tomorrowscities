---
author: huseyin.kaya
title: Land Slide
description: Land Slide damage assessment via Monte-Carlo Approach
image: https://raw.githubusercontent.com/TomorrowsCities/tomorrowcities/main/tomorrowcities/content/images/landslide.jpg?raw=true
thumbnail: https://raw.githubusercontent.com/TomorrowsCities/tomorrowcities/main/tomorrowcities/content/images/landslide.jpg?raw=true
alt: "Landslide analysis"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Data Formats
 
### Susceptibility Map

Since it contains geo-spatial information, the format of this file should be GeoJSON.

|id|susceptibility|geometry|
|--|--------------|--------|
|0 |low           |MULTIPOLYGON (((82.66785 27.80147, 82.66906 27... |
|1 |medium        |MULTIPOLYGON (((82.60206 27.85078, 82.60202 27... |
|2 |low           |MULTIPOLYGON (((82.68074 27.79833, 82.68025 27... |
|3 |high          |MULTIPOLYGON (((82.62131 27.86873, 82.62120 27... |

### Fragility
Collapse probability depends on three factors:

* **expstr**: taxonomy of the structure
* **susceptibility**: which susceptibility zone the structure is in
* **trigger level**: amount of rainfall which is categorized into minor, moderate and severe.

Since it is a tabular data with no geo-spatial context, the data can be provided in 
Microsoft Excel or JSON format.

|expstr|susceptibility|minor|moderate|severe|
|------|--------------|-----|--------|------|
|Adb+HC+10s+Edu| 	low 	|0.01 	|0.02 	|0.03|
|Adb+HC+1s+Res |	low 	|0.03 	|0.04 	|0.05|
|Adb+HC+1s+ResCom|	low |0.06 	|0.08 	|0.09| 

### Trigger Level

Trigger level selection becomes active when the user selects "landuse" hazard type. 
There are three pre-defined levels: minor, moderate, and severe. The fragility data 
should contain a column for each category.

## Algorithm
The algorithm starts with geo-spatial merge of susceptibility map and the building layer. 
For this purpose, **sjoin_nearest** function of GeoPandas is used. As a result of 
merging process, the buildings have susceptibility attribute. 

The merged tabular data is left joined with fragility data. In this merge, instead of using all minor, moderate
and severe columns, only the column matching to the trigger level is used. For instance, if the trigger level
is moderate, expstr, susceptibility,  and moderate columns are used. As a result of this merge, the buildings
now have collapse probabilities.

The next step is Monte-Carlo simulation. For each building, a random number between zero and one is picked.
If it is less than the building's collapse probability, then the damage state of the building is set to DS_COLLAPSED (4)
otherwise to DS_NO (0).

Then by using household, landuse and individual layers, the seven impact metrics are calculated.

Above process is repeated N times and the impact metrics are averaged. In the metric widgets 
these averaged impact metrics are displayed. 

In the map, and the layer displayer, however, the damage states of the buildings and other infrastructures are displayed 
according to the last Monte-Carlo random realization. However, the attributes metric1,...,metric7 denote the average 
over N random trials. 