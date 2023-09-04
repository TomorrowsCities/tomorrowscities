import gradio as gr
from tomorrowcities import DataGenerator
import warnings
import uuid
import os
import matplotlib.pyplot as plt


warnings.simplefilter(action='ignore')

plt.switch_backend("agg")

def generate(land_use_file, parameter_file, seed):
    oppath='.'
    dg = DataGenerator(parameter_file=parameter_file.name,
                    land_use_file=land_use_file.name)
    
    building, household, individual, land_use = dg.generate(seed)

    
    # Generate unique filenames
    opfile_map = 'map'+str(uuid.uuid4())+'.png'
    opfile_building = 'building_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_household = 'household_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_individual = 'individual_layer_'+str(uuid.uuid4())+'.xlsx'
    opfile_landuse =  'landuse_layer_'+str(uuid.uuid4())+'.xlsx'

    fig, ax = plt.subplots(1,1,figsize=(10,10))
    
    building.plot(ax=ax)
    plt.savefig(opfile_map)

    # Save to Excel files
    building.to_excel(os.path.join(oppath,opfile_building),index=False)
    household.to_excel(os.path.join(oppath,opfile_household),index=False)
    individual.to_excel(os.path.join(oppath,opfile_individual),index=False)
    land_use.to_excel(os.path.join(oppath,opfile_landuse),index=False)                                                                     

    info = f'# buildings: {len(building)}, # households: {len(household)}, # individuals: {len(individual)}'
    return opfile_building, opfile_household, opfile_individual, opfile_landuse, opfile_map, info

with gr.Blocks() as demo:
    with gr.Row():
        land_use_file = gr.File(label="Upload Land Use File")
        parameter_file = gr.File(label="Upload Parameter File")
        seed = gr.Slider(label="Seed", minimum=0, maximum=1000, value=0, step=1)
    btn = gr.Button("Generate")
    with gr.Row():
        with gr.Column():
            building = gr.File(label="Buildings")
            household = gr.File(label="Households")
        with gr.Column():
            individual = gr.File(label="Individuals")
            land_use = gr.File(label="Land Use")
        map = gr.Image(label="Map")
    info = gr.Textbox(label="Info")
    gr.Examples(examples=[['tests/polygonsTV50_v2b.zip','tests/Input_DistributionTables_20230614.xlsx',0]],
                inputs=[land_use_file, parameter_file, seed])

    btn.click(fn=generate, inputs=[land_use_file, parameter_file, seed], 
              outputs=[building, household, individual, land_use, map, info])

demo.launch()