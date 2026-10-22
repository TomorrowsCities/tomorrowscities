---
author: huseyin.kaya
title: Flood
description: How flood damage is calculated, how vulnerability data should be prepared, and which Engine parameters matter most
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/flood.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/flood.png?raw=true
alt: "Flood vulnerability analysis"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Introduction
The core component used in flood vulnerability analysis depends on a mapping between water levels and relative damage on the structure. The shape of the curve depends on the typology of the structure, material type, height, code levels and the occupancy type. The Joint Research Centre (JRC) led by the European Commission provides technical reports and guidelines to generate such damage curves [1]. It is also always possible to make minor modification for special cases such as single storey adobe buildings in Africa [2,3]. 

## How Flood Damage Is Calculated
For buildings, the app assigns a flood depth to each exposed asset from the nearest hazard information and then matches the building exposure string to the corresponding flood vulnerability curve. The vulnerability curve converts water depth into a **relative damage** value between 0 and 1.

That relative damage is then translated into a discrete damage state:

* **DS0** for no damage
* **DS1** for flooded / slight damage
* **DS2** for moderate damage
* **DS3** for extensive damage
* **DS4** for complete damage

The DS assignment is controlled by the thresholds configured in Engine. As a result, the same flood depth can lead to different DS summaries if those thresholds are changed.

These categories are bins of economic damage ratio, not measured structural collapse probabilities. Human injury is calculated separately; changing only DS thresholds does not change the default casualty estimate.

## Hazard Units and Spatial Assignment

Building flood depths must be in **metres above ground**. GIRI centimetre rasters must be divided by 100 before upload; the TIFF importer does not automatically convert units. Do not convert an already prepared metre raster again. TIFF upload represents nonzero cells by centre points and assigns the nearest point to each building polygon, with the configured distance cutoff. This spatial method is unchanged by the casualty revision; a coarse raster and a small cutoff can exclude buildings within a wet cell.

Road flood assignment uses the original TIFF cell boundaries retained at import: an edge receives the maximum depth among intersected cells. For point-only inputs without raster grid metadata, roads use the nearest measurement within the configured distance cutoff. Re-upload the original TIFF to rerun older scenarios with cell-based road exposure. Building assignment and casualty calculations are unchanged by this road correction. See [Road Network Analysis](/docs/road) for edge closure and bridge assumptions.

## Data Format for Flood Vulnerability
Flood vulnerability is a tabular data example of which is shown below: 

|expstr	|hw0	|hw0_5	|hw1	|hw1_5	|hw2	|hw3	|hw4	|hw5	|hw6 |
|-------|-----|-------|-----|-------|-----|-----|-----|-----|----|
|BrCfl+LC+1s+Res	|0.000	|0.660	|0.980	|1.000	|1.000	|1.000	|1.000	|1.000	|1.000
|S/LFM+DUM+LC+2s+Com	|0.000	|0.330	|0.490	|0.620	|0.720	|0.870	|0.930	|0.980	|1.000
|BrCfl+HC+3s+Res	|0.000	|0.220	|0.327	|0.413	|0.480	|0.580	|0.620	|0.653	|0.667

The exposure string in the first column (**expstr**) contains four components separeted by '+' symbol: material type, code level, number of storeys and the occupancy. The material type can also contain '+' symbol, therefore parsing is done from right to left. In the example below, for instance, the material type of the second curve is 'S/LFM+DUM'.

The tabular data can be provided to engine in two formats: Microsoft Excel or JSON both of which is ok. However, if 
there are thousands of records in your data, we recommend JSON since importing a JSON is much faster than importing a Microsoft Excel.

Each exposure class must have one finite, nondecreasing curve within [0, 1], starting at zero. Optional deeper knots such as `hw9` or `hw12_5` are supported. Between knots, interpolation is linear. Beyond the last knot, its damage ratio is held rather than jumping to total loss. These are economic vulnerability curves, not human injury curves.

## Flood Casualties

**people-risk-v1** replaces the default anonymous depth-only casualty curve with a provisional adaptation of the Defra/Environment Agency Flood Risks to People equations [4]. Fatalities are a subset of the combined harm cohort, so each casualty is counted once.

For each floor, `d = max(h - k*H, 0)` and `HR = d*(v+0.5)+DF`, with HR zero on dry floors. The exposed fraction is `X = clip(HR*AV/100, 0, 1)` and the harm fraction is `Y = clip(2*PV, 0, 1)`. Expected combined casualties are `sum(N_present/F * X * Y)`. Expected fatalities are the subset `sum(harm_on_floor * clip(2*HR/100, 0, 1))`; expected nonfatal injuries are the difference. Here PV is a fraction-based score: fraction aged 75+ plus fraction with long-term illness, potentially overlapping.

`N_present = residents * occupancy * (1-evacuated) * (1-sheltered)`. Residents are spread equally over F storeys, using an assumed floor spacing H. Shelter is an **additional safely protected fraction of remaining occupants**, separate from the dry upper floors already represented. Avoid representing the same evacuation or shelter benefit again in AV. The result is independent of economic DS thresholds.

### Scenario Assumptions

Calculation Parameters exposes velocity, debris factor, AV, PV, floor spacing, occupancy, safe evacuation and safe shelter. Defaults are velocity **0 m/s**, debris **0**, AV **6**, PV **0.25**, spacing **3 m**, occupancy **1**, evacuated **0**, sheltered **0**. AV and PV are illustrative sensitivity inputs, not regional demographic findings. AV is the sum of warning, onset and area scores; it ranges from 3 to 9. A depth map cannot determine these settings. In particular, zero velocity is an assumed still-water scenario, not an estimate of unobserved flow.

This is an application adaptation, **not a locally validated forecast or the complete official methodology**. Floor allocation, explicit population reductions, fraction bounds and integer allocation are application choices. Upper floors are assumed structurally stable and habitable; collapse, basements, flood duration, rapid rise, breach dynamics and actual occupant locations are excluded. Non-resident workers/students and indirect health effects are not included. Validate locally and vary the assumptions before using these outputs for decisions. Economic DS4 does not establish collapse or invalidate shelter automatically.

Exports contain `casualty_expected`, `fatalities_expected`, `injuries_nonfatal_expected`, `people_at_risk_expected`, `casualty_probability` and `casualty_model`. The integer total is rounded once across the building stock and allocated by largest remainders. The result panel downloads the version and assumptions used for the last run. [Metric 8](/docs/metrics) explains assignment to individual records. Two return periods alone do not establish annual average casualties.

### Legacy Compatibility

Select **legacy-depth** only to reproduce the previous application baseline: economic DS2+ gating, the previous depth curve, per-building truncation and a 74.38% endpoint at 6 m and above. This reproduces the corrected baseline, not the earlier bug that jumped to 100% above 6 m. Saved scenarios without a model version retain legacy interpretation until rerun. Earthquake, landslide, road and power calculations are unchanged by this casualty model.

## Calculation Parameters in Engine
The **Calculation Parameters** panel on the Engine page includes several flood-specific settings. These parameters are important because they control how hazard values are interpreted and how relative damage is converted into damage states.

* **Minimum Flood Damage State 2 Threshold**: the minimum relative damage value required for a building to be assigned **DS2** instead of **DS1**.
* **Minimum Flood Damage State 3 Threshold**: the minimum relative damage value required for a building to be assigned **DS3** instead of **DS2**.
* **Minimum Flood Damage State 4 Threshold**: the minimum relative damage value required for a building to be assigned **DS4** instead of **DS3**.
* **Minimum Flood Distance Threshold (meters)**: if a building is farther than this distance from the nearest flood hazard record, the app treats the building as outside the effective flood influence and sets the local flood intensity to zero.
* **Minimum Water Level Threshold for Roads (meters)**: for road network analysis, non-bridge road segments are marked as damaged when flood depth exceeds this threshold.
* **Minimum Water Level Threshold for Culverts (meters)**: for road network analysis, culvert segments are marked as damaged when flood depth exceeds this threshold.

In practice, the first three thresholds shape the **building DS distribution**, while the distance and infrastructure thresholds affect which exposed assets are considered impacted at all. This means these settings can change not only building counts by DS level, but also downstream accessibility and network-related metrics when transport infrastructure is included in the scenario.

## Remarks
* In both JRC [1] and modified version by Englhardt et.al [2],  the generated curves
do not depend on code levels of the structures. So any policy affecting code levels in flood damage assessment should find another way to change the damage states. See [policies](/docs/policies) for more information.
* Because flood DS categories are threshold-based in the app, it is worth reviewing the Engine parameter values before comparing two scenarios. Different threshold choices can produce different DS totals even when the underlying flood depths are unchanged.

## Parameter Tips
* Keep the **DS2**, **DS3**, and **DS4** thresholds in ascending order so that damage states remain logically separated.
* Lower DS thresholds will generally produce more moderate-to-severe damage states, while higher thresholds will make the same vulnerability curves appear less severe.
* If the hazard layer is sparse or generalized, review the **Minimum Flood Distance Threshold** carefully because a very large value can spread hazard influence too far from the mapped flood locations.
* The **road** and **culvert** water level thresholds are especially important when accessibility or transport disruption metrics are part of the analysis.
* When comparing two flood scenarios, try to keep these parameters unchanged unless your purpose is specifically to test sensitivity to threshold choices.


## References

* [1] Global flood depth-damage functions: Methodology and the database with guidelines, [link](https://publications.jrc.ec.europa.eu/repository/handle/JRC105688)
* [2] Englhardt, Johanna, et al. "Enhancement of large-scale flood risk assessments using building-material-based vulnerability curves for an object-based approach in urban and rural areas." Natural Hazards and Earth System Sciences 19.8 (2019): 1703-1722.  [link](https://nhess.copernicus.org/articles/19/1703/2019/nhess-19-1703-2019.pdf)
* [3] [Flood Vulnerability Generator](https://huggingface.co/spaces/hkayabilisim/flood_vulnerability_generator)
* [4] Defra / Environment Agency, HR Wallingford et al. (2006), *Flood Risks to People, Phase 2: FD2321/TR1*, sections 3.5, 5.4 and 6. [Technical report](https://assets.publishing.service.gov.uk/media/602bbc768fa8f50383c41f80/Flood_risks_to_people_-_Phase_2_The_flood_risks_to_people_methodology_technical_report.pdf). Crown copyright; source acknowledged. Used here with the application adaptations described above.
