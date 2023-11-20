---
author: huseyin.kaya
title: Data Formats 
description: Description of the data formats used in web application
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/data.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/data.png?raw=true
alt: "Data Formats"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Data Structures
Tomorrow's Cities Decision Support Environment (TCDSE) is capable of conducting different hazard scenarios on different infrastructures, hence it needs to use several layers with different data input/output formats.

## Storage Formats
**Tabular**
If the data does not contain geo-spatial information, then spreadsheet formats such as
Comma-Separated Values (*.csv) or Microsoft Excel (*.xlsx) can be used to store the data.

**GeoGSON**
The primary choice of the webapp to store geo-spatial information is GeoJSON for couple of reasons. 
First, unlike SHP format, it doesn't require auxillary files so it is easy to transfer or load
a GeoJSON file. Secondly, it is supported by QGIS and geopandas Python libraries. Another advantage is
that every GeoJSON is a text file and you can always look at the content by any text editor.

**GeoTIFF**
When the intensity measures are given as a mesh of rectangular grid, then the number of points to store 
can become very large. In those cases, the size of the GeoJSON files will be very large because GeoJSON is 
a text file and there will be redundant information. It is possible to compress a GeoJSON but a better 
approach is to use GeoTIFF files. GeoTIFF is useful because it is a raster file and moreover geo-spatial
context is already built-in in the format. Additionally GeoTIFF files are lot smaller than GeoJSON files.
Please note that GeoTIFF is only advised to represent intensity measures on a mesh grid. 

**Multi-band GeoTIFF**
GeoTIFF format also supports multiple bands which becomes handy when we want to store multiple
density maps in single TIF file. This is especially useful for using multiple spectral acceleration 
intensity maps. In order to convey which band corresponds to which spectral acceleration period, the bands
in the GeoTIFF are labelled such as "PGA", "SA 0.3", "SA 1", etc.


## Layers
The layers supported by tomorrowcities are listed below.  In this section, we will cover all of them and provide information so that the users are able to generate data compatible to web application. Unless otherwise
mentioned, all geo-spatial layers have WGS 84 coordinate reference system with EPSG:4326.

* land use 
* building
* household
* individual
* intensity
* fragility
* vulnerability
* power nodes
* power edges

### Landuse
Landuse plan is presented as a GeoJSON format whose attributes are given below:


|population|status|zone|densitycap|luf|landuse_lu|area|zoneid|floorarear|setback|avgincome|
|----------|------|----|----------|---|----------|----|------|----------|-------|---------|
0|None 	|Agricultural Zone 	|0.0 	|Agricultural Zone 	|Agricultural Zone 	|4099.24144134 	|4 	|0.0 	|0.0 	|None|
0| None |Forest Zone 	|0.0 	|Forest Zone 	|Forest Zone 	|30843.9849839 	|5 	|0.0 	|0.0 	|None|
7081 	|None 	|Residential Very Low Density 	|5.0 	|Residential-Very Low Density |	Agriculture Cum Resedential	|1416.16357154 	|226 	|0.0 	|0.0 	|lowIncome|


### Buildings
Buildings are the core component of visioning scenarios. The features of the building with some example data are shown below:

|zoneid| bldid | nhouse | residents | specialfac | expstr          | fptarea | geometry     | 
|------|-------|--------|-----------|------------|-----------------|---------|--------------|
|4     | 17    | 41     | 178       | 0          |RCi+HC+18s+ResCom| 111     | MultiPolygon |


where

* **zoneid (integer)** refers to the unique identitifer of the zone that building is located in. The features of the corresponding zone is described in a dedicated zone table.
* **bldid (integer)** is a unique building identifier.
* **nhouse (integer)** is the number of household in that building.
* **residents (integer)** stores the number of individual live in the building.
* **expstr (string)** 

### Households
Households are defined in a tabular format whose attributes are shown below:

|bldid|hhid|income|nind|commfacid|
|-----|----|------|----|---------|
|17   |12  |lowIncomeA|3|3643|

where

* **bldid (integer)** is the building identifier where the household is located in 
* **hhid (integer)** is the unique identifier for the household
* **income (string)** is the income level of the household
* **nind (integer)** is the number of individuals living in the household
* **commfacid (integer)** is the building identifier of the community facility. In Tomorrow's Cities, it is used to define the hospital associated with the household. 

### Individuals
Individual layer is a tabular data which can be stored in Excel or JSON format.
The attributes are:

|hhid|individ|gender|age|head|eduattstat|indivfacid|
|----|-------|------|---|----|----------|----------|
|24448| 	1| 	2| 	8| 	1| 	3| 	-1|
|1 	|5552 	|2 	|2 	|8 	|1 	|4 	|-1 	|
|2 	|31586 	|3 	|2 	|9 	|1 	|5 	|-1 	|

where 

* **hhid** refers to household identifier where the individual lives in.
* **individ** is the unique individual identifier
* **gender** is a categorical variable for gender: 1: male, 2:female
* **age** is the age category
* **head** is a binary feature indicating that the individual is the head of the household
* **eduattstat** is the education level
* **indivfacid** is the facility (school or workspace) that the individual is associated with

### Intensity Measures
Whether it is flood, debris or earthquake, every hazard map should contain at least two properties: a point geometry and intensity measure denotes by 'im'. The data can be provided via GeoTIFF or GeoJSON format. TIFF files should contain CRS 
information so that the engine could map the coordinates to a common CRS to conduct calculations.


### Vulnerability
The engine has a built-in support for [Global Vulnerability Model (GVM)](https://github.com/gem/global_vulnerability_model) used in [Global Earthquake Model (GEM)](https://github.com/gem). 
GVM uses an XML format in which one can define several vulnerability functons. There are almost a thousand XML files in [GVM repository](https://github.com/gem/global_vulnerability_model) precomputed for hundred cities from all continents. When a user uploads an XML file conforming to GVM, the engine can parse, display and use it in the calculations.

The GVM's XML format is very simple. For demonstration purposes, we provide a short but structurally-complete one below. Please note that the values do not represent a real vulnerability function:

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<nrml xmlns="http://openquake.org/xmlns/nrml/0.5">
<vulnerabilityModel id="vulnerability_model" 
                    assetCategory="buildings" 
                    lossCategory="structural">
  <description>Example vulnerability model</description>

  <vulnerabilityFunction id="CR/LDUAL+CDL+DUM/H12/COM" dist="BT">
    <imls imt="SA(1.0)">0.05 0.1 1.2 2.3 5.2 6.6 8.38 15</imls>
    <meanLRs>1e-08 0.0001 0.002 0.06 0.14 0.19 0.6 0.99</meanLRs>
    <covLRs>1e-08 1e-08 1e-08 1e-08 0.62 0.53 1e-08 1e-08 </covLRs>
  </vulnerabilityFunction>

  <vulnerabilityFunction id="MUR+CLBRS/LWAL+DNO/H1/RES" dist="BT">
    <imls imt="SA(1.0)">0.04 0.2 1.2 2.3 5.2 6.4 9.38 15</imls>
    <meanLRs>1e-08 0.001 0.003 0.06 0.15 0.18 0.7 0.99</meanLRs>
    <covLRs>1e-08 1e-08 1e-08 1e-08 0.2 0.6 1e-08 1e-08 </covLRs>
  </vulnerabilityFunction>

  </vulnerabilityModel>
</nrml>
~~~

