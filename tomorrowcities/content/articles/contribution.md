---
author: huseyin.kaya
title: Contributing
description: A step-by-step guideline for contributors
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/contribute.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/contribute.png?raw=true
alt: "Contributing"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Adding a new layer

On top of the **engine.py**, there is a reactive variable caller **layers**
to contain all information about the layers. You can add a new layer to that
variable. Here we provide an example.

```python
layers = solara.reactive({
    # ... 
    'layers' : {
        'landslide susceptibility': {
            'render_order': 50,
            'map_info_tooltip': 'Number of zones in the susceptibility map',
            'data': solara.reactive(None),
            'map_layer': solara.reactive(None),
            'force_render': solara.reactive(False),
            'visible': solara.reactive(False),
            'pre_processing': identity_preprocess,
            'extra_cols': {},
            'attributes_required': [set(['id','susceptibility','geometry'])],
            'attributes': [set(['id','susceptibility','geometry'])]},
    #...
```

The above step is the minimum requirement of importing data and visualizing 
on the map. If you need extra stuff for visualization, then edit **create_map_layer** function.

## Adding a new Hazard
Add your hazard to application state:

```python
app_state = solara.reactive({
    #...
    'hazard_list': ["earthquake","flood","landslide"],
    #...
```

Update **is_ready_to_run** to add the required layers for your hazard.

Update **execute_engine** to include the relation with your hazard and infrastructure type.
For each instrastructure type, you'll see dedicated functions such as **execute_road**,
or **execute_power**, etc. Inside each one, make sure you load the necessary data
before calling the backend.