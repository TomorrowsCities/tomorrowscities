from typing import Optional
import solara
import os
import pprint

from . import user
from . import LoginForm
from . import storage, storage_control, storage_disconnect
from .engine import layers, load_from_state

@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    aws_access_key_id = solara.use_reactive('gAAAAABlNYcieCqS_iKRhX_J4LXea2hZ7UOqml4ebclJuGJaNpf0h_vOIYiYqLvPmHly8y8hcxBYr-_YUroLb5UG95xpPYTMjEhH_roobgY7hd7hTxJ9mB4=')
    aws_secret_access_key = solara.use_reactive('gAAAAABlNYeL1SvCXf6DePlh2I6U_rrd9Izv1QlR6U9eev00bloKdUApf1r29l3UUh6G1PS9DagGLF228f3peWCrWdgZgT_-gUV3ueV6nHR9_QERYCWr0iaAUpcmqPVzIy81ESHqNZ2Z')
    master_key = solara.use_reactive('')
    region_name = solara.use_reactive('gAAAAABlNYfC41QcaN-_OwD0XwHGOY8BD38YtNXlvd8dWT74aUoLeERtw1OADP_jIKMqDAqvRMnoioqHONI6-um3NCeKlbG2rw==')
    bucket_name = solara.use_reactive('gAAAAABlNYfYJwQCh6S9bO2npj7Qd1r9riEsGHxw6LAK5xz1DreQv7cpHdmepFtLhB8DlNDEKRDsRsFXD9zRPVMMc5JDcYiMQQ==')

    session_name = solara.use_reactive(None)
    session_list = solara.use_reactive([])


    


    def load_selected_session():
        data = storage.value.load_data(session_name.value)
        pprint.pprint(data)
        load_from_state(data)

    def refresh_session_list():
        session_list.set(sorted(storage.value.list_sessions(),reverse=True))

    #for k in ['aws_access_key_id', 'aws_secret_access_key','region_name','bucket_name']:
    #    solara.Text(f'{k} --> {os.environ[k]}')
    solara.Title("TCDSE » Account")
    if user.value is None:
        LoginForm()
    else:    
        if storage.value is None:
            with solara.Card(title='Attaching AWS S3',subtitle='Please attach an S3 bucket to save workspace sessions'):
                solara.InputText(label='Master Key',value=master_key, password=True)
                solara.InputText(label='AWS Access Key ID', value=aws_access_key_id, password=True,disabled=True)
                solara.InputText(label='AWS Secret Access Key', value=aws_secret_access_key,password=True,disabled=True)
                solara.InputText(label='AWS Region Name', value=region_name,password=True,disabled=True)
                solara.InputText(label='Bucket Name', value=bucket_name,password=True,disabled=True)
                solara.Button(label="Connect to S3", 
                            on_click=lambda: storage_control(master_key.value, aws_access_key_id.value, 
                                                            aws_secret_access_key.value, 
                                                            region_name.value,
                                                         bucket_name.value))
        else:
            with solara.Card(title='Load Session', subtitle='Choose a session from storage'):
                solara.Select(label='Choose session',value=session_name.value, values=session_list.value,
                            on_value=session_name.set)
                solara.Button(label="Load", on_click=lambda: load_selected_session())
                solara.Button(label="Refresh", on_click=lambda: refresh_session_list())
            solara.Button(label="Disconnect from S3",on_click=lambda: storage_disconnect())

