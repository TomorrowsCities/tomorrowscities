---
author: huseyin.kaya
title: Policies in a nutshell
description: A brief introduction to policies
image: https://images.unsplash.com/photo-1429041966141-44d228a42775?ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=2500&q=80
thumbnail: https://images.unsplash.com/photo-1429041966141-44d228a42775?ixid=MXwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHw%3D&ixlib=rb-1.2.1&auto=format&fit=crop&w=350&q=80
alt: "Policies"
createdAt: 2023-10-10
duration: 6 min read
category:
  - general
---

### Policy 1: Land and tenure security program
When this policy applied, the code levels of the residential buildings are set to higher standards 
which effectively reduces the damage states during hazard simulations. Since this policy only changes
the code levels, the computing engine is required to run again whevener this policy is applied.

There could be cases where the damage curves used to assess the vulnerability do not depend on code levels.
Flood damage curves, for instance, fall into this category. In such a case, we opt to increase the
height of buildings by addingt two storeys to work witk more suppressed damage curves.
Please note that, the scope of this change is only a temporary one and is bound only to flood damage calculation. 


### Policy 2: State-led upgrading/retrofitting of low-income/informal housing
When applied, this policy increase the code level of the buildings located in low income A and B zones.
This effectively reduces the damage states, and hence several impact metrics, starting from building-level
metrics. 

Similar to policy 1, if the code level is not used in damage assessment other features are used 
to increase the stability of the structure. For instance, for flood calculations, the height of the structures
are increased by 2 storeys.

### Policy 3: Robust investment in WASH (water, sanitation and hygiene) and flood-control infrastructure 
When applied the expected outcome is exposure and Social Vulnerability reduction - decreased diseases, 
casualties and other losses and damages in the event of floods due to better water and sewage management. 

Since the effect of this policy is very dramatic, 6 storeys are added.

### Policy 4: Investments in road networks and public spaces through conventional paving
Expected outcome: Exposure reduction - better mobility and more escape routes during hazard events. 
Since the transportation network analysis is not done yet, we choose to improve the special
facilities to mimic the stability of road networks.  In other works for flood hazard type, we decrese 
the damage curve value for special facilities by increasing the height of the structures.

### Policy 5: Shelter Law - All low-income and informal settlements should have physical and free access to community centres and shelters
Expected outcome: Social Vulnerability reduction - reducing the effects of displacement and other issues such as food insecurity. 
Concerns: Implementation/Enforcement – evidence that some shelters remain unfunded or little effective despite their physical existence 
In implementation, we filter residential buildings in low income regions, and slight increase the height levels.

### Policy 6: Funding community-based networks in low-income areas (holistic approaches)
Expected outcome: Social Vulnerability reduction - meeting diverse emergency needs
Concerns: Implementation/Enforcement – funds could not be available as soon as hazards hit, decreasing their effectivity. Not certain how groups would allocate funding. 
Implementation: filter non 
In implementation, we filter commercial buildings in low income regions, and slight increase the height levels.

### Policy 7: Urban farming programs 
Expected outcome: Exposure Reduction - reserve of % of land to urban farming (by residents) in hazard-prone areas. Social Vulnerability reduction due to improved food security. 
Concerns: Equity – who would benefit from policy in practice and have access to produce

In implementating this policy, we change the occupancy type of 30% of the residulual buildings
into agriculture. So the damage curves for the agricultural areas is much lower than residental types.

### Policy 8: Emergency cash transfers to vulnerable households
Expected outcome: Social Vulnerability reduction - strengthening of economic capacity. 
Concerns: Implementation/Enforcement – funds could not be available as soon as hazards hit, decreasing their effectivity. Equity – ‘invisible residents’ (e.g., migrants) would lose benefit. 
Implementation: damage curves of non-special buildings are suppressed.

### Policy 9: Waste collection and rivers cleaning program 
Expected outcome: Social Vulnerability reduction – reduced risk of diseases and other negative effects of waste mixed with water runoff
Concerns: Implementation/Enforcement – policy could take a long time to generate meaningful results. Not clear if effective in the immediate aftermath of a flood
Implementation: damage curves of every structure in the visioning scenarios are moderately suppressed.

## Policy 10: Enforcement of environmental protection zones
Expected outcome: Reduced exposure in hazard-prone or environmentally sensitive areas
Concerns: Equity – increased land prices or displacement of informal settlers in environmentally sensitive areas
Implementation: some random subset of buildings are assigned as agriculture mimiching to create protected zones.

