---
author: huseyin.kaya
title: Flood
description: How to define flood vulnerabiities and conduct damage assessment 
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/flood.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/flood.png?raw=true
alt: "Flood vulnerability analysis"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

### Introduction
The core component used in flood vulnerability analysis depends on a mapping between water levels and relative damage on the structure. The shape of the curve depends on the typology of the structure, material type, height, code levels and the occupancy type. The Joint Research Centre (JRC) led by the European Commission provides technical reports and guidelines to generate such damage curves [1]. It is also always possible to make minor modification for special cases such as single storey adobe buildings in Africa [2,3]. 

### Data Format for Flood Vulnerability
Flood vulnerability is a tabular data example of which is shown below: 

|expstr	|hw0	|hw0_5	|hw1	|hw1_5	|hw2	|hw3	|hw4	|hw5	|hw6 |
|-------|-----|-------|-----|-------|-----|-----|-----|-----|----|
|BrCfl+LC+1s+Res	|0.000	|0.660	|0.980	|1.000	|1.000	|1.000	|1.000	|1.000	|1.000
|S/LFM+DUM+LC+2s+Com	|0.000	|0.330	|0.490	|0.620	|0.720	|0.870	|0.930	|0.980	|1.000
|BrCfl+HC+3s+Res	|0.000	|0.220	|0.327	|0.413	|0.480	|0.580	|0.620	|0.653	|0.667

The exposure string in the first column (**expstr**) contains four components separeted by '+' symbol: material type, code level, number of storeys and the occupancy. The material type can also contain '+' symbol, therefore parsing is done from right to left. In the example below, for instance, the material type of the second curve is 'S/LFM+DUM'.

The tabular data can be provided to engine in two formats: Microsoft Excel or JSON both of which is ok. However, if 
there are thousands of records in your data, we recommend JSON since importing a JSON is much faster than importing a Microsoft Excel.

## Remarks
* In both JRC [1] and modified version by Englhardt et.al [2],  the generated curves
do not depend on code levels of the structures. So any policy affecting code levels in flood damage assessment should find another way to change the damage states. See [policies](/docs/policies) for more information.


## References

* [1] Global flood depth-damage functions: Methodology and the database with guidelines, [link](https://publications.jrc.ec.europa.eu/repository/handle/JRC105688)
* [2] Englhardt, Johanna, et al. "Enhancement of large-scale flood risk assessments using building-material-based vulnerability curves for an object-based approach in urban and rural areas." Natural Hazards and Earth System Sciences 19.8 (2019): 1703-1722.  [link](https://nhess.copernicus.org/articles/19/1703/2019/nhess-19-1703-2019.pdf)
* [3] [Flood Vulnerability Generator](https://huggingface.co/spaces/hkayabilisim/flood_vulnerability_generator)
