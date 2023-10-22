from typing import Optional, cast
import solara
from solara.alias import rv
import dataclasses
import boto3
import os
import pickle
import pprint
from cryptography.fernet import Fernet

from ..data import articles

route_order = ["/", "docs","engine","utilities","settings","account"]

def check_auth(route, children):
    # This can be replaced by a custom function that checks if the user is
    # logged in and has the required permissions.

    # routes that are public or only for admin
    # the rest only requires login
    public_paths = ["/","docs","engine","utilities","account"]
    admin_paths = ["settings"]


    if route.path in public_paths:
        children_auth = children
    else:
        if user.value is None:
            children_auth = [LoginForm()]
        else:
            if route.path in admin_paths and not user.value.admin:
                children_auth = [solara.Error("You are not an admin")]
            else:
                children_auth = children
    return children_auth


class S3Storage:
    def __init__(self, aws_access_key_id, aws_secret_access_key, region_name, bucket_name):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.s3 = self.connect()
    def connect(self):
        session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        return session.client('s3')

    def is_alive(self):
        try:
            buckets = self.s3.list_buckets()
            for bucket in buckets['Buckets']:
                if bucket['Name'] == self.bucket_name:
                    return True
            return False
        except:
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

def get_S3(master_key:str, aws_access_key_id: str, aws_secret_access_key: str, region_name: str, bucket_name: str):
    fernet = Fernet(master_key)

    dec_aws_access_key_id = fernet.decrypt(aws_access_key_id).decode()
    dec_aws_secret_access_key = fernet.decrypt(aws_secret_access_key).decode()
    dec_region_name = fernet.decrypt(region_name).decode()
    dec_bucket_name = fernet.decrypt(bucket_name).decode()
    s3 = S3Storage(dec_aws_access_key_id, dec_aws_secret_access_key, dec_region_name, dec_bucket_name)
    s3.connect()
    return s3

def revive_storage():
    if 'master_key' in os.environ:
        print('reading storage from env')
        return get_S3(os.environ['master_key'],
                    os.environ['aws_access_key_id'],
                    os.environ['aws_secret_access_key'],
                    os.environ['region_name'],
                    os.environ['bucket_name'])
    return None
    

storage = solara.reactive(cast(Optional[S3Storage], revive_storage()))  






def storage_control(master_key:str, aws_access_key_id: str, aws_secret_access_key: str, region_name: str, bucket_name: str):
    fernet = Fernet(master_key)

    dec_aws_access_key_id = fernet.decrypt(aws_access_key_id).decode()
    dec_aws_secret_access_key = fernet.decrypt(aws_secret_access_key).decode()
    dec_region_name = fernet.decrypt(region_name).decode()
    dec_bucket_name = fernet.decrypt(bucket_name).decode()
    storage.value = S3Storage(dec_aws_access_key_id, dec_aws_secret_access_key, dec_region_name, dec_bucket_name)
    storage.value.connect()
    os.environ['master_key'] = master_key
    os.environ['aws_access_key_id'] = aws_access_key_id
    os.environ['aws_secret_access_key'] = aws_secret_access_key
    os.environ['region_name'] = region_name
    os.environ['bucket_name'] = bucket_name  

def storage_disconnect():
    storage.value = None

@dataclasses.dataclass
class User:
    username: str
    admin: bool = False


user = solara.reactive(cast(Optional[User], None))
login_failed = solara.reactive(False)


def login_control(username: str, password: str):
    # this function can be replace by a custom username/password check
    if username == "test" and password == "test":
        user.value = User(username, admin=False)
        login_failed.value = False
    elif username == "admin" and password == "admin":
        user.value = User(username, admin=True)
        login_failed.value = False
    else:
        login_failed.value = True


@solara.component
def LoginForm():
    username = solara.use_reactive("")
    password = solara.use_reactive("")
    with solara.Card("Login"):
        solara.Markdown(
            """
        This is an example login form.

          * use admin/admin to login as admin.
          * use test/test to login as a normal user.
        """
        )
        solara.InputText(label="Username", value=username)
        solara.InputText(label="Password", password=True, value=password)
        solara.Button(label="Login", on_click=lambda: login_control(username.value, password.value))
        if login_failed.value:
            solara.Error("Wrong username or password")



@solara.component
def Layout(children=[]):
    router = solara.use_context(solara.routing.router_context)
    route, routes = solara.use_route(peek=True)

    if route is None:
        return solara.Error("Route not found")
    
    children = check_auth(route, children)


    with solara.AppLayout(children=children, title="TomorrowCities Decision Support Environment", navigation=True) as main:
        with solara.AppBar():
            with solara.lab.Tabs(align="center"):
                for route in routes:
                    name = route.path if route.path != "/" else "Welcome"
                    is_admin = user.value and user.value.admin
                    # we could skip the admin tab if the user is not an admin
                    if route.path == "settings" and not is_admin:
                         continue
                    if user.value is not None and route.path == "logon":
                        continue
                    # in this case we disable the tab
                    solara.lab.Tab(name, path_or_route=route, disabled=False)
            if user.value:
                solara.Text(f"Logged in as {user.value.username} as {'admin' if user.value.admin else 'user'}")
                with solara.Tooltip("Logout"):
                    with solara.Link(f"/account"):
                        solara.Button(icon_name="mdi-logout", icon=True, on_click=lambda: user.set(None))
            else:
                with solara.Link(f"/account"):
                    solara.Button(icon_name="mdi-login",label='login', icon=True)

    
    return main


@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    css = """
    .v-input {
        height: 10px;
    }

    .v-application {
        font-family: Roboto,sans-serif;
        line-height: 1;
    }

    .v-btn-toggle:not(.v-btn-toggle--dense) .v-btn.v-btn.v-size--default {
        height: 24px;
        min-height: 0;
        min-width: 24px;
    }

    """
    solara.Style(value=css)
    with solara.VBox() as main:
        solara.Title("TCDSE » Welcome")
        article = articles["welcome"]
        solara.Markdown(article.markdown)


    return main
