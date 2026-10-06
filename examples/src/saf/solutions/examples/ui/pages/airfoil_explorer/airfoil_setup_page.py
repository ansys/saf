import dash
from dash import html

dash.register_page(
    __name__,
    name="Airfoil Setup",
    path_template="/projects/<project_id>/airfoil-explorer/airfoil-setup",
)


#TODO replace with actual content for the Airfoil Setup page
layout = html.Div("Airfoil Setup")