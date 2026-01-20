import reacton.ipyvuetify as rv
import solara

from ..data import articles

@solara.component
def ArticleCard(name):
    article = articles[name]
    with rv.Card(class_="d-flex flex-column fill-height", hover=True) as main:
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
    # How to Use
    # Changelog   
    # Data Formats
    # Metrics
    # Policies
    # Contributing
    # Flood
    # Landslide
    # Road Networks
    # Power Network Analysis    

    order = ["howtouse", "changelog", "data", "metrics", "policies", "contribution", "flood", "landslide", "road", "power"]
    
    with rv.Row(wrap=True) as main:
        for name in order:
                if name in articles:
                    with rv.Col(cols=12, sm=6, lg=3, class_="pa-4"):
                    	ArticleCard(name)
    # solara.Title(" ")
    return main