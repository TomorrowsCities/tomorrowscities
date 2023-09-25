import solara

from . import user

@solara.component
def Page():
    assert user.value is not None
    solara.Markdown(f"Hi {user.value.username}, you are an admin")