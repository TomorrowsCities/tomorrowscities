import reacton.ipyvuetify as rv
import solara

from ..data import articles

@solara.component
def ArticleCard(name):
    article = articles[name]
    with rv.Card(max_width="400px") as main:
        rv.CardTitle(children=[article.title])
        with rv.CardText():
            solara.Markdown(article.description)
            with solara.Link(f"/docs/{name}"):
                solara.Button("Read article", text=True, icon_name="mdi-book-open")
    return main


@solara.component
def Overview():
    with solara.ColumnsResponsive(12) as main:
        with solara.Card():
            with solara.ColumnsResponsive(12, small=6, large=4):
                for name in articles:
                    ArticleCard(name)
    return main