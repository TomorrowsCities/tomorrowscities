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

route_order = ["/", "engine","explore","settings"]

def check_auth(route, children):
    # This can be replaced by a custom function that checks if the user is
    # logged in and has the required permissions.

    # routes that are public or only for admin
    # the rest only requires login
    public_paths = ["/","docs","engine","explore","utilities","policies","settings","account"]
    admin_paths = [""]

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

class S3Storage(dict):
    def __init__(self, aws_access_key_id, aws_secret_access_key, region_name, bucket_name):
        #super().__init__(self,
        #    aws_access_key_id = aws_access_key_id,
        #    aws_secret_access_key = aws_secret_access_key,
        #    region_name = region_name,
        #    bucket_name = bucket_name)
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.bucket_name = bucket_name
        # I'm deliberately not adding Boto S3 object as an attribute 
        # since it is not JSON serializable

    def get_client(self):
        session = boto3.Session(
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name
        )
        return session.client('s3')

    def is_alive(self):
        client = self.get_client()
        if client is not None:
            buckets = client.list_buckets()
            for bucket in buckets['Buckets']:
                if bucket['Name'] == self.bucket_name:
                    return True
        return False

        
    def upload_file(self, file_name, object_name=None):
        if self.is_alive():
            client = self.get_client()
            if object_name is None:
                object_name = file_name
            
            client.upload_file(file_name, self.bucket_name, object_name)
            return f"https://{self.bucket_name}.s3.amazonaws.com/{object_name}"
        return f"Upload to bucket:{self.bucket_name} failed file_name:{file_name} object_name:{object_name}"
    def load_metadata(self, session_name):
        # Use the get_object method to read the file        
        if self.is_alive():
            client = self.get_client()
            client.download_file(self.bucket_name, f'{session_name}.metadata', f'/tmp/{session_name}.metadata')

            with open(f'/tmp/{session_name}.metadata', 'rb') as fileObj:
                # Access the content of the file from the response
                metadata = pickle.load(fileObj)

            print(type(metadata))

        return metadata
    
    def load_object(self, object_name):
        # Use the get_object method to read the file
        if self.is_alive():
            client = self.get_client()
            client.download_file(self.bucket_name, object_name, f'/tmp/{object_name}')
            print(f'Downloading {object_name}')

            with open(f'/tmp/{object_name}', 'rb') as fileObj:
                # Access the content of the file from the response
                data = pickle.load(fileObj)
            return data
    
    def load_data(self, session_name):
        return self.load_object(f'{session_name}.data')
    
    def list_objects(self): 
        if self.is_alive():
            client = self.get_client()
            objects = client.list_objects(Bucket=self.bucket_name)
            objects_array = set()
            for obj in objects.get('Contents', []):
                if "." in obj["Key"]:
                    print(obj["Key"].split('.')[:-1])
                    objects_array.add(obj["Key"].split('.')[:-1][0])
            return [a for a in objects_array]
    
    def list_sessions(self):
        objects = self.list_objects()
        return [o for o in objects if "TCDSE_SESSION" in o]

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
        solara.Title(" ")
        article = articles["welcome"]
        solara.Markdown(article.markdown)


    return main
