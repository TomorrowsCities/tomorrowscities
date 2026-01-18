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

## Tomorrow's Cities Decision Support Environment (TCDSE) Webapp v0.6
TCDSE is a web application designed to conduct computational tasks to generate information needed for decision mechanisms in designing future cities. The web application, which will be referred as TCDSE for short, contains a computational engine capable of executing several hazard scenarios on different exposure datasets and infrastructures. 

## Documentation
Documentation is moved to [TomorrowsCities Wiki Page](https://github.com/TomorrowsCities/tomorrowcities/wiki) 

## What is New?

**Changelog: v0.6**

   * **Backend**
       * feature: multiple damage class for flood by @hkayabilisim in [113](https://github.com/TomorrowsCities/tomorrowscities/pull/113)
       * fix: typos in damage state static variables by @hkayabilisim in [116](https://github.com/TomorrowsCities/tomorrowscities/pull/116)
   * **Performance**
      * fix: performance issues on too large tally files by @hkayabilisim in [83](https://github.com/TomorrowsCities/tomorrowscities/pull/83)
      * fix: refactor explore for large tally files by @hkayabilisim in [85](https://github.com/TomorrowsCities/tomorrowscities/pull/85)
   * **Data Generation**
      * fix: update exposure data generation by @o-z-e-r-e-r in [87](https://github.com/TomorrowsCities/tomorrowscities/pull/87)
      * fix: update backend/engine.py by @o-z-e-r-e-r in [91](https://github.com/TomorrowsCities/tomorrowscities/pull/91)
      * fix: rerender map after data generation by @hkayabilisim in [92](https://github.com/TomorrowsCities/tomorrowscities/pull/92)
      * ui: data generation sample inputs by @o-z-e-r-e-r in [88](https://github.com/TomorrowsCities/tomorrowscities/pull/88)
      * ui: update data generation sample link by @o-z-e-r-e-r in [89](https://github.com/TomorrowsCities/tomorrowscities/pull/89)
   * **Authentication**
      * feature: get rid of local user authentication by @hkayabilisim in [71](https://github.com/TomorrowsCities/tomorrowscities/pull/71)
      * feature: enabling test login for local environments by @hkayabilisim in [76](https://github.com/TomorrowsCities/tomorrowscities/pull/76)
      * fix: enable_test_logon env check is corrected by @hkayabilisim in [80](https://github.com/TomorrowsCities/tomorrowscities/pull/80)
      * fix: prevent logging out after page reloads by @hkayabilisim in [74](https://github.com/TomorrowsCities/tomorrowscities/pull/74)
   * **Color Schemes**
      * ui: color standardization (urban atlas) by @hkayabilisim in [79](https://github.com/TomorrowsCities/tomorrowscities/pull/79)
      * fix: revered color order (red -> high damage) by @hkayabilisim in [82](https://github.com/TomorrowsCities/tomorrowscities/pull/82)
      * fix: apply custom colours to power network after calculation by @o-z-e-r-e-r in [112](https://github.com/TomorrowsCities/tomorrowscities/pull/112)
      * ui: revise power node icons by @o-z-e-r-e-r in [108](https://github.com/TomorrowsCities/tomorrowscities/pull/108)
      * Revert "ui: revise power node icons" by @hkayabilisim in [110](https://github.com/TomorrowsCities/tomorrowscities/pull/110)
      * Apply again "ui: revise power node icons" by @hkayabilisim in [111](https://github.com/TomorrowsCities/tomorrowscities/pull/111)
   * **Policies**
      * feature: reimplement policy 1 by @hkayabilisim in [84](https://github.com/TomorrowsCities/tomorrowscities/pull/84)
      * feature: reimplement policy 2 by @hkayabilisim in [97](https://github.com/TomorrowsCities/tomorrowscities/pull/97)
      * feature: reimplement policy 3 by @hkayabilisim in [100](https://github.com/TomorrowsCities/tomorrowscities/pull/100)
      * feature/fix: policy 4 and cdf_median_increase by @hkayabilisim in [101](https://github.com/TomorrowsCities/tomorrowscities/pull/101)
      * features: implemented policy 5 by @hkayabilisim in [106](https://github.com/TomorrowsCities/tomorrowscities/pull/106)
      * feature: implemented policy 6 by @hkayabilisim in [103](https://github.com/TomorrowsCities/tomorrowscities/pull/103)
      * feature: implemented policy 8 by @hkayabilisim in [104](https://github.com/TomorrowsCities/tomorrowscities/pull/104)
      * feature: implemented policy 9 by @hkayabilisim in [105](https://github.com/TomorrowsCities/tomorrowscities/pull/105)
      * fix: disable policies 7 and 10 temporarly by @hkayabilisim in [109](https://github.com/TomorrowsCities/tomorrowscities/pull/109)
      * fix: cdf_median_decrease_in_percent to [0,1] by @hkayabilisim in [86](https://github.com/TomorrowsCities/tomorrowscities/pull/86)
      * fix: remove obsolete code for policy 9 by @hkayabilisim in [107](https://github.com/TomorrowsCities/tomorrowscities/pull/107)
   * **UI**
      * feature: persist engine results to browser refresh by @hkayabilisim in [93](https://github.com/TomorrowsCities/tomorrowscities/pull/93)
      * ui: update header & feat: provide collapsible layer displayer and data import by @o-z-e-r-e-r in [96](https://github.com/TomorrowsCities/tomorrowscities/pull/96)
      * ui: making labels more human-friendly by @hkayabilisim in [94](https://github.com/TomorrowsCities/tomorrowscities/pull/94)
      * ui: almost all attributes are now human-friendly by @hkayabilisim in [102](https://github.com/TomorrowsCities/tomorrowscities/pull/102)
      * ui: saving is limited to logged on users by @hkayabilisim in [72](https://github.com/TomorrowsCities/tomorrowscities/pull/72)
      * ui: arrange sample dataset by @o-z-e-r-e-r in [99](https://github.com/TomorrowsCities/tomorrowscities/pull/99)
      * ui: reorganized refactor filters by @hkayabilisim in [77](https://github.com/TomorrowsCities/tomorrowscities/pull/77)
      * fix: can't drop same file again by @hkayabilisim in [95](https://github.com/TomorrowsCities/tomorrowscities/pull/95)
   * **Others**
      * fix: use tempfiles on s3 operations by @hkayabilisim in [73](https://github.com/TomorrowsCities/tomorrowscities/pull/73)
      * fix: clear session button is fixed by @hkayabilisim in [75](https://github.com/TomorrowsCities/tomorrowscities/pull/75)
      * fix: wrong use of temp folder on s3 download by @hkayabilisim in [98](https://github.com/TomorrowsCities/tomorrowscities/pull/98)
      * ui: added landuse and tally to explore filters by @hkayabilisim in [78](https://github.com/TomorrowsCities/tomorrowscities/pull/78)
      * ui: added devcontainer support by @hkayabilisim in [81](https://github.com/TomorrowsCities/tomorrowscities/pull/81)
      * cleanup: remove unused debris option from backend by @hkayabilisim in [114](https://github.com/TomorrowsCities/tomorrowscities/pull/114)
      * cleanup: remove obsolete backend.calculate_metrics by @hkayabilisim in [115](https://github.com/TomorrowsCities/tomorrowscities/pull/115)

**Full Changelog**: [v0.5...v0.6](https://github.com/TomorrowsCities/tomorrowscities/compare/v0.5...v0.6)


**Changelog: v0.5**

* feature: github/google authentication via OAuth2 by @hkayabilisim in [68](https://github.com/TomorrowsCities/tomorrowscities/pull/68)
* feature: storage-related improvements by @hkayabilisim in [69](https://github.com/TomorrowsCities/tomorrowscities/pull/69)


    - AWS credentials are now in local secret env. This makes it possible
      to deploy the webapp pre-configures to have access to S3 bucket
    - Storage-related configs are removed from settings page
    - Storage initialization is moved into __init__
    - User information is added to the session metadata
    - Metadata viewer is added
    - Session save is disable if no run is made
    - session list is loaded on initialization


* feature: redundant policies redefined, step 1 by @hkayabilisim in [56](https://github.com/TomorrowsCities/tomorrowscities/pull/56)
* feature: separeated map and metric filters by @hkayabilisim in [59](https://github.com/TomorrowsCities/tomorrowscities/pull/59)
* feature: add more features to building filter by @hkayabilisim in [60](https://github.com/TomorrowsCities/tomorrowscities/pull/60)
* ui: provide auto-resize metric panel by @o-z-e-r-e-r in [57](https://github.com/TomorrowsCities/tomorrowscities/pull/57)
* ui: moved "earthquake_intensity_unit" to ENGINE by @hkayabilisim in [61](https://github.com/TomorrowsCities/tomorrowscities/pull/61)
* ui: added progress bar during session upload by @hkayabilisim in [65](https://github.com/TomorrowsCities/tomorrowscities/pull/65)
* ui: added progress bar during session load by @hkayabilisim in [66](https://github.com/TomorrowsCities/tomorrowscities/pull/66)
* fix: refactored explore for indiv-based metrics by @hkayabilisim in [67](https://github.com/TomorrowsCities/tomorrowscities/pull/67)
* fix: center calculation is now in geometric by @hkayabilisim in [62](https://github.com/TomorrowsCities/tomorrowscities/pull/62)
* fix: remove pandas warning message by @hkayabilisim in [63](https://github.com/TomorrowsCities/tomorrowscities/pull/63)
* fix: remove metricX cols from building by @hkayabilisim in [64](https://github.com/TomorrowsCities/tomorrowscities/pull/64)

**Full Changelog**: [v0.4...v0.5](https://github.com/TomorrowsCities/tomorrowscities/compare/v0.4...v0.5)


**Changelog: v0.4**

* feature: switching to fine-level metrics by @hkayabilisim in [54](https://github.com/TomorrowsCities/tomorrowscities/pull/54)
* feature: disable lanslide option by @hkayabilisim in [52](https://github.com/TomorrowsCities/tomorrowscities/pull/52)
* feature: unit selection for earthquake intensities by @hkayabilisim in [50](https://github.com/TomorrowsCities/tomorrowscities/pull/50)
* feature: GEM fragility XML import by @hkayabilisim in [45](https://github.com/TomorrowsCities/tomorrowscities/pull/45)
* feature: GEM format for earthquake calculations by @hkayabilisim in [46](https://github.com/TomorrowsCities/tomorrowscities/pull/46)
* feature: power fragility displayer by @hkayabilisim in [48](https://github.com/TomorrowsCities/tomorrowscities/pull/48)
* ui: data import is the first tab in engine by @hkayabilisim in [53](https://github.com/TomorrowsCities/tomorrowscities/pull/53)
* fix: g-normalization in displayer is disabled by @hkayabilisim in [49](https://github.com/TomorrowsCities/tomorrowscities/pull/49)
* fix: corrected attribute list of power node by @hkayabilisim in [47](https://github.com/TomorrowsCities/tomorrowscities/pull/47)
* fix: add precheck for missing housholds by @hkayabilisim in [51](https://github.com/TomorrowsCities/tomorrowscities/pull/51)


**Full Changelog**: [v0.3...v0.4](https://github.com/TomorrowsCities/tomorrowscities/compare/v0.3...v0.4)

**Changelog: v0.3**

* Banner removed by @o-z-e-r-e-r in [13](https://github.com/TomorrowsCities/tomorrowscities/pull/13)
* Update on webapp header and requirements list by @o-z-e-r-e-r in [14](https://github.com/TomorrowsCities/tomorrowscities/pull/14)
* Update on engine page by @o-z-e-r-e-r in [15](https://github.com/TomorrowsCities/tomorrowscities/pull/15)
* Visual updates by @o-z-e-r-e-r in [18](https://github.com/TomorrowsCities/tomorrowscities/pull/18)
* Visual updates (02/02/24) by @o-z-e-r-e-r in [20](https://github.com/TomorrowsCities/tomorrowscities/pull/20)
* improvement: faster data loading by @hkayabilisim in [24](https://github.com/TomorrowsCities/tomorrowscities/pull/24)
* feature: added multiple file drop support by @hkayabilisim in [25](https://github.com/TomorrowsCities/tomorrowscities/pull/25)
* fix: refactor load for multiple file upload by @hkayabilisim in [26](https://github.com/TomorrowsCities/tomorrowscities/pull/26)
* feature: culvert support for flood+road by @hkayabilisim in [27](https://github.com/TomorrowsCities/tomorrowscities/pull/27)
* fix: assign zero to nodata locations in geotiff by @hkayabilisim in [28](https://github.com/TomorrowsCities/tomorrowscities/pull/28)
* fix: workaround for nonunique edge_id in nodes by @hkayabilisim in [29](https://github.com/TomorrowsCities/tomorrowscities/pull/29)
* feature: session save and load from explore page by @hkayabilisim in [30](https://github.com/TomorrowsCities/tomorrowscities/pull/30)
* Filter layout by @hkayabilisim in [31](https://github.com/TomorrowsCities/tomorrowscities/pull/31)
* feat: pre-compute checks by @hkayabilisim in [32](https://github.com/TomorrowsCities/tomorrowscities/pull/32)
* feat: added option to keep directions in graphs by @hkayabilisim in [34](https://github.com/TomorrowsCities/tomorrowscities/pull/34)
* feat: uniqueness check for landslide fragility by @hkayabilisim in [38](https://github.com/TomorrowsCities/tomorrowscities/pull/38)
* fix: uninitialized network object by @hkayabilisim in [39](https://github.com/TomorrowsCities/tomorrowscities/pull/39)
* ui: activate dataframe view and improve engine & explore page visualisations by @o-z-e-r-e-r in [37](https://github.com/TomorrowsCities/tomorrowscities/pull/37)
* Merge remote-tracking branch 'origin/main' into branch240401 by @hkayabilisim in [40](https://github.com/TomorrowsCities/tomorrowscities/pull/40)
* fix: reset existing index in input dataframes by @hkayabilisim in [41](https://github.com/TomorrowsCities/tomorrowscities/pull/41)
* feat: a pre-check if hospitals exist in building by @hkayabilisim in [42](https://github.com/TomorrowsCities/tomorrowscities/pull/42)
* Redefine population displacement by @hkayabilisim in [43](https://github.com/TomorrowsCities/tomorrowscities/pull/43)

**Full Changelog**: [v0.2.4_fix2...v0.3](https://github.com/TomorrowsCities/tomorrowscities/compare/v0.2.4_fix2...v0.3)

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
* Reorganized the folders in the [Sample Dataset](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view).
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
* Added dummy data to [Sample Dataset](https://drive.google.com/file/d/1HthdwrK0snqVUk0T_j2tHtLJoIyLFdKu/view) for Rapti.

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