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

### Metric 8: Casualty

This metric is calculated on building-level context meaning that it is directly related to the damage state of each building and the number of residents in that building.

## Average Impact Metrics in Monte-Carlo Simulations
When the hazard scenario is run with different random realizations such as landslide calculations,
then the impact metrics are calculated by taking average of all simulations. 
