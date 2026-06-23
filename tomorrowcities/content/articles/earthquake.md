---
author: erdem.ozer
title: Earthquake
description: How earthquake damage is calculated, how fragility data should be prepared, and what to check before analysis
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/earthquake.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/earthquake.png?raw=true
alt: "Earthquake fragility analysis"
createdAt: 2026-06-23
duration: 7 min read
category:
  - general
---

[TOC]

## Introduction
The earthquake workflow estimates building damage states by combining an exposure model, an earthquake intensity map, and fragility information. In practical terms, the app first assigns an intensity measure to each building, then matches that building to the corresponding fragility definition, and finally converts the resulting probabilities into a discrete damage state.

For buildings, the expected output is a damage state from **DS0** to **DS4**, where DS0 means no damage and DS4 represents collapse or complete damage. These damage states then feed downstream impact metrics such as casualties, displacement, and building damage summaries.

## How Earthquake Damage Is Calculated
For the standard tabular fragility workflow, the app builds a vulnerability string from the exposure model and matches it to the fragility table. The matching logic is based on:

* **material**
* **code level**
* **height class**

The engine then combines that matched fragility record with the assigned intensity measure and derives probabilities for DS1 to DS4. Depending on the selected simulation method:

* **Legacy** mode assigns the most likely damage state.
* **Monte Carlo** mode samples damage states probabilistically across multiple trials.

The app can work with:

* a single-band intensity measure such as **PGA** or **IM**
* multi-band spectral acceleration data such as **SA 0.30**, **SA 1.00**, etc.

If multi-band intensity data are used, the app interpolates the required spectral range before estimating building damage.

## Calculation Parameters in Engine
The **Calculation Parameters** panel on the Engine page includes a small set of earthquake-specific controls that directly affect how damage states are assigned:

* **Unit of earthquake intensity map**: this tells the app whether the uploaded intensity values are provided in **`m/s2`** or **`g`**. The engine normalizes the hazard values differently depending on this choice, so selecting the wrong unit can substantially overestimate or underestimate damage.
* **Earthquake simulation method**: you can choose between **Legacy** and **Monte Carlo**.
* **Legacy** mode converts the fragility probabilities into a single most-likely damage state for each building. This is useful when you want a stable, repeatable scenario result.
* **Monte Carlo** mode samples damage states probabilistically from the fragility curves. This is better suited to uncertainty exploration, but the realized DS counts can vary from run to run.
* **Number of trials**: when Monte Carlo is selected, the engine enables a trial count setting. Increasing the number of trials gives a broader simulation sample and can help stabilize aggregate summaries, but it also increases runtime.

These settings primarily affect **building damage state assignment**, and downstream metrics such as casualties, displacement, and DS summaries are then recalculated from those generated building damage states.

## Data Format for Earthquake Fragility
The standard tabular earthquake fragility format should contain one row per building class and include the following fields:

|expstr|med_slight|med_moderate|med_extensive|med_complete|beta_slight|beta_moderate|beta_extensive|beta_complete|
|------|----------|------------|-------------|------------|-----------|-------------|--------------|-------------|
|CR+LC+LR|0.18|0.28|0.42|0.62|0.55|0.55|0.55|0.55|
|MUR+MC+MR|0.10|0.16|0.24|0.34|0.60|0.60|0.60|0.60|
|W+LC+LR|0.07|0.12|0.18|0.25|0.65|0.65|0.65|0.65|

In this format:

* **expstr** is the building fragility class used for matching
* **med_\*** values are median intensity thresholds for each damage state
* **beta_\*** values are dispersion parameters

The tabular earthquake fragility format is primarily matched against the building-side earthquake fragility string assembled from the exposure data. In other words, fragility records must be consistent with the building classes produced or imported into the scenario.

## GEM XML Fragility Support
The app also supports **GEM fragility XML** input. When GEM XML is used:

* the fragility model is parsed into `fragilityFunctions`
* building exposure strings are matched to fragility function IDs
* only **discrete** GEM fragility functions are supported

This option is useful when you already work with GEM-style fragility models and want to preserve their intensity-measure definitions directly.

## Remarks
* The intensity map and the fragility model must be compatible. If the fragility data require spectral periods that do not exist in the intensity map, the analysis cannot be completed correctly.
* If you use **PGA** or a single `im` column, make sure the selected earthquake intensity unit matches the uploaded data.
* The app supports earthquake intensity unit selection in **`m/s2`** or **`g`**. Choosing the wrong unit can materially change the resulting damage states.
* For GEM XML workflows, only **discrete** fragility functions are supported at the moment.
* Fragility matching is only as good as the exposure classification. If material, code level, storey count, or occupancy assumptions are too coarse, the damage results should be interpreted as scenario-based estimates rather than exact real-world outcomes.
* In Monte Carlo mode, realized damage states can vary across trials. This is expected and is part of the uncertainty representation.

## What to Check Before Running
Before running an earthquake analysis, it is good practice to confirm:

* the building layer has the expected structural attributes
* the fragility file covers all exposure classes used in the scenario
* the intensity layer includes the required bands or columns
* the selected unit for earthquake intensity is correct
* the chosen simulation method reflects your intended use, whether deterministic-style overview or uncertainty exploration

## Parameter Tips
* Start with **Legacy** mode if you want a quick, stable first-pass result that is easy to compare across scenarios.
* Use **Monte Carlo** when you want to explore uncertainty and possible variation in DS outcomes rather than only the most likely state.
* If earthquake intensities were prepared from external hazard products, double-check whether they are stored in **`g`** or **`m/s2`** before running the analysis.
* If Monte Carlo results appear noisy at small map extents, increasing the number of trials can make aggregate summaries more stable.
* When comparing multiple earthquake scenarios, keep the unit and simulation settings consistent so that differences in outputs reflect hazard changes rather than parameter changes.

## References
* GEM Foundation resources on vulnerability and fragility modelling: [link](https://github.com/gem/global_vulnerability_model)
* OpenQuake / GEM fragility model conventions: [link](https://github.com/gem/oq-engine)
