---
author: huseyin.kaya
title: Flood Vulnerability Analysis
description: Methodologies in flood damage assessment
image: https://images.unsplash.com/photo-1429041966141-44d228a42775?ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=2500&q=80
thumbnail: https://images.unsplash.com/photo-1429041966141-44d228a42775?ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=350&q=80
alt: "Flood vulnerability analysis"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

The core component used in flood vulnerability analysis is to generate a mapping between water levels and relative damage on the structure. The shape of the curve depends on the typology of the structure, material type, height, code levels and many other features.

The Joint Research Centre (JRC) led by the European Commission provides technical reports and guidelines to generate damage curves [1]. It is also always possible to make minor modification for special cases such as single storey adobe buildings in Africa [2]. 

We provide a user interface to visualize and generate damages curves in [3].

## Remarks
* In both JRC [1] and modified version by Englhardt et.al [2],  the generated curves
do not depend on code levels of the structures. So any policy affecting code levels in flood damage assessment should find another way to change the damage states. See [policies](/docs/policies) for more information.


## References

* [1] Global flood depth-damage functions: Methodology and the database with guidelines, [link](https://publications.jrc.ec.europa.eu/repository/handle/JRC105688)
* [2] Englhardt, Johanna, et al. "Enhancement of large-scale flood risk assessments using building-material-based vulnerability curves for an object-based approach in urban and rural areas." Natural Hazards and Earth System Sciences 19.8 (2019): 1703-1722.  [link](https://nhess.copernicus.org/articles/19/1703/2019/nhess-19-1703-2019.pdf)
* [3] [Flood Vulnerability Generator](https://huggingface.co/spaces/hkayabilisim/flood_vulnerability_generator)
