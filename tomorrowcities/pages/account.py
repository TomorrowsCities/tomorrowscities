from typing import Optional
import solara
import os
import pprint

from . import user
from . import LoginForm

@solara.component
def Page():
    solara.Title("TCDSE » Account")
    if user.value is None:
        LoginForm()

