import solara
from typing import Optional, cast
import pickle
import boto3
import os
from . import user, config

landslide_max_trials = solara.reactive(5)
threshold_flood = solara.reactive(0.2) 
threshold_flood_distance = solara.reactive(10)
threshold_road_water_height = solara.reactive(0.3) 
threshold_culvert_water_height = solara.reactive(1.5)
preserve_edge_directions = solara.reactive(False)
population_displacement_consensus = solara.reactive(2)

@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):

    with solara.Card(title='Metric-related Parameters',
                     subtitle='Minimum number of direct damage, inaccessibility or power lost should be observed to claim a population displacement.'):
        solara.Select(label='population displacement consensus', values=[1,2,3,4], value=population_displacement_consensus)

    with solara.Card(title='Connectivity Parameters',subtitle='Parameters effecting connectivity analysis in road/power networks'):
        solara.Checkbox(label='Preserve directions in graph edges', value=preserve_edge_directions)

    with solara.Card(title='Landslide Parameters',subtitle='Choose the parameters for the landslide simulation'):
        solara.SliderInt(label='Number of Monte-Carlo Trials', value=landslide_max_trials, min=1,max=100)

    with solara.Card(title='Flood Parameters',subtitle='Choose the parameters for the flood simulations'):
        solara.Markdown(md_text='''
                        If the relative damage obtained from the vulnerability curve is beyond 
                        the flood threshold, the structure is assumed to flooded.
                        After resetting the value, please execute the simulation again to see its effect.''')
        solara.SliderFloat(label='Flood Threshold (relative damage)', value=threshold_flood, min=0,max=1, step=0.1)
        solara.Markdown(md_text='''
                        If the distance from a structure to the nearest flood intensity measure
                        is greater than Flood Distance, then the structure is assumed to be
                        intact from flood.
                        After resetting the value, please execute the simulation again to see its effect.''')
        solara.SliderInt(label='Minimum Flood Distance Threshold (meters)', value=threshold_flood_distance, min=0,max=100)

        solara.Markdown(md_text='''
                        If the water level is beyond this threshold then the road 
                        is assumed to be flooded.''')
        solara.SliderFloat(label='Minimum Water Level Threshold for Roads (meters)', value=threshold_road_water_height, min=0,max=1)
        solara.Markdown(md_text='''
                        If the water level is beyond this threshold then the culvert 
                        hence the road containing it is assumed to be flooded.''')
        solara.SliderFloat(label='Minimum Water Level Threshold for Culverts (meters)', value=threshold_culvert_water_height, min=0,max=3)

    solara.Title(" ")