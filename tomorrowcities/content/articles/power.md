---
author: huseyin.kaya
title: Power Network Analysis
description: How to conduct power network analysis in Tomorrowville
image: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/power.png?raw=true
thumbnail: https://github.com/TomorrowsCities/tomorrowcities/blob/main/tomorrowcities/content/images/power.png?raw=true
alt: "Power Network Analysis"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

[TOC]

## Power Infrastructure Analysis


### Data
**Power Nodes**

node_id|pwr_plant|n_bldgs|eq_vuln|geometry|
|-------|---------|-------|-------|--------|
|1      |1        |None   |None   |POINT (36.80602 -1.31293)|
|2      |0        |0      |ESS1   |POINT (36.80302 -1.36646)|
|3      |0        |3      |ESS2   |POINT (36.80302 -1.36646)|

**node_id** is a unique identifier for electrical power node.
**pwr_plant** indicates that the power node is a generator/power source
when it is set to 1 or True.
**n_bldgs** is used for the nodes which distributes electricity to the
neighboring building. If this attribute is a positive value then it will used
to distribute power to the neighbors. Such nodes are called *server* nodes.
**eq_vuln** is the taxonomy string used for the structural power node building.
When not specified, the node is assumed to be immune to hazards. Finally comes
the geometry column which is simple a point coordinate in WGS84 coordinate
reference system.

**Power Edges**
The minimum required attributes of the edges is shown below:

|edge_id|from_node|to_node|geometry|
|---------|-------|-------|--------|
|1        |2      |1   |LINESTRING (82.61515 27.80731, ...|
|2        |3      |1   |LINESTRING (82.72634 27.68782, ...|
|3        |1      |2   |LINESTRING (82.06824 27.80731, ...|

where **edge_id** is the unique identifier of the transmission line between any two nodes.
**from/to_node** attributes define the starting and ending nodes of the transmission line.
Finally comes the geometry as a line string. For transmission lines, no taxonomy information
is required.

**Power Fragility**
The fragility functions for the power node structures are defined as a tabular tabular data whose
attributes are shown below.

| vuln_string  |med_Slight | med_Moderate | med_Extensive | med_Complete | beta_Slight | beta_Moderate | beta_Extensive | beta_Complete |                                       description|
|--------------|-----------|--------------|---------------|--------------|-------------|---------------|----------------|---------------|--------------------------------------------------|
|       ESS1   |    0.15   |       0.29   |        0.45   |       0.90   |      0.70   |        0.55   |         0.45   |        0.45   | Low Voltage (115 KV) Substation (Anchored/Seis...|
|       ESS2   |    0.13   |       0.26   |       0.34    |      0.74    |     0.65    |       0.50    |        0.40    |       0.40    | Low Voltage (115 KV) Substation (Unanchored/St...|
|       ESS3   |    0.15   |       0.25   |       0.35    |      0.70    |     0.60    |       0.50    |        0.40    |       0.40    | Medium Voltage (230 KV) Substation (Anchored/S...|

**vuln_string** of the fragility curves should match **eq_vuln** field of the power nodes. Median and beta values of four fragility curves (slight, moderate, extensive and complete) are defined
in the same row. It is optional to add a description message.

### Additional Auxillary Attributes
As soon as the power network analysis is conducted, 
the engine creates internal attributes tagged to building and household layers
which will be visible in LayerDisplayer. The name of the additional attribute is
*has_power* which is a boolean variable. When used in the building layer, it indicates
if a building has power or not. The same attribute is also used in household layer
which indicates the associated building has power.
