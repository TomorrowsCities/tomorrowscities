from typing import Optional
import solara

from . import user
from . import LoginForm

@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    solara.Title("TCDSE » Account")
    if user.value is None:
        LoginForm()
    else:    
        solara.Markdown(f'Hello {user.value.username}')
