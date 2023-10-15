from typing import Optional

import solara

from .. import data
from ..components.article import Overview


@solara.component
def Page(name: Optional[str] = None, page: int = 0, page_size=100):
    if name is None:
        with solara.Column() as main:
            solara.Title("TCDSE» Documentation")
            Overview()
            solara.Text('Images by rawpixel.com')
        return main
    if name not in data.articles:
        return solara.Error(f"No such article: {name!r}")
    article = data.articles[name]
    with solara.ColumnsResponsive(12) as main:
        solara.Title("TCDSE » Documentation » " + article.title)
        with solara.Link("/docs"):
            solara.Text("« Back to documentation")
        with solara.Card():
            solara.Markdown(article.markdown)
    return main