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
There are seven fundamental impact metrics displayed in the web application. For each them there is an associcated threhold but for the sake of simplicity, it is not explicitly stated.

### Metric 1: Number of workers unemployed
It denotes the number of invidivuals who last their jobs either due to a severe damage at the workplace 
or lost access to a functional workplace. When the metrics is displayed on a building-level, it is the sum of
such individuals living in that building.

### Metric 2: Number of children with no access to education
Similar to the first metrics but individual here refers to a child who is associated with a school.
The metric becomes active if the school is damaged or not accessible.

### Metric 3: Number of households with no access to hospital
The number of households who lost its access to its associated hospital.
Either hospital is damaged or the path between the household and the hospital
is broken.

### Metric 4: Number of individuals with no access to hospital
It is derived from metric 3 by counting the individuals in the corresponding households.

### Metric 5: Number of households displaced
It is direct result of building damage state. If a building is damaged, then the households in it are also
damaged.

### Metric 6: Number of homeless individuals
It is derived from metric 5.

### Metric 7: Population displacement
An individual is assumed to be displaced if the associated household is damaged, or he/she lost access to workplace, schoold or hospital. 