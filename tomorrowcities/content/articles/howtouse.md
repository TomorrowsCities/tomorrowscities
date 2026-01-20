---
author: o-z-e-r-e-r
title: How to use WebApp
description: Use instructions for TCDSE WebApp
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/welcome.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/welcome.png?raw=true
alt: "How to use WebApp"
createdAt: 2026-01-19
duration: 20 min read
category:
  - general
---

## How to Use WebApp
Instructions is moved to [TomorrowsCities Wiki Page](https://github.com/TomorrowsCities/tomorrowcities/wiki)

## Quickstart
* Download [Sample Dataset](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view) to your local environment and unzip the archieve file.
* Go to [engine](/engine)
* Drag/drop necessary files to the drop zone of the engine and execute the engine. A sample session is displayed below. 
* The impact metrics will be immediately seen on the page.

<video width="853" controls>
  <source src="https://github-production-user-asset-6210df.s3.amazonaws.com/2515171/270064030-0733ad34-0a7f-445e-86fb-9a61df4e2969.mp4" type="video/mp4">
</video>

In case the file names in the video are not clearly seen, they are: 

* nairobi_business_buildings.geojson
* nairobi_business_household.json
* nairobi_business_individual.json
* nairobi_earthquake_fragility.json
* nairobi_earthquake_intensity.geojson

The used files above satisfy minimum requirements to run Earthquake analysis on buildings. 

## Features
General capabilities/features of the web application can be summarized as follows:

*Hazard Scenarios*

* Earthquake
* Flood
* Landslide

*Exposure Scenarios*

* Buildings
* Power networks
* Transportation

*Impact Metrics*

* Building and infrastructure-level damage states
* Household and individual-level derived metrics
* Casualy

*Policies*

* 20 [policies](/docs/policies) related to damage mitigation

*[Sample Dataset](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view)*

* Dar Es Salaam
* Rapti
* Nairobi
* Nablus

*Visualization*

* GIS Maps
* Hazard and Exposure data displayers
* Reactive metric widgets
* Damage state classifications

*Data structure*

* GeoJSON format for geospatial data
* Single or Multi-Band GeoTIFF formats for density maps
* Vanilla JSON and Excel for non-geospatioal tabular data
* XML support for [Global Vulnerability Model](https://github.com/gem/global_vulnerability_model) 

*Software*

* Pure-Python development for both backend and frontend
* Reactive user interface via Solara
* Leaflet backend for maps
* Easy deployment to cloud
