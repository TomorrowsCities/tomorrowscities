import reacton.ipyvuetify as rv
import solara

from ..data import articles

@solara.component
def ArticleCard(name):
    article = articles[name]
    with rv.Card(max_width="300px", height="360px", class_="d-flex flex-column") as main:
        with solara.Link(f"/docs/{name}"):
            rv.Img(height="150", src=article.image_url)
        rv.CardTitle(children=[article.title])
        with rv.CardText(class_="flex-grow-1"):
            solara.Text(article.description, style={"text-align": "justify", "display": "block"})
        with rv.CardActions():
            with solara.Link(f"/docs/{name}"):
                solara.Button("Read article", text=True, icon_name="mdi-book-open")
    return main


@solara.component
def Overview():
    # welcome is removed
    # 1.1. Data Formats
    # 1.2. Metrics
    # 1.3. Policies
    # 1.4. Contributing
    # 2.1 Flood
    # 2.2. Landslide
    # 2.3 Road Networks
    # 2.4 Power Network Analysis
    order = ["data", "metrics", "policies", "contribution", "flood", "landslide", "road", "power"]
    
    with solara.ColumnsResponsive(12) as main:
        with solara.Card():
            with solara.ColumnsResponsive(12, small=6, large=3):
                for name in order:
                     if name in articles:
                        ArticleCard(name)
    solara.Title(" ")
    return main