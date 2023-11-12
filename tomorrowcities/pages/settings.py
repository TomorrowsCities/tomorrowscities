import solara
from typing import Optional, cast
import pickle
import boto3
import os

from . import user

class S3Storage:
    def __init__(self, aws_access_key_id, aws_secret_access_key, region_name, bucket_name):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.s3 = self._connect()

    def _connect(self):
        session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        return session.client('s3')

    def is_alive(self):
        print(self.aws_access_key_id)
        print(self.aws_secret_access_key)
        print(self.region_name)
        print(self.bucket_name)
        buckets = self.s3.list_buckets()
        for bucket in buckets['Buckets']:
            if bucket['Name'] == self.bucket_name:
                return True
        return False

        
    def upload_file(self, file_name, object_name=None):
        if object_name is None:
            object_name = file_name
        self.s3.upload_file(file_name, self.bucket_name, object_name)
        return f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}"

    def load_metadata(self, session_name):
        # Use the get_object method to read the file
        self.s3.download_file(self.bucket_name, f'{session_name}.metadata', f'/tmp/{session_name}.metadata')

        with open(f'/tmp/{session_name}.metadata', 'rb') as fileObj:
            # Access the content of the file from the response
            metadata = pickle.load(fileObj)

        print(type(metadata))

        return metadata
    
    def load_object(self, object_name):
        # Use the get_object method to read the file
        self.s3.download_file(self.bucket_name, object_name, f'/tmp/{object_name}')
        print(f'Downloading {object_name}')

        with open(f'/tmp/{object_name}', 'rb') as fileObj:
            # Access the content of the file from the response
            data = pickle.load(fileObj)
        return data
    
    def load_data(self, session_name):
        return self.load_object(f'{session_name}.data')
    
    def list_objects(self): 
        objects = self.s3.list_objects(Bucket=self.bucket_name)
        objects_array = set()
        for obj in objects.get('Contents', []):
            objects_array.add(obj["Key"].split('.')[:-1][0])
        return [a for a in objects_array]
    
    def list_sessions(self):
        objects = self.list_objects()
        return [o for o in objects if "TCDSE_SESSION" in o]

def revive_storage():
    if 'aws_access_key_id' in os.environ:
        print('reviving storage from env')
        return S3Storage(
                    os.environ['aws_access_key_id'],
                    os.environ['aws_secret_access_key'],
                    os.environ['region_name'],
                    os.environ['bucket_name'])
    
storage = solara.reactive(revive_storage())  

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
    #else:
    #    StorageViewer()

    if err_message != '':
        solara.Error(err_message)