import solara
from typing import Optional, cast
import pickle
import boto3
import os
from . import user, S3Storage



def revive_storage():
    if 'aws_access_key_id' in os.environ:
        print('reviving storage from env')
        return S3Storage(
                    os.environ['aws_access_key_id'],
                    os.environ['aws_secret_access_key'],
                    os.environ['region_name'],
                    os.environ['bucket_name'])
    
storage = solara.reactive(revive_storage())  
landslide_max_trials = solara.reactive(5)

threshold_flood = solara.reactive(0.2) 
threshold_flood_distance = solara.reactive(10)
threshold_road_water_height = solara.reactive(0.3) 
threshold_culvert_water_height = solara.reactive(1.5)

def storage_control(aws_access_key_id: str, aws_secret_access_key: str, region_name: str, bucket_name: str):
    storage.value = S3Storage(aws_access_key_id, aws_secret_access_key, region_name, bucket_name)


def storage_disconnect():
    print('Disconnecting S3')
    storage.set(None)
    session_name.set(None)
    session_list.set([])
    os.environ.pop('aws_access_key_id')
    os.environ.pop('aws_secret_access_key')
    os.environ.pop('region_name')
    os.environ.pop('bucket_name')
    if 'aws_access_key_id' in os.environ.keys():
        print('After removing',os.environ['aws_access_key_id'])

session_name = solara.reactive(None)
session_list = solara.reactive([])

def refresh_session_list():
    session_list.set(sorted(storage.value.list_sessions(),reverse=True))

@solara.component
def StorageViewer():
    with solara.Card(title='Load Session', subtitle='Choose a session from storage'):
            solara.Select(label='Choose session',value=session_name.value, values=session_list.value,
                        on_value=session_name.set)
            solara.Button(label="Refresh", on_click=lambda: refresh_session_list())


@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    aws_access_key_id = solara.use_reactive('')
    aws_secret_access_key = solara.use_reactive('')
    region_name = solara.use_reactive('eu-west-3')
    bucket_name = solara.use_reactive('tcdse')
    err_message, set_err_message = solara.use_state('')

    def connect_storage(aws_access_key_id,
                        aws_secret_access_key, 
                        region_name,
                        bucket_name):
        print('connecting to s3')
        try:
            print(aws_access_key_id, aws_secret_access_key, region_name, bucket_name)

            s3 = S3Storage(aws_access_key_id, aws_secret_access_key, region_name, bucket_name)
            if s3.is_alive():
                storage.value = s3
                # Save for later to revive storage
                os.environ['aws_access_key_id'] = aws_access_key_id
                os.environ['aws_secret_access_key'] = aws_secret_access_key
                os.environ['region_name'] = region_name
                os.environ['bucket_name'] = bucket_name  
            set_err_message('')
        except Exception as e:
            set_err_message(str(e))
            print(e)

    if storage.value is None:
        s3_object = revive_storage()
        if s3_object is not None and s3_object.is_alive():
            storage.set(s3_object)
            StorageViewer()
        else:
            with solara.Card(title='Attaching AWS S3',subtitle='Please attach an S3 bucket to save workspace sessions'):
                solara.InputText(label='AWS Access Key ID', value=aws_access_key_id, on_value=aws_access_key_id.set)
                solara.InputText(label='AWS Secret Access Key', value=aws_secret_access_key,password=True, on_value=aws_secret_access_key.set)
                solara.InputText(label='AWS Region Name', value=region_name,on_value=region_name.set)
                solara.InputText(label='Bucket Name', value=bucket_name, on_value=bucket_name.set)
                solara.Button(label="Connect to S3", 
                            on_click=lambda: connect_storage(aws_access_key_id.value, 
                                                            aws_secret_access_key.value, 
                                                            region_name.value,
                                                            bucket_name.value))
    else:
        StorageViewer()

    if err_message != '':
        solara.Error(err_message)

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