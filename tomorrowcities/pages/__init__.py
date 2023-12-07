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
    public_paths = ["/","docs","engine","utilities","policies","settings","account"]
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
