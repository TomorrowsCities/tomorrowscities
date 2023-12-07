---
author: huseyin.kaya
title: Welcome!
description: A Brief Introduction to Tomorrow's Cities Decision Support Environment (TCDSE)
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/welcome.jpg?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/welcome.jpg?raw=true
alt: "Welcome!"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

## Tomorrow's Cities Decision Support Environment (TCDSE) Webapp v0.2: Derry
TCDSE is a web application designed to conduct computational tasks to generate information needed for decision mechanisms in designing future cities. The web application, which will be referred as TCDSE for short, contains a computational engine capable of executing several hazard scenarios on different exposure datasets and infrastructures. 

## Documentation
Documentation is moved to [TomorrowsCities Wiki Page](https://github.com/TomorrowsCities/tomorrowcities/wiki) 

## What is New?

**Changelog: v0.2.4**

* Landslide calculation
* Multi-band GeoTIFF support
* Casualty metric
* Adjustable flood settings
* New city added to sample dataset
* Flood analysis for power networks

**Changelog: v0.2.3**

* AWS S3 Sample Data Input mechanism is built
* popup functionality is implemented
* layout is now 3-column
* settings and data import is separated by tabs
* z-index of map is lowered

**Changelog: v0.2.2**

* Power and Road network analysis is completed.
* Electrical power loss information is propagated to household and individual layers.
* All seven impact metrics are updated to reflect electrical power-loss.
* All seven impact metrics are updated to reflect damage in road network.
* Documentation in the engine is extended.
* New version of the engine is redeployed to [HuggingFace](https://huggingface.co/spaces/hkayabilisim/app-engine).
* Reorganized the folders in the [Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing).
* Building layer can now be exported as CSV also.

**Changelog: v0.2.1**

* [27dd195](https://github.com/TomorrowsCities/tomorrowcities/commit/27dd195a240cbb97a97d124fc9b132ee2ea1f5e9) Integrated road network analysis into metric3
* [de6fbca](https://github.com/TomorrowsCities/tomorrowcities/commit/de6fbca8d8b03d350096190ae35646f47a9a0414) Changed engine layout to be more compact 
* [bc436b6](https://github.com/TomorrowsCities/tomorrowcities/commit/bc436b62c35f66b7432e40ca5e6c47364690c8f3) Bugfix a layout problem in engine page 
* [0b1cd96](https://github.com/TomorrowsCities/tomorrowcities/commit/0b1cd96149e129de30e5524f8956db1569202450) Bugfix in metric calculation: a typo in code_level 
* Extended documentation in welcome, data, metrics, and road pages.
* Added [a demonstration video](https://github.com/TomorrowsCities/tomorrowcities/assets/2515171/ec2dc36d-fe76-42fb-b9be-47a1690374de) to GitHub discussion page[discussion](https://github.com/TomorrowsCities/tomorrowcities/discussions/6).

**Changelog: v0.2**

* Transportation network analysis for flood and earthquake damage assessment
* Building and household-level loss of hospital access information
* Enabling custom preprocessing function for every layer
* building preprocessing added to generate material, storeys, code level and occupancy
* Building coloring based on loss of hospital acess
* Using centroid of bridges to calculate nearest earthquake intensity measure
* Backend.utils package is added
* Nearest transportation node is determined
* Started documentation for road network analysis
* Added dummy data to [Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing) for Rapti.

**v0.1**

* Transportation network with earthquake damage assessment with application to Rapti. See [Road Networks](/docs/road).
* "freqincome" attribute is added to building layer.
* Amazon S3 support to save session or policy database.
* The engine now can parse, display vulnerability curves located on [Global Vulnerability Model Reposity](https://github.com/gem/global_vulnerability_model) maintained by [Global Earthquake Model Foundation)](https://www.globalquakemodel.org/gem). To see the new fatures, download one of the XML files in  [Global Vulnerability Model Reposity](https://github.com/gem/global_vulnerability_model) and drag and drop to [Engine](/engine). The engine will read all the vulnerability functions defined in the XML file and display them. 
* basemap is changed to ESri.WorldImagery to see the landscapes especially rivers.
* utilities page is added.
* Excel to GeoJSON converted is added to utilities page.
* GeoTIFF support is added. 
* When an intensity layer is added via GeoTIFF format, only the non-zero intensity measure are retained by the engine.
* In map visualization of intensity layer, only the largest 500k points are displayed to render the map faster.
* rasterio.transform.xy function is replaced with a faster local implementation.
* Info box is added next to the map to see overall information and building/landuse details
when clicked.
* Implementation Capacity Score is added. If medium or low is selected, then building-level metrics is increased by 25% and 50%, respectively. If high is selected, there is no change in the metrics.

## Quickstart
* Download [Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing) to your local environment and unzip the archieve file.
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

*[Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing)*

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