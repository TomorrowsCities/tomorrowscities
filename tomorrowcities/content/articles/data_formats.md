---
author: huseyin.kaya
title: Data Formats 
description: Description of the data formats used in web application
alt: "Data Formats"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

## Data Structures
Tomorrow's Cities Decision Support Environment (TCDSE) is capable of conducting different hazard scenarios on different infrastructures, hence it needs to use several data input/output formats. 

There are may different possible strategies and data formats to describe and store data. 
In TCDSE, we generally use tabular data where each row corresponds to a unique object whereas the columns corresponds to the features of that object. Object here can refer to a building, individual, etc. Full list of the objects for which we use a dedicated data file is as follows:

* landuse 
* building
* household
* individual
* intensity
* fragility
* vulnerability
* power nodes
* power edges

**Storage Format:** The tabular data can be stored in different formats such as Comma-Separeted Values or spreadsheets. If the data does not contain geographic coordinates or the coordinates are defined with longitude and latitude pairs, spreadsheet formats 

In this way, building data can be joined with other type of data that we will mention in the coming section via relational databases.

### Format


## Layers
### Buildings
Buildings are the core component of visioning scenarios. The features of the building with some example data are shown below:

|zoneID| bldID | nHouse | residents | specialFac | expStr          | fptarea | geometry     | 
|------|-------|--------|-----------|------------|-----------------|---------|--------------|
|4     | 17    | 41     | 178       | 0          |RCi+HC+18s+ResCom| 111     | MultiPolygon |


where

* **zoneID (integer)** refers to the unique identitifer of the zone that building is located in. The features of the corresponding zone is described in a dedicated zone table.
* **bldID (integer)** is a unique building identifier.
* **nHouse (integer)** is the number of household in that building.
* **residents (integer)** stores the number of individual live in the building.
* **expStr (string)** 

### Intensity Measures
Whether it is flood, debris or earthquake, every hazard map should contain at least two properties: a point geometry and intensity measure denotes by 'im'. The data can be provided via GeoTIFF or GeoJSON format. TIFF files should contain CRS 
information so that the engine could map the coordinates to a common CRS to conduct calculations.


