from typing import Optional, cast
import solara
from solara.alias import rv
import dataclasses
import boto3
import os
import pickle
import pprint
from cryptography.fernet import Fernet
from dotenv import dotenv_values
import secrets
from requests_oauthlib import OAuth2Session
from typing import Dict
from ..data import articles

config = {
    **dotenv_values(".env.global"),  # global
    **dotenv_values(".env.local"),  # local sensitive variables
    **os.environ,  # override loaded values with environment variables
}

session_storage: Dict[str, Dict[str,str]] = {}

github_client = OAuth2Session(config['github_client_id'], 
                    scope=[config['github_scope']], 
                    redirect_uri=config['github_redirect_uri'])
google_client = OAuth2Session(config['google_client_id'], 
                    scope=[config['google_scope']], 
                    redirect_uri=config['google_redirect_uri'])

route_order = ["/", "engine","explore","settings", "docs", "utilities", "account"] # "policies"

def store_in_session_storage(key, value):
    sesssion_id = solara.get_session_id()
    if sesssion_id in session_storage.keys():
        session_storage[sesssion_id][key] = value
    else:
        session_storage[sesssion_id] = {key: value}

def read_from_session_storage(key):
    sesssion_id = solara.get_session_id()
    if sesssion_id in session_storage.keys():
        if key in session_storage[sesssion_id].keys():
            return session_storage[sesssion_id][key]
    return None

def check_auth(route, children):
    # This can be replaced by a custom function that checks if the user is
    # logged in and has the required permissions.

    # routes that are public or only for admin
    # the rest only requires login
    public_paths = ["/", "engine", "explore", "settings", "docs", "utilities", "account"] # "policies"
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
    user_profile: Dict = None
    auth_company: str = None
    admin: bool = False

    def get_unique_id(self):
        if self.user_profile and self.auth_company:
            unique_id = f'{self.auth_company}-{self.user_profile["id"]}'
        else:
            unique_id = f'{self.username}'
        return unique_id


user = solara.reactive(cast(Optional[User], None))

def test_logon():
    test_user = User(username="test", admin=False)
    store_in_session_storage('user', test_user)
    user.set(test_user)

@solara.component
def LoginForm():
    github_authorization_url, github_state = github_client.authorization_url(
        config['github_authorization_base_url'],
        access_type="offline", 
        prompt="select_account"
    )

    google_authorization_url, google_state = google_client.authorization_url(
        config['google_authorization_base_url'],
        access_type="offline", 
        prompt="select_account"
    )

    store_in_session_storage('github_state', github_state)
    store_in_session_storage('google_state', google_state)

    username = solara.use_reactive("")
    password = solara.use_reactive("")
    with solara.Card("Login"):
        with solara.Row():
            solara.Button(label="Login via Google", icon_name="mdi-google", 
                attributes={"href": google_authorization_url}, text=True, outlined=True, 
                on_click=lambda: store_in_session_storage('auth_company','google'))
            solara.Button(label="Login via GitHub", icon_name="mdi-github-circle", 
                attributes={"href": github_authorization_url}, text=True, outlined=True,
                on_click=lambda: store_in_session_storage('auth_company','github'))
            if config.get('enable_test_logon', 'False').lower() == 'true':
                solara.Button(label="Login via Local Test User", icon_name="mdi-account",
                    text=True, outlined=True, on_click=test_logon)

def logout():
    store_in_session_storage('user', None)
    user.set(None)


mobile_menu_open = solara.reactive(False)

@solara.component
def Layout(children=[]):
    user.value = read_from_session_storage('user')

    router = solara.use_context(solara.routing.router_context)
    route, routes = solara.use_route(peek=True)

    if route is None:
        return solara.Error("Route not found")
    
    children = check_auth(route, children)



    with solara.AppLayout(children=children, title="", navigation=False) as main:
        with solara.AppBar():
            # Mobile Menu Dialog (Moved inside AppBar to prevent layout split)
            with rv.Dialog(v_model=mobile_menu_open.value, 
                           on_v_model=mobile_menu_open.set, 
                           fullscreen=True, 
                           transition="dialog-bottom-transition",
                           overlay_opacity=0.9,
                           style_="z-index: 2000;"): 
                
                with rv.Card(style_="padding: 20px;"):
                    with rv.Toolbar(dark=True, color="#1c4220", dense=False, flat=True): 
                        rv.ToolbarTitle(children=["Menu"])
                        rv.Spacer()
                        solara.Button(icon_name="mdi-close", icon=True, on_click=lambda: mobile_menu_open.set(False), style={"color": "white"})
                    
                    # Use standard Buttons in a Column for reliable clicking
                    with solara.Column(style={"margin-top": "20px", "gap": "10px"}):
                        for route_entry in routes:
                            if route_entry.path == "account":
                                continue
                            name = route_entry.path if route_entry.path != "/" else "Welcome"
                            
                            is_active = (route_entry.path == route.path) if route else False
                            
                            def on_click_nav(r=route_entry):
                                router.push(r.path)
                                mobile_menu_open.set(False)
                            
                            # Styled button to look like a menu item
                            solara.Button(label=name, 
                                          on_click=on_click_nav, 
                                          text=True, 
                                          style={"justify-content": "flex-start", "height": "50px", "font-size": "1.2rem", "width": "100%", "background-color": "rgba(0,0,0,0.05)" if is_active else "transparent"})
                                          
                        solara.Markdown("---") # Divider substitute
                        
                        if user.value:
                            solara.Text(f"Logged in as {user.value.username}", style={"padding": "10px", "font-weight": "bold"})
                            def on_click_logout():
                                logout()
                                mobile_menu_open.set(False)
                            solara.Button(label="Logout", icon_name="mdi-logout", on_click=on_click_logout, 
                                          text=True, style={"justify-content": "flex-start", "height": "50px", "color": "red", "width": "100%"})
                        else:
                            def on_click_login():
                                router.push("/account")
                                mobile_menu_open.set(False)
                            solara.Button(label="Login", icon_name="mdi-login", on_click=on_click_login, 
                                          text=True, style={"justify-content": "flex-start", "height": "50px", "color": "green", "width": "100%"})

            with solara.Row(style="width: 100%; align-items: center"):
                # Left Column: Logo + Text
                with solara.Row(style="display: flex; align-items: center"):
                     rv.Img(src="/static/public/tomorrows-cities-logo-header.png", height="50", contain=True, style_="max-width: 150px")
                     #solara.Text("TCDSE WebApp", style={"width": "180px", "font-weight": "bold", "font-size": "1.5em"})
                
                rv.Spacer()

                # Center Column: Tabs (Desktop Only)
                with solara.Div(classes=["mobile-hide"]):
                    with solara.lab.Tabs(align="center"):
                        for route in routes:
                            if route.path == "account":
                                continue
                            name = route.path if route.path != "/" else "Welcome"
                            # in this case we disable the tab
                            solara.lab.Tab(name, path_or_route=route, disabled=False)
                
                rv.Spacer()

                # Right Column: Login/User Info (Desktop Only)
                with solara.Div(classes=["mobile-hide"], style="display: flex; align-items: center"):
                    if user.value:
                        solara.Text(f"Logged in as {user.value.username} as {'admin' if user.value.admin else 'user'}")
                        with solara.Tooltip("Logout"):
                            with solara.Link(f"/account"):
                                solara.Button(icon_name="mdi-logout", icon=True, on_click=logout)
                    else:
                        with solara.Link(f"/account"):
                            solara.Button(icon_name="mdi-login",label='LOGIN', icon=True, style={"margin-right": "10px"})
                
                # Hamburger Button (Mobile Only)
                # Using Div with mobile-show class to hide on desktop using !important
                # Inline style ensures flex behavior when visible on mobile
                with solara.Div(classes=["mobile-show"], style="display: flex"):
                    solara.Button(icon_name="mdi-menu", icon=True, on_click=lambda: mobile_menu_open.set(not mobile_menu_open.value))

    
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

def connect_storage():
    print('reviving storage from env')
    try:

        storage = S3Storage(
                    config['aws_access_key_id'],
                    config['aws_secret_access_key'],
                    config['region_name'],
                    config['bucket_name'])
        print('storage is', storage)
        if storage.is_alive():
            return storage
    except Exception as e:
        print(e)
        return None

storage = solara.reactive(connect_storage())  

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
