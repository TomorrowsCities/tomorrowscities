---
author: o-z-e-r-e-r
title: How to Use the Web App
description: A practical guide to working with the Tomorrow's Cities web application
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/welcome.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/welcome.png?raw=true
alt: "How to Use the Web App"
createdAt: 2026-06-03
duration: 8 min read
category:
  - general
---

## How to Use the Web App

The Tomorrow's Cities web application is designed to help you prepare data, run hazard-impact calculations, inspect results on the map, and validate supporting datasets in one place.

If you are new to the platform, the simplest workflow is:

1. Prepare or generate your input data.
2. Open [Compute](/engine).
3. Load your files.
4. Select the infrastructure and hazard settings.
5. Run the calculation.
6. Review maps, tables, and metrics.

This guide reflects the current structure of the app and the latest public guidance from the project wiki.

If you would like additional walkthroughs, screenshots, or supporting notes about the application, you can also visit the project Wiki page: [How to use the Webapp](https://github.com/TomorrowsCities/tomorrowscities/wiki/2-%E2%80%90-How-to-use-the-Webapp).

## Know the Main Sections

The top navigation currently includes five main areas:

* [Home](/)
* [Compute](/engine)
* [Explore](/explore)
* [Utilities](/utilities)
* [Documentation](/docs)

Use them as follows:

* **Compute** is where you upload data, configure the scenario, run the analysis, and inspect outputs.
* **Explore** is for loading saved sessions and reviewing results interactively.
* **Utilities** provides data converters, validators, and template generators.
* **Documentation** gives detailed references for [data](/docs/data), [metrics](/docs/metrics), [policies](/docs/policies), and hazard-specific topics.

## Before You Start

Before opening the Compute page, make sure your files are prepared for the scenario you want to analyse.

A typical scenario may include:

* A hazard layer such as earthquake intensity, flood depth, or landslide intensity
* Exposure layers such as buildings, land use, households, individuals, roads, or power infrastructure
* A vulnerability or fragility dataset that matches the selected hazard
* Supporting network files such as road nodes, road edges, power nodes, or power edges when infrastructure analysis is included

Good preparation matters. Spatial files should align correctly on the map, and tabular files should contain the identifiers needed to connect households to buildings, individuals to households, and facilities to the relevant exposure layers.

For detailed format requirements, see [Data](/docs/data).

## Two Ways to Begin in Compute

The current app supports two practical starting points.

### Option 1: Upload existing analysis data

Open [Compute](/engine), then go to the **Data Import** tab and use **Upload Data**.

You can:

* Drag and drop files from your computer
* Click the upload area to browse local files
* Load sample files from cloud storage when that option is available in your environment

Supported inputs include Excel, GeoTIFF, JSON, GeoJSON, and GEM XML.

If you want to test the platform quickly, use the sample dataset linked from the app or the project documentation. A minimal earthquake-building workflow usually includes:

* building layer
* household layer
* individual layer
* hazard intensity layer
* fragility or vulnerability file

### Option 2: Generate exposure data first

If you do not already have building, household, and individual layers, use the exposure-generation workflow in the Compute page.

Upload:

* a parameter file
* a land-use file

Then click **Generate**. The app creates building, household, and individual layers for you, after which you can upload hazard and vulnerability data and continue with the main analysis.

This is especially useful when you are building a scenario from land-use information rather than importing a complete exposure package.

## Check Your Imported Data

After loading files, pause for a quick quality check before running the model.

In the current app, you can verify data in three ways:

* **Map view**: confirm that buildings, hazard layers, roads, power assets, and land-use polygons appear in the correct location
* **Map Info**: inspect loaded layer counts and feature details
* **Layer Details**: review data tables for both spatial and non-spatial datasets

A few practical checks go a long way:

* Make sure layers overlap correctly
* Confirm that expected columns are present
* Check that hazard data matches the fragility or vulnerability model you loaded
* Confirm that supporting road or power files are loaded if you selected those infrastructure types

If a file loads but does not behave correctly in the calculation, the issue is often a missing identifier, a mismatched attribute name, or an incorrect geometry/CRS setup.

## Configure the Analysis

Once the required data is loaded, move to the **Settings** tab in [Compute](/engine).

You will configure the scenario in this order:

### 1. Select infrastructure

The app currently lets you analyse one or more of:

* `building`
* `power`
* `road`

Choose only the infrastructure types supported by the data you have loaded.

### 2. Select hazard

The current hazard options include:

* `earthquake`
* `flood`
* `landslide`

Your hazard choice must match the input hazard layer and the vulnerability or fragility dataset.

### 3. Review calculation parameters

Open **Calculation Parameters** and check the scenario-specific settings before running the model.

Examples include:

* earthquake intensity unit
* earthquake simulation method
* flood thresholds
* flood depth reduction
* preserve edge directions for road and power networks
* landslide trigger level

If you are using earthquake data, pay special attention to the intensity unit. If you are using flood data, confirm that the water-depth thresholds fit your dataset and assumptions.

### 4. Optional: apply policies

The Compute page also includes a **Policies** selector. If you enable policies, the app exposes extra controls for the parameters affected by those interventions.

For policy definitions and interpretation, see [Policies](/docs/policies).

## Run the Calculation

When everything is ready, click **Calculate**.

During execution:

* wait for the progress bar to complete
* avoid refreshing the page
* avoid changing the loaded layers mid-run

Once the analysis finishes, the app updates:

* the map
* the layer data
* the summary metrics
* the metric statistics, when applicable

For some scenarios, the app also writes new output fields into the relevant layers, such as damage state, accessibility status, power availability, or impact-related attributes.

## Review the Results

The current app is strongest when you read results through all three lenses together: map, table, and metrics.

### Map

Use the map to understand where impacts occur.

You can:

* zoom to neighbourhood scale for detailed inspection
* click individual buildings, roads, or infrastructure assets
* compare input and output layers visually
* inspect feature attributes in **Map Info**

### Layer Details

Open **Layer Details** to inspect records in tabular form.

This is useful for:

* checking the new output columns created by the calculation
* confirming damage-state assignments
* reviewing infrastructure status changes
* exporting processed layers

The current app supports downloads from the details panel, including formats such as GeoJSON, JSON, and CSV depending on the layer type.

### Metrics and Metric Statistics

The impact widgets provide a fast summary of what the scenario means at system level. Use them to review totals, affected populations, damaged assets, access changes, and other derived outputs.

When reading metrics, remember one important detail: some results may depend on the current visible map extent. If you want the full-area picture, zoom out so the entire study area is visible.

For deeper interpretation of result indicators, see [Metrics](/docs/metrics).

## Save and Revisit Work

If session storage is available and you are signed in, the Compute page allows you to **Save Session**.

Saved sessions can then be opened in [Explore](/explore), where you can:

* load previous analyses
* inspect metadata
* review maps and metrics again
* apply filters for buildings, land use, and metrics

Explore is especially useful when you want to revisit a completed analysis without rebuilding the full scenario from scratch.

## Use Utilities to Prepare Better Inputs

The [Utilities](/utilities) page is a practical companion to Compute. It includes tools for common preparation and QA tasks such as:

* `Excel -> GeoJSON` conversion
* `JSON -> CSV` conversion
* `CSV -> JSON` conversion
* flood vulnerability template generation
* land-use and exposure validation
* hazard-data validation
* vulnerability and fragility validation

If your data is not loading as expected, Utilities is often the fastest place to diagnose the issue before returning to Compute.

## Recommended First Run

If you want a clean first experience:

1. Start with the sample dataset.
2. Open [Compute](/engine).
3. Upload the required building, household, individual, hazard, and fragility or vulnerability files.
4. Select the matching infrastructure and hazard.
5. Run **Calculate**.
6. Review the map, metrics, and layer exports.

After that, move on to your own case-study data.

## Troubleshooting Tips

If results do not appear as expected, check the following:

* The hazard type matches the loaded hazard layer and vulnerability or fragility data.
* All required supporting layers are present for the selected infrastructure.
* Key identifiers between datasets are complete and consistent.
* Spatial layers align correctly on the map.
* Earthquake units and flood thresholds are configured correctly.
* The dataset loaded successfully but was not misclassified due to missing or unusual column names.

When in doubt, validate the inputs in [Utilities](/utilities) and compare your files with the requirements in [Data](/docs/data).

## In Short

Use **Compute** to build and run scenarios, **Explore** to revisit saved analyses, **Utilities** to prepare and validate data, and **Documentation** to understand the underlying data structures, metrics, and policies. With the right inputs and a quick validation step before calculation, the app becomes a fast and reliable environment for hazard-impact analysis.
