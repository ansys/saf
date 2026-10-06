import dash
from dash import html

dash.register_page(
    __name__,
    name="About",
    path_template="/projects/<project_id>/airfoil-explorer/about",
)


#TODO replace with actual content for the About page
layout = html.Div("Airfoil Explorer")