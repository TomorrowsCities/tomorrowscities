---
author: huseyin.kaya
title: Metrics
description: A brief introduction to impact metrics and implementation strategies
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/metrics.jpg?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/metrics.jpg?raw=true
alt: "Metrics"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Metrics
There are seven fundamental impact metrics displayed in the web application. 
Their calculations heavily depend on the damage state of buildings and/or other
infrastructural elements such as electrical power generators, roads or bridges. 

### Metric 1: Number of workers unemployed
It denotes the number of invidivuals who lost their jobs based on any of the following conditions:

* the associated workplace is damaged beyond a threshold
* the associated workplace has lost electricity
* the associated workplace can not be reached from the building that the individual lives in via
transportation network.

### Metric 2: Number of children with no access to education
Similar to the first metrics but individual here refers to individuals associated with a school.
This metric takes place when any of the following conditions holds:

* the school is damaged beyond a threshold
* the school has lost electricity
* the school can not be reached from the building that the individual lives in via
transportation network.

### Metric 3: Number of households with no access to hospital
The number of households who lost its access to its associated hospital.
Access is lost when any of the following conditions hold:

* the damage state of the associated hospital is beyond a threshold
* the associated hospital is inaccessible via transportation network
* the associated hospital has no electricity

### Metric 4: Number of individuals with no access to hospital
This metric is very similar to metric 3 except individual-hospital association
is used. In this metric, individual-hospital association is built upon household-hospital association.
An individual is said to lost his/her access to hospital when any of the conditions hold:

* the damage state of the associated hospital is beyond a threshold
* the associated hospital is inaccessible via transportation network
* the associated hospital has no electricity

### Metric 5: Number of households displaced
It is direct result of building damage state. If a building is damaged, then the households in it are also
damaged.

### Metric 6: Number of homeless individuals
It is derived from metric 5.

### Metric 7: Population displacement
An individual is assumed to be displaced when any of the following condition holds:

* the associated household is damaged
* the individual's workplace, school, or associated hospital is damageds
* the individual can not reach to workplace, school, or associated hospital via transportation network
* the individual's workplace, school, or associated hospital has no electricity

### Metric 8: Casualties

This metric counts unique people suffering direct physical injury or death. A fatality is part of the casualty total, not an additional person. It does not count displacement, all people in flooded buildings, or indirect illness after the event.

For **floods**, the default **people-risk-v1** model estimates harm separately from economic damage. Residents are distributed equally across the storeys in `expstr`; local depth on floor k is `max(depth - k * floor_height, 0)`. The hazard, area vulnerability and people vulnerability equations are adapted from Defra/EA FD2321/TR1. Occupancy, safe evacuation and additional safe shelter fractions adjust the population present. Dry upper floors have no direct inundation harm under the assumed stable-building conditions. DS thresholds and the uploaded economic vulnerability table do not gate this casualty estimate.

The default assumptions are **illustrative scenario inputs**, not measurements for Mumbai or another location: velocity 0 m/s, debris factor 0, area vulnerability 6, people vulnerability 0.25, floor height 3 m, full residential occupancy, and no evacuation or additional shelter. A depth raster alone cannot establish these conditions. See [Flood](/docs/flood) for formulas, limitations and the source. Review the assumptions in Calculation Parameters before interpreting results.

The model retains fractional expected casualties and expected fatal/nonfatal components in the building export. The displayed integer total rounds the stock-wide expectation once; largest remainders allocate people to buildings. Random selection then assigns that fixed building count to individuals without replacement. These identities are bookkeeping assignments, not predictions of which people will be harmed; age and illness are represented through an aggregate vulnerability parameter, not individual targeting. Expected severity components are not separately realised individual outcomes.

**Legacy-depth** remains available for comparison with earlier application results. It applies an uncalibrated depth curve to all residents in DS2+ buildings, truncates each building's count and holds the 6 m endpoint at 74.38%. Saved scenarios without a casualty model version load as legacy; selecting a different model requires rerunning the analysis. The result panel provides an assumptions download identifying the model that produced the current output.

For **earthquakes and landslides**, the existing building-damage-based casualty calculations are retained. This revision changes the default flood casualty method; it does not change those hazard calculations. Results are conditional on each scenario event, not annual average casualties.

## Average Impact Metrics in Monte-Carlo Simulations
When the hazard scenario is run with different random realizations such as landslide calculations,
then the impact metrics are calculated by taking average of all simulations. 
