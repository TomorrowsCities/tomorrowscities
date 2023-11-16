---
author: huseyin.kaya
title: Land Slide
description: Land Slide damage assessment via Monte-Carlo Approach
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/flood.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/flood.png?raw=true
alt: "Flood vulnerability analysis"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

# Data Formats
 
## Susceptibility Map
Since it contains geo-spatial information, the format of this file should be GeoJSON.

|id|susceptibility|geometry|
|--|--------------|--------|
|0 |low           |MULTIPOLYGON (((82.66785 27.80147, 82.66906 27... |
|1 |medium        |MULTIPOLYGON (((82.60206 27.85078, 82.60202 27... |
|2 |low           |MULTIPOLYGON (((82.68074 27.79833, 82.68025 27... |
|3 |high          |MULTIPOLYGON (((82.62131 27.86873, 82.62120 27... |

## Fragility
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

## Trigger Level
Trigger level selection becomes active when the user selects "landuse" hazard type. 
There are three pre-defined levels: minor, moderate, and severe. The fragility data 
should contain a column for each category.


